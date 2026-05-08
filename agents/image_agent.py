"""
ImageAgent — Agent 4
Generates a graphical abstract per article using Gemini Imagen, then runs a
Claude vision verification loop to ensure the image matches the article content.
Uploads accepted images to Supabase Storage. Falls back to Unsplash on any error.
"""
import base64
import io
import json
import logging
import random

import anthropic
from google import genai
from google.genai import types as genai_types
from supabase import create_client

from core.config import (
    ANTHROPIC_API_KEY, GOOGLE_API_KEY,
    SUPABASE_URL, SUPABASE_KEY,
    CLAUDE_MODEL, IMAGEN_MODEL, FALLBACK_IMAGES,
    GRAPHICAL_ABSTRACT_MAX_ATTEMPTS, GRAPHICAL_ABSTRACT_MIN_SCORE,
)

logger = logging.getLogger(__name__)
_imagen_client = genai.Client(api_key=GOOGLE_API_KEY)


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(summary: dict, corrections: list[str] = None) -> str:
    """
    Constructs the Imagen generation prompt.
    On retry attempts, appends the specific inaccuracies Claude flagged
    so Imagen addresses them directly.
    """
    tag = summary.get("tags", ["robotics"])[0]
    base = f"""Create a scientific graphical abstract for a robotics research article.
Communicate the entire article at a glance — no reading required.

Article: {summary['headline']}
Summary: {summary['digest']}
Domain: {tag}

The image must show:
- The core method or system being proposed (draw it, label it clearly)
- The key result or metric (diagram, chart, or visual comparison)
- Clean labeled elements — infographic style, white background, clear hierarchy
- Arrows, icons, flow diagrams, minimal text labels only
- Style: flat design, scientific infographic

Do NOT generate: stock photos, decorative backgrounds, abstract art, or any
element not directly derived from the article."""

    if corrections:
        fixes = "\n".join(f"- {c}" for c in corrections)
        base += f"\n\nIMPORTANT — fix ALL of these inaccuracies from the previous version:\n{fixes}"

    return base.strip()


# ── Gemini Imagen call ────────────────────────────────────────────────────────

def _generate_image(prompt: str) -> bytes:
    """Calls Gemini Imagen 3 via the new google-genai SDK and returns raw PNG bytes."""
    response = _imagen_client.models.generate_images(
        model=IMAGEN_MODEL,
        prompt=prompt,
        config=genai_types.GenerateImagesConfig(
            number_of_images=1,
            safety_filter_level="BLOCK_ONLY_HIGH",
        ),
    )
    buf = io.BytesIO()
    response.generated_images[0].image.pil_image.save(buf, format="PNG")
    return buf.getvalue()


# ── Claude vision verification ────────────────────────────────────────────────

def _verify(image_bytes: bytes, summary: dict) -> dict:
    """
    Sends the image to Claude vision. Claude scores accuracy 1–10 and lists
    any specific inaccuracies so the next generation attempt can fix them.
    """
    ac = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    response = ac.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": image_b64},
                },
                {
                    "type": "text",
                    "text": f"""Verify this graphical abstract for accuracy against its source article.

Article: {summary['headline']}
Summary: {summary['digest']}

Score on:
1. Does it accurately represent the core method or system?
2. Does it reflect the correct application domain?
3. Are elements present that contradict or misrepresent the article?
4. Does it visually communicate the key result?
5. Is it free of generic/decorative elements unrelated to the article?

Respond ONLY in this exact JSON (no preamble, no markdown):
{{"score": <int 1-10>, "accurate": <true if score >= 8>, "inaccuracies": [<short strings>], "reasoning": "<one sentence>"}}""",
                },
            ],
        }],
    )

    return json.loads(response.content[0].text.strip())


# ── Feedback loop ─────────────────────────────────────────────────────────────

def _generate_graphical_abstract(summary: dict) -> bytes:
    """
    Runs the generate → verify → correct loop up to MAX_ATTEMPTS times.
    Always returns the best image found — never returns None.
    """
    corrections = []
    best_image: bytes = None
    best_score = 0

    for attempt in range(1, GRAPHICAL_ABSTRACT_MAX_ATTEMPTS + 1):
        logger.info(f"[ImageAgent] Attempt {attempt}/{GRAPHICAL_ABSTRACT_MAX_ATTEMPTS}: {summary['headline'][:55]}")

        prompt = _build_prompt(summary, corrections)
        image_bytes = _generate_image(prompt)

        verification = _verify(image_bytes, summary)
        score = verification["score"]
        logger.info(f"[ImageAgent] Score: {score}/10 — {verification['reasoning']}")

        if score > best_score:
            best_score = score
            best_image = image_bytes

        if verification["accurate"] and score >= GRAPHICAL_ABSTRACT_MIN_SCORE:
            logger.info(f"[ImageAgent] Accepted on attempt {attempt}")
            break

        if attempt < GRAPHICAL_ABSTRACT_MAX_ATTEMPTS:
            corrections = verification["inaccuracies"]
            logger.info(f"[ImageAgent] Corrections for next attempt: {corrections}")

    if best_score < GRAPHICAL_ABSTRACT_MIN_SCORE:
        logger.warning(
            f"[ImageAgent] Best score {best_score} below threshold after "
            f"{GRAPHICAL_ABSTRACT_MAX_ATTEMPTS} attempts — using best available"
        )

    return best_image


# ── Supabase upload ───────────────────────────────────────────────────────────

def _upload(image_bytes: bytes, article_id: str) -> str:
    """Uploads image bytes to Supabase Storage and returns the public CDN URL."""
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    path = f"{article_id}.png"
    sb.storage.from_("roboscope-images").upload(
        path, image_bytes,
        {"content-type": "image/png", "upsert": "true"},
    )
    return sb.storage.from_("roboscope-images").get_public_url(path)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_images(summaries: list[dict]) -> list[dict]:
    results = []
    for summary in summaries:
        article_id = summary["article_id"]
        try:
            image_bytes = _generate_graphical_abstract(summary)
            url = _upload(image_bytes, article_id)
            results.append({"article_id": article_id, "image_url": url, "is_fallback": False})
            logger.info(f"[ImageAgent] Uploaded: {url[:60]}")
        except Exception as e:
            logger.warning(f"[ImageAgent] Fallback for {article_id}: {e}")
            results.append({
                "article_id": article_id,
                "image_url": random.choice(FALLBACK_IMAGES),
                "is_fallback": True,
            })
    return results
