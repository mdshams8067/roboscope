"""
SummarizerAgent — Agent 3
For each curated article, calls the configured LLM to produce a structured JSON summary
designed for robotics students. Retries once on JSON parse failure.
"""
import hashlib
import json
import logging
import re

from core import llm
from core.config import TOPIC_TAGS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""
You are a robotics research communicator writing for final-year undergraduate and
graduate robotics students. Your job is to explain research clearly and concisely —
not to impress other researchers, but to make sure a student immediately understands
what was built, how it works, and why it matters.

You will receive an article title, abstract or full text, and source metadata.
You must return ONLY valid JSON with no preamble, no markdown, no backticks.

OUTPUT SCHEMA:
{{
  "headline": <string: max 12 words, must describe what the system DOES not what the paper IS>,
  "hook": <string: one sentence — the most surprising or compelling fact about this work>,
  "what_it_does": <string: one sentence — what the robot or system physically or computationally does, written concretely>,
  "key_idea": <string: one sentence — the single clever technical insight, with any jargon immediately explained in parentheses>,
  "result": <string: one sentence — the most specific quantitative result, or most concrete real-world demonstration>,
  "why_it_matters": <string: one sentence — connects to an open problem in robotics that students know about>,
  "student_note": <string: one sentence — something a student would find practically useful or intellectually interesting>,
  "tags": <list of 2-3 strings chosen ONLY from: {TOPIC_TAGS}>,
  "difficulty": <string: one of "accessible" | "intermediate" | "advanced">,
  "tldr": <string: max 20 words — the one-sentence version a student would text to a friend>
}}

RULES:
- Never use the words: "novel", "propose", "framework", "benchmark", "baseline", "demonstrate", "leverage", "utilize"
- Never start a sentence with "The authors" or "This paper"
- The "result" field must contain at least one number OR describe a specific real-world deployment — no vague claims
- The "hook" must be the most surprising thing about the work, written like a human would say it out loud
- The "tldr" must be something you could say in one breath — no subordinate clauses
- difficulty: "accessible" = any engineering student gets it; "intermediate" = needs robotics background; "advanced" = needs graduate-level background

EXAMPLE OUTPUT for a manipulation paper:
{{
  "headline": "Robot hand learns dexterous tool use from 10 minutes of video",
  "hook": "It learned to use scissors, a spatula, and a screwdriver by watching YouTube — no teleoperation data needed.",
  "what_it_does": "A robot hand watches video of humans using tools and infers how to replicate the same motions without ever being physically guided.",
  "key_idea": "It uses a vision model to extract 3D hand pose from video (figuring out finger positions from a regular camera), then maps those poses to robot joint angles using a learned correspondence model.",
  "result": "Achieved 78% success rate on 12 unseen tools, compared to 31% for the previous best method that required human demonstration data.",
  "why_it_matters": "Getting robots to use tools is one of the core unsolved problems in manipulation — most methods require expensive teleoperation setups that don't scale.",
  "student_note": "Code and dataset are open source — this is a strong starting point if you want to work on imitation learning from video.",
  "tags": ["Manipulation", "Foundation Models"],
  "difficulty": "intermediate",
  "tldr": "Robot learned to use 12 different tools just by watching YouTube videos of humans."
}}
"""

_VALID_DIFFICULTY = {"accessible", "intermediate", "advanced"}


def _parse_json(raw: str) -> dict:
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
    raise json.JSONDecodeError("No JSON object found", raw, 0)


def _validate(data: dict, title: str) -> dict:
    if data.get("difficulty") not in _VALID_DIFFICULTY:
        data["difficulty"] = "intermediate"
    result = data.get("result", "")
    has_quantity = (
        any(c.isdigit() for c in result)
        or "deployed" in result.lower()
        or "open source" in result.lower()
    )
    if not has_quantity:
        logger.warning(f"[SummarizerAgent] result field has no quantitative claim: {title}")
    return data


def _summarize_one(article: dict) -> dict:
    prompt = f"Title: {article['title']}\n\nSnippet: {article['snippet']}"
    if article.get("full_text"):
        prompt += f"\n\nFull text excerpt: {article['full_text'][:1000]}"

    raw = llm.chat(SYSTEM_PROMPT, prompt, max_tokens=1024, temperature=0.3)
    try:
        data = _parse_json(raw)
    except json.JSONDecodeError:
        fix_prompt = (
            f"{prompt}\n\nYour previous response was not valid JSON:\n{raw}\n\n"
            "Return only the JSON object, nothing else."
        )
        data = _parse_json(llm.chat(SYSTEM_PROMPT, fix_prompt, max_tokens=1024, temperature=0.3))

    return _validate(data, article["title"])


def _fallback_summary(article: dict) -> dict:
    snippet = article.get("snippet") or ""
    return {
        "headline":       article["title"][:80],
        "hook":           snippet[:200] or "No summary available.",
        "what_it_does":   snippet or "No summary available.",
        "key_idea":       "",
        "result":         "",
        "why_it_matters": "",
        "student_note":   "",
        "tags":           ["Industry"],
        "difficulty":     "intermediate",
        "tldr":           article["title"][:100],
    }


def summarize(articles: list[dict]) -> list[dict]:
    summaries = []
    for article in articles:
        article_id = hashlib.sha256(article["url"].encode()).hexdigest()[:8]
        try:
            data = _summarize_one(article)
            summaries.append({
                "article_id":     article_id,
                "source_url":     article["url"],
                "headline":       data.get("headline", article["title"])[:120],
                "hook":           data.get("hook", ""),
                "what_it_does":   data.get("what_it_does", ""),
                "key_idea":       data.get("key_idea", ""),
                "result":         data.get("result", ""),
                "why_it_matters": data.get("why_it_matters", ""),
                "student_note":   data.get("student_note", ""),
                "tags":           data.get("tags", ["Industry"]),
                "difficulty":     data.get("difficulty", "intermediate"),
                "tldr":           data.get("tldr", ""),
            })
            logger.info(f"[SummarizerAgent] {article_id} — {data.get('headline', '')[:55]}")
        except Exception as e:
            logger.warning(f"[SummarizerAgent] Fallback for {article_id}: {e}")
            fb = _fallback_summary(article)
            summaries.append({**fb, "article_id": article_id, "source_url": article["url"]})
    return summaries
