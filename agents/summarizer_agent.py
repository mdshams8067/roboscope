"""
SummarizerAgent — Agent 3
For each curated article, calls the configured LLM to produce a structured JSON summary
designed for robotics students. Retries once on JSON parse failure.
"""
import hashlib
import json
import logging
import re

import requests

from core import llm
from core.text_extractor import build_context_text, extract_sections

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a robotics research communicator writing for early-stage graduate students
and researchers — people starting a Master's in robotics or AI who have solid engineering foundations
and are actively mapping the research frontier.

Your job is to explain each paper so the reader immediately understands what was built,
the core technical insight, how it fits into the current research landscape, and what it
enables or challenges next. Do not simplify — be precise and concrete.

You will receive a paper title, abstract or full text, source metadata, and optionally
a research_theme from the curation stage. If research_theme is provided, use it to frame
the paper's position in the field.

You must return ONLY valid JSON with no preamble, no markdown, no backticks.

OUTPUT SCHEMA:
{
  "headline": <string: max 12 words — describe what the system DOES, not what the paper IS.
               Must be specific enough that two different papers could not share the same headline>,

  "hook": <string: one sentence — the single most surprising, counterintuitive, or intellectually
           provocative fact about this work. Written as a human would say it out loud.
           Should make a researcher want to read further>,

  "what_it_does": <string: one sentence — what the robot or system physically or computationally
                  does, written concretely. Name the specific task, environment, or capability.
                  No vague verbs like "addresses" or "tackles">,

  "key_idea": <string: one sentence — the single core technical contribution. If it uses a known
               technique in a new way, name the technique and explain the novel application.
               Jargon is acceptable if immediately unpacked in parentheses>,

  "core_challenge": <string: one sentence — what specific technical problem or failure mode does
                   this work directly address? Look for "existing methods fail when...",
                   "the key challenge is...", "prior approaches cannot..." in the abstract.
                   Write it as the problem, not the solution>,

  "key_assumption": <string: one sentence — what assumption or limitation does this work overcome,
                   relax, or expose? Look for "unlike prior work", "without requiring",
                   "we remove the assumption that". If the paper introduces a new assumption
                   instead, state that>,

  "result": <string: one sentence — the most specific quantitative result OR the most concrete
             real-world demonstration. Must contain at least one number, a named deployment,
             or a named benchmark. Never vague>,

  "what_it_enables": <string: one sentence — what becomes possible or easier because of this work?
                     What research direction does it open or accelerate? Forward-looking>,

  "open_source": <string or null: URL if code or data is explicitly released in the abstract or
                 text. Do not guess or fabricate. null if not mentioned>,

  "tags": <list of 2-4 specific technical keywords extracted directly from the paper —
           use the paper's own terminology, e.g. "Diffusion Policy", "Sim-to-Real Transfer",
           "Contact-Rich Manipulation", "Vision-Language-Action". Do NOT use generic categories>,

  "tldr": <string: max 20 words — one sentence a researcher would say to a colleague in the
           corridor. Captures the contribution, not just the topic>
}

RULES — apply all without exception:
- Never use: "novel", "propose", "framework", "benchmark", "baseline",
  "demonstrate", "leverage", "utilize", "state-of-the-art", "sota"
- Never start a sentence with "The authors" or "This paper"
- "result" must contain at least one number OR a named deployment OR a named benchmark
- "hook" must be surprising — if it could open any robotics paper, rewrite it until it
  could only describe this one
- "headline" must be specific — two different papers must not be able to share it
- "tags" must come from the paper's own vocabulary — do not invent categories
- "tldr" must fit in one breath with no subordinate clauses
- If open_source information is not in the abstract or text, set "open_source" to null

EXAMPLE OUTPUT for a locomotion paper:
{
  "headline": "Quadruped runs on ice and gravel using touch-sensitive feet",
  "hook": "The robot learned to recover from slipping on ice without ever training on ice — just by feeling the difference in how its feet make contact.",
  "what_it_does": "A quadruped robot adapts its gait in real time to surfaces ranging from gravel to wet ice using proprioceptive feedback from force-sensitive feet, without vision.",
  "key_idea": "Rather than classifying the surface type and switching gaits, it uses a contact Jacobian estimator (a model that infers terrain stiffness from how force distributes across the foot) to continuously modulate foot placement timing.",
  "core_challenge": "Most learning-based locomotion controllers break when the real world deviates even slightly — slip on ice is outside any simulator's physics model.",
  "key_assumption": "Drops the assumption that terrain type must be classified before gait adaptation — instead treats terrain as a continuous signal inferred from contact alone.",
  "result": "Achieved 94% success rate crossing 8 surface types including wet ice and loose gravel, versus 61% for the vision-based ETH terrain classifier baseline.",
  "what_it_enables": "Blind (vision-free) robust locomotion becomes credible for confined or dark environments where onboard cameras are impractical.",
  "open_source": "github.com/example/contact-adapt-quadruped",
  "tags": ["Legged Locomotion", "Proprioceptive Adaptation", "Contact Estimation", "Blind Walking"],
  "tldr": "Quadruped learned to walk on ice by feeling contact forces — no vision, no terrain classifier needed."
}
"""

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
    result = data.get("result", "")
    has_quantity = (
        any(c.isdigit() for c in result)
        or "deployed" in result.lower()
        or "open source" in result.lower()
    )
    if not has_quantity:
        logger.warning(f"[SummarizerAgent] result field has no quantitative claim: {title}")
    return data


def _build_context(article: dict) -> str:
    """
    Returns the best available text for this article, populating _pdf_bytes
    and _context_text on the dict as a cache so downstream agents skip re-download.
    """
    if article.get("_context_text"):
        return article["_context_text"]

    pdf_bytes = article.get("_pdf_bytes")
    if not pdf_bytes:
        pdf_url = article.get("pdf_url", "")
        if pdf_url:
            try:
                r = requests.get(
                    pdf_url,
                    headers={"User-Agent": "RoboScope/1.0 (github.com/mdshams8067/roboscope)"},
                    timeout=30,
                    stream=True,
                )
                r.raise_for_status()
                pdf_bytes = r.content
                article["_pdf_bytes"] = pdf_bytes
                logger.info(f"[SummarizerAgent] PDF downloaded ({len(pdf_bytes)} bytes): {article['title'][:60]}")
            except Exception as e:
                logger.warning(f"[SummarizerAgent] PDF download failed: {e}")

    if pdf_bytes:
        sections = extract_sections(pdf_bytes)
        context_text = build_context_text(article.get("snippet", ""), sections)
        article["_context_text"] = context_text
        return context_text

    return article.get("snippet", "")


def _summarize_one(article: dict) -> dict:
    context_text = _build_context(article)
    prompt = f"Title: {article['title']}\n\nPaper content:\n{context_text}"
    if article.get("research_theme"):
        prompt += f"\n\nResearch theme (from curation): {article['research_theme']}"

    raw = llm.chat(SYSTEM_PROMPT, prompt, max_tokens=1500, temperature=0.3)
    try:
        data = _parse_json(raw)
    except json.JSONDecodeError:
        fix_prompt = (
            f"{prompt}\n\nYour previous response was not valid JSON:\n{raw}\n\n"
            "Return only the JSON object, nothing else."
        )
        data = _parse_json(llm.chat(SYSTEM_PROMPT, fix_prompt, max_tokens=1500, temperature=0.3))

    return _validate(data, article["title"])


def _fallback_summary(article: dict) -> dict:
    snippet = article.get("snippet") or ""
    return {
        "headline":        article["title"][:80],
        "hook":            snippet[:200] or "No summary available.",
        "what_it_does":    snippet or "No summary available.",
        "key_idea":        "",
        "core_challenge":  "",
        "key_assumption":  "",
        "result":          "",
        "what_it_enables": "",
        "open_source":     None,
        "tags":            ["Robotics"],
        "tldr":            article["title"][:100],
    }


def summarize(articles: list[dict]) -> list[dict]:
    summaries = []
    for article in articles:
        article_id = hashlib.sha256(article["url"].encode()).hexdigest()[:8]
        try:
            data = _summarize_one(article)
            summaries.append({
                "article_id":      article_id,
                "source_url":      article["url"],
                "headline":        data.get("headline", article["title"])[:120],
                "hook":            data.get("hook", ""),
                "what_it_does":    data.get("what_it_does", ""),
                "key_idea":        data.get("key_idea", ""),
                "core_challenge":  data.get("core_challenge", ""),
                "key_assumption":  data.get("key_assumption", ""),
                "result":          data.get("result", ""),
                "what_it_enables": data.get("what_it_enables", ""),
                "open_source":     data.get("open_source", None),
                "tags":            data.get("tags", ["Robotics"]),
                "tldr":            data.get("tldr", ""),
            })
            logger.info(f"[SummarizerAgent] {article_id} — {data.get('headline', '')[:55]}")
        except Exception as e:
            logger.warning(f"[SummarizerAgent] Fallback for {article_id}: {e}")
            fb = _fallback_summary(article)
            summaries.append({**fb, "article_id": article_id, "source_url": article["url"]})
    return summaries
