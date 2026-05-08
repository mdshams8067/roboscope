"""
CuratorAgent — Agent 2
Uses Claude with tool use to score and filter articles.
Claude can call fetch_article_text when a snippet is too short to judge.
"""
import json
import logging

import anthropic
import requests
from bs4 import BeautifulSoup

from core.config import (
    ANTHROPIC_API_KEY, CLAUDE_MODEL,
    TOP_N_ARTICLES, MINIMUM_RELEVANCE_SCORE,
    BREAKTHROUGH_MIN_SCORE, BREAKTHROUGH_MIN_TIER,
)

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Tool definition ───────────────────────────────────────────────────────────
# This is the contract Claude reads. When it decides a snippet is too short,
# it will emit a tool_use block with name="fetch_article_text" and the URL.

FETCH_ARTICLE_TOOL = {
    "name": "fetch_article_text",
    "description": (
        "Fetch the full text of an article when the snippet is under 200 characters "
        "and more context is needed to evaluate relevance. "
        "Returns the first 2000 characters of the article body."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The article URL to fetch"}
        },
        "required": ["url"],
    },
}

SYSTEM_PROMPT = """You are a robotics research curator for a student-focused news feed.

Each article includes its source tier (1 = highest, 3 = lowest). Use the tier as a signal
when assessing credibility and novelty — but score on content, not tier alone.

Score each article on four axes (1–10 each):
1. Research depth   — new method, result, or system presented? (weight 0.35)
2. Industry impact  — real deployment or commercial milestone? (weight 0.25)
3. Student access   — can a final-year robotics student engage meaningfully? (weight 0.20)
4. Novelty          — genuinely new work vs. incremental/survey/workshop content? (weight 0.20)

Composite score = (depth×0.35) + (impact×0.25) + (accessibility×0.20) + (novelty×0.20), rounded to one decimal.

Flag novelty LOW (≤4) for papers containing: workshop, survey, extended abstract, technical report.

If a snippet is under 200 characters, call fetch_article_text to get more context before scoring.

Additionally, set "breakthrough": true if ALL of the following are true:
- composite score ≥ 8.5
- source tier ≤ 2 (i.e., tier 1 or tier 2 — not community aggregators)
- the article describes a genuinely novel result: first-ever demonstration, large benchmark gain,
  real-world deployment of a previously lab-only system, or acceptance at a top-tier venue

Respond ONLY with valid JSON — no preamble, no markdown fences:
{"scores": [{"url": "<url>", "score": <float>, "breakthrough": <bool>, "breakthrough_reason": "<one sentence or null>", "axes": {"depth": <int>, "impact": <int>, "accessibility": <int>, "novelty": <int>}, "reason": "<one sentence>"}]}"""


# ── Tool implementation ───────────────────────────────────────────────────────

def _fetch_article_text(url: str) -> str:
    """Run when Claude calls the fetch_article_text tool. Claude asks; we execute."""
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "RoboScope/1.0"})
        resp.raise_for_status()
    except requests.RequestException as e:
        return f"Error fetching article: {e}"

    soup = BeautifulSoup(resp.text, "html.parser")
    container = soup.find("article") or soup.find("main") or soup.body
    if not container:
        return "Could not extract article text."
    return container.get_text(separator=" ", strip=True)[:2000]


# ── Tool-use loop ─────────────────────────────────────────────────────────────

def _run_scoring_loop(articles: list[dict]) -> list[dict]:
    """
    Multi-turn Claude call. Claude may call fetch_article_text one or more times
    before returning its final JSON scores. We service each tool call and loop back.
    """
    article_list = "\n\n".join(
        f"URL: {a['url']}\nTitle: {a['title']}\nSource tier: {a.get('_tier', 2)}\nSnippet ({len(a['snippet'])} chars): {a['snippet']}"
        for a in articles
    )
    messages = [{"role": "user", "content": f"Score these articles:\n\n{article_list}"}]

    while True:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=[FETCH_ARTICLE_TOOL],
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    try:
                        return json.loads(block.text)["scores"]
                    except (json.JSONDecodeError, KeyError):
                        logger.warning("[CuratorAgent] Failed to parse scores JSON")
                        return []
            return []

        if response.stop_reason == "tool_use":
            # Add Claude's response (with tool_use blocks) to history before replying
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    url = block.input.get("url", "")
                    logger.info(f"[CuratorAgent] Fetching full text: {url[:70]}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,   # must match the block id exactly
                        "content": _fetch_article_text(url),
                    })
            messages.append({"role": "user", "content": tool_results})
        else:
            logger.warning(f"[CuratorAgent] Unexpected stop_reason: {response.stop_reason}")
            return []


# ── Public API ────────────────────────────────────────────────────────────────

def curate(articles: list[dict]) -> list[dict]:
    if not articles:
        return []

    logger.info(f"[CuratorAgent] Scoring {len(articles)} articles...")
    scores = _run_scoring_loop(articles)

    verdict_map = {s["url"]: s for s in scores}

    scored = []
    for article in articles:
        verdict = verdict_map.get(article["url"])
        if not verdict:
            continue
        score = verdict["score"]
        if score < MINIMUM_RELEVANCE_SCORE:
            logger.info(f"Dropped (score {score} < {MINIMUM_RELEVANCE_SCORE}): {article['title'][:60]}")
            continue

        # Breakthrough: Claude must flag it AND the source must meet tier + score thresholds.
        # Claude's prompt already enforces score ≥ 8.5, but we double-check tier here
        # because Claude cannot verify the actual tier value — it only sees what we sent.
        is_breakthrough = (
            verdict.get("breakthrough", False)
            and article.get("_tier", 3) <= BREAKTHROUGH_MIN_TIER
            and score >= BREAKTHROUGH_MIN_SCORE
        )
        if is_breakthrough:
            logger.info(f"BREAKTHROUGH detected: {article['title'][:60]} — {verdict.get('breakthrough_reason')}")

        scored.append({
            **article,
            "score": score,
            "breakthrough": is_breakthrough,
            "breakthrough_reason": verdict.get("breakthrough_reason") if is_breakthrough else None,
        })

    scored.sort(key=lambda a: a["score"], reverse=True)
    selected = scored[:TOP_N_ARTICLES]
    logger.info(f"[CuratorAgent] {len(selected)} articles selected after filtering")
    return selected
