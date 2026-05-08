"""
SummarizerAgent — Agent 3
For each curated article, calls Claude to produce a structured JSON summary.
Retries once on JSON parse failure before falling back to a safe default.
"""
import hashlib
import json
import logging

import anthropic

from core.config import ANTHROPIC_API_KEY, CLAUDE_MODEL, TOPIC_TAGS

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = f"""You are a technical writer for a robotics news feed aimed at final-year engineering students.

Given an article title and snippet, produce a JSON summary with exactly these fields:
- headline: max 12 words, distinct from the original title, punchy and specific
- digest: exactly 3 sentences — technically accurate, no dumbing down, student audience
- tags: 2–3 items chosen ONLY from this list: {TOPIC_TAGS}
- image_prompt: one sentence describing a photorealistic or infographic scene for image generation

Respond ONLY with valid JSON. No preamble, no markdown fences, no extra fields.

Example output:
{{
  "headline": "New Legged Robot Masters Outdoor Terrain Without GPS",
  "digest": "Sentence one about the method. Sentence two about results. Sentence three about implications.",
  "tags": ["Legged", "SLAM"],
  "image_prompt": "A quadruped robot navigating rocky mountain terrain at dusk, photorealistic."
}}"""


def _summarize_one(article: dict, retry: bool = True) -> dict:
    """Call Claude for a single article. Retries once on JSON parse error."""
    prompt = f"Title: {article['title']}\n\nSnippet: {article['snippet']}"
    if article.get("full_text"):
        prompt += f"\n\nFull text excerpt: {article['full_text'][:1000]}"

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        if retry:
            # Re-prompt Claude with the bad output and ask it to fix the JSON
            fix_messages = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": raw},
                {"role": "user", "content": "That response was not valid JSON. Return only the JSON object, nothing else."},
            ]
            fix_resp = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=fix_messages,
            )
            return json.loads(fix_resp.content[0].text.strip())
        raise


def _fallback_summary(article: dict) -> dict:
    """Safe default used when Claude call or parse fails entirely."""
    return {
        "headline": article["title"][:80],
        "digest": article["snippet"] or "No summary available.",
        "tags": ["Industry"],
        "image_prompt": "A robotics research laboratory with modern equipment, photorealistic.",
    }


# ── Public API ────────────────────────────────────────────────────────────────

def summarize(articles: list[dict]) -> list[dict]:
    summaries = []
    for article in articles:
        article_id = hashlib.sha256(article["url"].encode()).hexdigest()[:8]
        try:
            data = _summarize_one(article)
            summaries.append({
                "article_id":   article_id,
                "headline":     data.get("headline", article["title"])[:120],
                "digest":       data.get("digest", ""),
                "tags":         data.get("tags", ["Industry"]),
                "image_prompt": data.get("image_prompt", ""),
            })
            logger.info(f"[SummarizerAgent] Summarized: {article_id} — {data.get('headline', '')[:50]}")
        except Exception as e:
            logger.warning(f"[SummarizerAgent] Fallback for {article_id}: {e}")
            fb = _fallback_summary(article)
            summaries.append({**fb, "article_id": article_id})

    return summaries
