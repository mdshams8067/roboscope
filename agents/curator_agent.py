"""
CuratorAgent — Agent 2
Scores and filters articles using the configured LLM provider.
Processes articles in batches to stay within free-tier rate limits.
"""
import json
import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from core import llm
from core.config import (
    TOP_N_ARTICLES, MINIMUM_RELEVANCE_SCORE,
    BREAKTHROUGH_MIN_SCORE, BREAKTHROUGH_MIN_TIER,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a robotics research curator for a student-focused news feed.

STEP 1 — ROBOTICS RELEVANCE (hard filter, apply first):
An article is robotics-relevant ONLY if it is directly about one or more of:
- Physical robots (manipulators, legged/wheeled robots, humanoids, drones, surgical robots)
- Core robotics capabilities (motion planning, SLAM, grasping, locomotion, teleoperation, sim-to-real)
- AI/ML applied to physical autonomous systems (embodied AI, robot learning, VLA models)
- Robotics hardware (actuators, sensors, grippers, exoskeletons)
- Robotics industry milestones (deployment, funding, acquisition of a robotics company)

If an article is about general AI, general ML, computer science, mathematics, materials science,
memory chips, drug discovery, or any other field NOT directly involving physical robots or
autonomous physical systems, assign score=0 and set robotics_relevant=false.
Do NOT give such articles a pass because they mention "AI" — the subject must be physical systems.

STEP 2 — SCORING (only for robotics-relevant articles):
Each article includes its source tier (1 = highest, 3 = lowest).

Score each article on four axes (1–10 each):
1. Research depth   — new method, result, or system presented? (weight 0.35)
2. Industry impact  — real deployment or commercial milestone? (weight 0.25)
3. Student access   — can a final-year robotics student engage meaningfully? (weight 0.20)
4. Novelty          — genuinely new work vs. incremental/survey/workshop content? (weight 0.20)

Composite score = (depth×0.35) + (impact×0.25) + (accessibility×0.20) + (novelty×0.20), rounded to one decimal.

Flag novelty LOW (≤4) for papers containing: workshop, survey, extended abstract, technical report.

Additionally, set "breakthrough": true if ALL of the following are true:
- composite score ≥ 8.5
- source tier ≤ 2 (tier 1 or tier 2 — not community aggregators)
- the article describes a genuinely novel result: first-ever demonstration, large benchmark gain,
  real-world deployment of a previously lab-only system, or acceptance at a top-tier venue

Respond ONLY with valid JSON — no preamble, no markdown fences:
{"scores": [{"url": "<url>", "score": <float>, "robotics_relevant": <bool>, "breakthrough": <bool>, "breakthrough_reason": "<one sentence or null>", "axes": {"depth": <int>, "impact": <int>, "accessibility": <int>, "novelty": <int>}, "reason": "<one sentence>"}]}"""


def _fetch_article_text(url: str) -> str:
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


def _extract_json(raw: str) -> dict:
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    arr = re.search(r"\[.*\]", raw, re.DOTALL)
    if arr:
        return json.loads(arr.group())
    obj = re.search(r"\{.*\}", raw, re.DOTALL)
    if obj:
        return json.loads(obj.group())
    raise ValueError(f"No JSON found in response: {raw[:300]}")


def _score_batch(articles: list[dict]) -> list[dict]:
    article_list = "\n\n".join(
        f"URL: {a['url']}\nTitle: {a['title']}\nSource tier: {a.get('_tier', 2)}\nSnippet ({len(a['snippet'])} chars): {a['snippet']}"
        for a in articles
    )
    try:
        raw = llm.chat(SYSTEM_PROMPT, f"Score these articles:\n\n{article_list}", max_tokens=4096, temperature=0.2)
        parsed = _extract_json(raw)
        return parsed if isinstance(parsed, list) else parsed["scores"]
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"[CuratorAgent] Failed to parse scores JSON: {e}")
        return []
    except RuntimeError as e:
        logger.warning(f"[CuratorAgent] LLM unavailable, skipping batch: {e}")
        return []


def curate(articles: list[dict]) -> list[dict]:
    if not articles:
        return []

    logger.info(f"[CuratorAgent] Scoring {len(articles)} articles in batches...")
    scores = []
    batch_size = 10
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        logger.info(f"[CuratorAgent] Batch {i // batch_size + 1}: {len(batch)} articles")
        scores.extend(_score_batch(batch))
        if i + batch_size < len(articles):
            time.sleep(4)

    verdict_map = {s["url"]: s for s in scores}

    scored = []
    for article in articles:
        verdict = verdict_map.get(article["url"])
        if not verdict:
            continue

        if not verdict.get("robotics_relevant", True):
            logger.warning(f"Dropped (not robotics): {article['title'][:60]}")
            continue

        score = verdict["score"]
        if score < MINIMUM_RELEVANCE_SCORE:
            logger.info(f"Dropped (score {score} < {MINIMUM_RELEVANCE_SCORE}): {article['title'][:60]}")
            continue

        is_breakthrough = (
            verdict.get("breakthrough", False)
            and article.get("_tier", 3) <= BREAKTHROUGH_MIN_TIER
            and score >= BREAKTHROUGH_MIN_SCORE
        )
        if is_breakthrough:
            logger.info(f"BREAKTHROUGH: {article['title'][:60]} — {verdict.get('breakthrough_reason')}")

        scored.append({
            **article,
            "score": score,
            "breakthrough": is_breakthrough,
            "breakthrough_reason": verdict.get("breakthrough_reason") if is_breakthrough else None,
        })

    scored.sort(key=lambda a: a["score"], reverse=True)

    # Enforce research paper quota: 70% of slots reserved for arXiv/HF papers.
    # Remaining slots filled with editorial/news for industry context.
    research_keys = {"arxiv_conference_accepted", "arxiv_preprint", "huggingface_daily_papers"}
    research = [a for a in scored if a.get("_source_key") in research_keys]
    news     = [a for a in scored if a.get("_source_key") not in research_keys]

    research_quota = max(int(TOP_N_ARTICLES * 0.7), min(len(research), TOP_N_ARTICLES))
    news_quota     = TOP_N_ARTICLES - min(len(research), research_quota)

    selected = research[:research_quota] + news[:news_quota]
    selected = selected[:TOP_N_ARTICLES]

    r_count = sum(1 for a in selected if a.get("_source_key") in research_keys)
    logger.info(f"[CuratorAgent] {len(selected)} articles selected ({r_count} research, {len(selected)-r_count} news)")
    return selected
