"""
ImageAgent — Agent 4

Image resolution order per article:
  1. og:image / twitter:image scraped from the article page
     — If the image comes from the same domain as the article (i.e. a site logo),
       fall through to step 2.
  2. HuggingFace paper thumbnail (huggingface.co/papers/{arxiv_id})
     — For arXiv and HuggingFace Papers sources whose og:image is a logo.
  3. (Optional) Gemini Imagen graphical abstract with LLM vision verification loop
     — Only runs when USE_GRAPHICAL_ABSTRACT=true in .env AND LLM_PROVIDER=gemini.
     — Requires Gemini billing enabled (Imagen is a paid API).
     — Best image from up to GRAPHICAL_ABSTRACT_MAX_ATTEMPTS is uploaded to Supabase.
  4. Random Unsplash robotics fallback.
"""
import io
import json
import logging
import random
import re

import PIL.Image
import requests
from bs4 import BeautifulSoup
from supabase import create_client

from core import llm
from core.config import (
    GOOGLE_API_KEY,
    SUPABASE_URL, SUPABASE_SERVICE_KEY,
    FALLBACK_IMAGES,
    USE_GRAPHICAL_ABSTRACT, GEMINI_IMAGEN_MODEL, LLM_PROVIDER,
    GRAPHICAL_ABSTRACT_MAX_ATTEMPTS, GRAPHICAL_ABSTRACT_MIN_SCORE,
)

logger = logging.getLogger(__name__)


# ── og:image scraping ─────────────────────────────────────────────────────────

def _og_image(url: str) -> str | None:
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for prop in ("og:image", "twitter:image"):
            tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if tag and tag.get("content"):
                return tag["content"].strip()
    except Exception as e:
        logger.debug(f"[ImageAgent] og:image fetch failed for {url}: {e}")
    return None


def _is_site_logo(image_url: str, article_url: str) -> bool:
    """True if the image is served from the same root domain as the article (likely a logo)."""
    try:
        from urllib.parse import urlparse
        img_host = urlparse(image_url).netloc.lstrip("www.")
        art_host = urlparse(article_url).netloc.lstrip("www.")
        return img_host == art_host or img_host.endswith("." + art_host) or art_host.endswith("." + img_host)
    except Exception:
        return False


def _arxiv_id(url: str) -> str | None:
    m = re.search(r"(\d{4}\.\d{4,5})", url)
    return m.group(1) if m else None


def _hf_paper_image(arxiv_id: str) -> str | None:
    img = _og_image(f"https://huggingface.co/papers/{arxiv_id}")
    if img and "huggingface.co" in img:
        return img
    return None


def _best_article_image(source_url: str) -> str | None:
    """
    Steps 1 and 2: real article image or HuggingFace paper thumbnail.
    Returns a URL string, or None to trigger graphical abstract / fallback.
    """
    img = _og_image(source_url)
    if img and not _is_site_logo(img, source_url):
        return img

    aid = _arxiv_id(source_url)
    if aid:
        img = _hf_paper_image(aid)
        if img:
            return img

    return None


# ── Graphical abstract (optional — requires Gemini billing) ───────────────────

def _build_prompt(summary: dict, corrections: list[str] = None) -> str:
    tag = summary.get("tags", ["robotics"])[0]
    prompt = (
        f"Scientific graphical abstract for a robotics research article. "
        f"Article: {summary['headline']}. "
        f"Domain: {tag}. "
        f"Show the core method or system, key result, clean labeled diagram elements, "
        f"arrows and flow diagrams, flat design, infographic style, white background. "
        f"No stock photos, no decorative backgrounds, no abstract art."
    )
    if corrections:
        prompt += f" Fix these issues from the previous version: {'; '.join(corrections)}."
    return prompt


def _imagen_generate(prompt: str) -> bytes:
    """Call Gemini Imagen and return PNG bytes. Raises on any failure."""
    from google import genai
    from google.genai import types as genai_types

    client = genai.Client(api_key=GOOGLE_API_KEY)
    response = client.models.generate_images(
        model=GEMINI_IMAGEN_MODEL,
        prompt=prompt,
        config=genai_types.GenerateImagesConfig(number_of_images=1),
    )
    image_bytes = response.generated_images[0].image.image_bytes
    # Normalise to PNG via PIL
    pil = PIL.Image.open(io.BytesIO(image_bytes))
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()


def _verify(image_bytes: bytes, summary: dict) -> dict:
    """Score the generated image for accuracy against the article using the LLM vision model."""
    prompt = f"""Verify this graphical abstract for accuracy against its source article.

Article: {summary['headline']}
Summary: {summary.get('what_it_does', summary.get('digest', ''))}

Score on:
1. Does it accurately represent the core method or system?
2. Does it reflect the correct application domain?
3. Are elements present that contradict or misrepresent the article?
4. Does it visually communicate the key result?
5. Is it free of generic/decorative elements unrelated to the article?

Respond ONLY in this exact JSON (no preamble, no markdown):
{{"score": <int 1-10>, "accurate": <true if score >= 8>, "inaccuracies": [<short strings>], "reasoning": "<one sentence>"}}"""

    raw = llm.vision_chat(prompt, image_bytes)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if fence:
            return json.loads(fence.group(1))
        obj = re.search(r"\{.*\}", raw, re.DOTALL)
        if obj:
            return json.loads(obj.group())
        raise


def _generate_with_verification(summary: dict) -> bytes:
    """Generate → verify → correct loop. Returns best image found."""
    corrections = []
    best_image: bytes = None
    best_score = 0

    for attempt in range(1, GRAPHICAL_ABSTRACT_MAX_ATTEMPTS + 1):
        logger.info(f"[ImageAgent] Imagen attempt {attempt}/{GRAPHICAL_ABSTRACT_MAX_ATTEMPTS}: {summary['headline'][:55]}")
        prompt = _build_prompt(summary, corrections)
        image_bytes = _imagen_generate(prompt)

        verification = _verify(image_bytes, summary)
        score = verification["score"]
        logger.info(f"[ImageAgent] Verification score {score}/10 — {verification['reasoning']}")

        if score > best_score:
            best_score = score
            best_image = image_bytes

        if verification["accurate"] and score >= GRAPHICAL_ABSTRACT_MIN_SCORE:
            logger.info(f"[ImageAgent] Accepted on attempt {attempt}")
            return best_image

        if attempt < GRAPHICAL_ABSTRACT_MAX_ATTEMPTS:
            corrections = verification["inaccuracies"]

    if best_score < GRAPHICAL_ABSTRACT_MIN_SCORE:
        logger.warning(f"[ImageAgent] Best score {best_score}/10 after {GRAPHICAL_ABSTRACT_MAX_ATTEMPTS} attempts — using best available")

    return best_image


def _upload(image_bytes: bytes, article_id: str) -> str:
    """Upload to Supabase Storage (service_role key bypasses RLS) and return public URL."""
    sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    path = f"{article_id}.png"
    buf = io.BytesIO(image_bytes)
    pil = PIL.Image.open(buf)
    out = io.BytesIO()
    pil.save(out, format="PNG")
    sb.storage.from_("roboscope-images").upload(
        path, out.getvalue(),
        {"content-type": "image/png", "upsert": "true"},
    )
    return sb.storage.from_("roboscope-images").get_public_url(path)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_images(summaries: list[dict]) -> list[dict]:
    results = []
    for summary in summaries:
        article_id = summary["article_id"]
        source_url = summary.get("source_url", "")

        # Step 1 + 2: real article image or HF paper thumbnail
        image_url = _best_article_image(source_url) if source_url else None

        if image_url:
            logger.info(f"[ImageAgent] Article image found for {article_id}: {image_url[:70]}")
            results.append({"article_id": article_id, "image_url": image_url, "is_fallback": False})
            continue

        # Step 3: optional Gemini Imagen graphical abstract
        if USE_GRAPHICAL_ABSTRACT and LLM_PROVIDER == "gemini":
            try:
                image_bytes = _generate_with_verification(summary)
                url = _upload(image_bytes, article_id)
                logger.info(f"[ImageAgent] Graphical abstract uploaded: {url[:70]}")
                results.append({"article_id": article_id, "image_url": url, "is_fallback": False})
                continue
            except Exception as e:
                logger.warning(f"[ImageAgent] Imagen failed for {article_id}: {e}")

        # Step 4: Unsplash fallback
        fallback = random.choice(FALLBACK_IMAGES)
        logger.info(f"[ImageAgent] Unsplash fallback for {article_id}")
        results.append({"article_id": article_id, "image_url": fallback, "is_fallback": True})

    return results
