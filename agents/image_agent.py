"""
ImageAgent — Agent 4

Image resolution order per article:
  1. PDF figure extraction — download paper PDF, extract embedded images,
     match to captions, pick methodology figure via LLM, upload to Supabase
  2. Random Unsplash robotics fallback
"""
import io
import json
import logging
import random
import re

import fitz          # PyMuPDF — package name is pymupdf, import name is fitz
import pdfplumber
import PIL.Image
import requests
from supabase import create_client

from core import llm
from core.config import (
    SUPABASE_URL, SUPABASE_SERVICE_KEY,
    FALLBACK_IMAGES,
)

logger = logging.getLogger(__name__)

MIN_WIDTH_PX  = 150
MIN_HEIGHT_PX = 150
MAX_PDF_BYTES = 20 * 1024 * 1024  # 20 MB
SUPABASE_BUCKET = "roboscope-images"


# ── PDF download ──────────────────────────────────────────────────────────────

def _download_pdf(pdf_url: str, title: str) -> bytes | None:
    try:
        resp = requests.get(
            pdf_url,
            headers={"User-Agent": "RoboScope/1.0 (research aggregator; github.com/mdshams8067/roboscope)"},
            timeout=30,
            stream=True,
        )
        resp.raise_for_status()
        if int(resp.headers.get("Content-Length", 0)) > MAX_PDF_BYTES:
            logger.warning(f"[ImageAgent] PDF too large, skipping: {title[:60]}")
            return None
        pdf_bytes = resp.content
        logger.info(f"[ImageAgent] PDF downloaded ({len(pdf_bytes)} bytes): {title[:60]}")
        return pdf_bytes
    except Exception as e:
        logger.warning(f"[ImageAgent] PDF download failed for {title[:60]}: {e}")
        return None


# ── Figure extraction (PyMuPDF) ───────────────────────────────────────────────

def _extract_figures(pdf_bytes: bytes) -> list[dict]:
    figures = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        idx = 0
        for page_num in range(len(doc)):
            page = doc[page_num]
            for img_info in page.get_images(full=True):
                xref = img_info[0]
                try:
                    base = doc.extract_image(xref)
                    w, h = base["width"], base["height"]
                    if w < MIN_WIDTH_PX or h < MIN_HEIGHT_PX:
                        continue

                    img = PIL.Image.open(io.BytesIO(base["image"])).convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=85, optimize=True)

                    bbox = (0, 0, w, h)
                    for rect in page.get_image_rects(xref):
                        bbox = tuple(rect)
                        break

                    figures.append({
                        "index":    idx,
                        "page":     page_num,
                        "bbox":     bbox,
                        "y_center": (bbox[1] + bbox[3]) / 2,
                        "width":    w,
                        "height":   h,
                        "bytes":    buf.getvalue(),
                    })
                    idx += 1
                except Exception:
                    continue
        doc.close()
    except Exception as e:
        logger.warning(f"[ImageAgent] PyMuPDF extraction failed: {e}")

    logger.info(f"[ImageAgent] Extracted {len(figures)} figures")
    return figures


# ── Caption extraction (pdfplumber) ──────────────────────────────────────────

def _extract_captions(pdf_bytes: bytes) -> list[dict]:
    captions = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages):
                words = page.extract_words(x_tolerance=3, y_tolerance=3, use_text_flow=True)
                if not words:
                    continue

                lines: dict[float, list] = {}
                for w in words:
                    lines.setdefault(round(w["top"], 1), []).append(w)

                sorted_lines = [
                    (y, " ".join(w["text"] for w in sorted(lines[y], key=lambda w: w["x0"])))
                    for y in sorted(lines)
                ]

                i = 0
                while i < len(sorted_lines):
                    y, text = sorted_lines[i]
                    if text.strip().lower().startswith(("figure ", "fig.", "fig ", "figure.")):
                        parts = [text.strip()]
                        j = i + 1
                        while j < len(sorted_lines):
                            ny, ntext = sorted_lines[j]
                            if ny - sorted_lines[j-1][0] > 20:
                                break
                            if ntext.strip().lower().startswith(("figure ", "fig.", "table ", "section ")):
                                break
                            parts.append(ntext.strip())
                            j += 1
                        captions.append({"page": page_num, "y_top": y, "text": " ".join(parts)})
                        i = j
                    else:
                        i += 1
    except Exception as e:
        logger.warning(f"[ImageAgent] pdfplumber failed: {e}")

    logger.info(f"[ImageAgent] Extracted {len(captions)} captions")
    return captions


# ── Figure–caption matching ───────────────────────────────────────────────────

def _match(figures: list[dict], captions: list[dict]) -> list[dict]:
    matched = []
    for fig in figures:
        best_cap, best_dist = "", float("inf")
        for cap in captions:
            if cap["page"] != fig["page"]:
                continue
            dist = abs(cap["y_top"] - fig["y_center"])
            if dist < best_dist:
                best_dist, best_cap = dist, cap["text"]
        matched.append({**fig, "caption": best_cap})
    return matched


# ── LLM: pick methodology figure ─────────────────────────────────────────────

def _pick_figure(figures: list[dict], title: str, summary_text: str) -> int:
    caption_list = "\n".join(
        "Figure {}: {}".format(i, f["caption"] or "(no caption — page {})".format(f["page"] + 1))
        for i, f in enumerate(figures)
    )
    system = "You select the most informative figure from a robotics research paper to use as a visual summary thumbnail."
    user = f"""Paper title: {title}
Summary: {summary_text[:400]}

Available figures:
{caption_list}

Pick the single figure index (0-based integer) that best represents the paper's core methodology, architecture, or main system diagram.
- Prefer overview diagrams and architecture figures
- Avoid result graphs, ablation tables, or qualitative comparison grids
- If captions are missing, methodology figures are usually early in the paper

Return ONLY valid JSON with no preamble:
{{"chosen_index": <integer>, "reason": "<one sentence>"}}"""

    try:
        raw = llm.chat(system, user, max_tokens=150, temperature=0.1)
        obj = re.search(r"\{.*\}", raw, re.DOTALL)
        result = json.loads(obj.group() if obj else raw)
        chosen = int(result["chosen_index"])
        logger.info(f"[ImageAgent] LLM picked figure {chosen}: {result.get('reason', '')}")
        return chosen if 0 <= chosen < len(figures) else 0
    except Exception as e:
        logger.warning(f"[ImageAgent] Figure selection failed: {e} — using figure 0")
        return 0


# ── Supabase upload ───────────────────────────────────────────────────────────

def _upload(image_bytes: bytes, article_id: str) -> str | None:
    try:
        sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        path = f"{article_id}.jpg"
        sb.storage.from_(SUPABASE_BUCKET).upload(
            path, image_bytes, {"content-type": "image/jpeg", "upsert": "true"},
        )
        return sb.storage.from_(SUPABASE_BUCKET).get_public_url(path)
    except Exception as e:
        logger.warning(f"[ImageAgent] Supabase upload failed: {e}")
        return None


# ── PDF extraction pipeline ───────────────────────────────────────────────────

def _extract_pdf_figure(
    pdf_url: str, article_id: str, title: str, summary_text: str,
    cached_bytes: bytes | None = None,
) -> str | None:
    """Full PDF → figure → Supabase pipeline. Returns public URL or None."""
    pdf_bytes = cached_bytes or _download_pdf(pdf_url, title)
    if not pdf_bytes:
        return None

    figures = _extract_figures(pdf_bytes)
    if not figures:
        logger.warning(f"[ImageAgent] No figures found in PDF: {title[:60]}")
        return None

    captions = _extract_captions(pdf_bytes)
    matched  = _match(figures, captions)
    idx      = _pick_figure(matched, title, summary_text)

    chosen = matched[idx]
    logger.info(
        f"[ImageAgent] Chosen figure {idx}: page={chosen['page']}, "
        f"size={chosen['width']}×{chosen['height']}, caption={chosen['caption'][:80]}"
    )

    return _upload(chosen["bytes"], article_id)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_images(summaries: list[dict], articles: list[dict] = None) -> list[dict]:
    """
    articles is optional — used to look up pdf_url per article_id.
    If not provided, PDF extraction is skipped and Unsplash fallback is used.
    """
    article_map = {}
    if articles:
        import hashlib
        for a in articles:
            aid = hashlib.sha256(a["url"].encode()).hexdigest()[:8]
            article_map[aid] = a

    results = []
    for summary in summaries:
        article_id   = summary["article_id"]
        summary_text = summary.get("tldr") or summary.get("digest", "")

        article  = article_map.get(article_id, {})
        pdf_url  = article.get("pdf_url", "")
        title    = article.get("title", summary.get("headline", ""))

        image_url = None

        # Step 1 — PDF figure extraction (uses cached bytes from SummarizerAgent if available)
        if pdf_url:
            try:
                image_url = _extract_pdf_figure(
                    pdf_url, article_id, title, summary_text,
                    cached_bytes=article.get("_pdf_bytes"),
                )
            except Exception as e:
                logger.warning(f"[ImageAgent] PDF pipeline error for {article_id}: {e}")

        # Step 2 — Unsplash fallback
        if not image_url:
            image_url = random.choice(FALLBACK_IMAGES)
            logger.info(f"[ImageAgent] Unsplash fallback for {article_id}")
            results.append({"article_id": article_id, "image_url": image_url, "is_fallback": True})
            continue

        results.append({"article_id": article_id, "image_url": image_url, "is_fallback": False})

    return results
