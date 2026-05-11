"""
CuratorAgent — Agent 2
Selects papers via random round-robin across conferences.
Calls LLM once on the selected papers to attach research_theme and why_this_matters.
Conference acceptance is the quality filter — no scoring needed.
"""
import json
import logging
import random
import re
from collections import defaultdict

from core import llm
from core.config import TOP_N_ARTICLES

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are labelling robotics and AI research papers for a feed aimed at early-stage graduate students and researchers.

For each paper, return two fields:
- research_theme: 2-4 words using the field's own vocabulary
  (e.g. "Diffusion Policies", "Sim-to-Real Transfer", "Dexterous Manipulation", "VLA Foundation Models", "Legged Locomotion")
- why_this_matters: one sentence written to an early researcher — what open problem does this advance and why should they care?

Respond ONLY with valid JSON — no preamble, no markdown fences:
{"papers": [{"url": "<url>", "research_theme": "<theme>", "why_this_matters": "<sentence>"}]}"""


def _extract_json(raw: str) -> dict:
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    obj = re.search(r"\{.*\}", raw, re.DOTALL)
    if obj:
        return json.loads(obj.group())
    raise ValueError(f"No JSON found in response: {raw[:300]}")


def _label(articles: list[dict]) -> dict[str, dict]:
    """Single LLM call to label all selected papers. Returns url → label dict."""
    article_list = "\n\n".join(
        f"URL: {a['url']}\nTitle: {a['title']}\nAbstract: {a['snippet'][:400]}"
        for a in articles
    )
    try:
        raw = llm.chat(SYSTEM_PROMPT, f"Label these papers:\n\n{article_list}", max_tokens=4096, temperature=0.2)
        parsed = _extract_json(raw)
        papers = parsed if isinstance(parsed, list) else parsed.get("papers", [])
        return {p["url"]: p for p in papers}
    except Exception as e:
        logger.warning(f"[CuratorAgent] Labelling failed: {e} — research_theme and why_this_matters will be empty")
        return {}


def curate(articles: list[dict]) -> list[dict]:
    if not articles:
        return []

    # Group by conference and shuffle each pool independently
    by_conference: dict[str, list] = defaultdict(list)
    for a in articles:
        by_conference[a.get("conference", "unknown")].append(a)

    for pool in by_conference.values():
        random.shuffle(pool)

    # Round-robin: one paper from each conference before any gets a second slot
    conferences = list(by_conference.keys())
    pointers = {conf: 0 for conf in conferences}
    selected = []

    while len(selected) < TOP_N_ARTICLES:
        added = 0
        for conf in conferences:
            if len(selected) >= TOP_N_ARTICLES:
                break
            idx = pointers[conf]
            pool = by_conference[conf]
            if idx < len(pool):
                selected.append(pool[idx])
                pointers[conf] += 1
                added += 1
        if added == 0:
            break

    conf_counts = defaultdict(int)
    for a in selected:
        conf_counts[a.get("conference", "unknown")] += 1
    logger.info(f"[CuratorAgent] {len(selected)} selected: {dict(conf_counts)}")

    # Label selected papers with research_theme and why_this_matters
    label_map = _label(selected)
    for article in selected:
        label = label_map.get(article["url"], {})
        article["research_theme"]   = label.get("research_theme", "")
        article["why_this_matters"] = label.get("why_this_matters", "")
        article["breakthrough"]     = False
        article["breakthrough_reason"] = None

    return selected
