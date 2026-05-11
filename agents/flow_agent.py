"""
FlowAgent — Agent 6
Breaks down each article into a sequential visual flow diagram.
Cached in SQLite — never regenerated for the same URL.
"""
import json
import logging
import re

from core import llm
import core.database as db
from core.config import BLOCK_TYPES, FLOW_AGENT_MAX_BLOCKS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are breaking down a robotics research paper or industry news article into a
sequential flow diagram for undergraduate robotics students.

Your output must be a series of blocks that, read top to bottom, tell the complete
story of the article — what problem was solved, how, and what it means. Each block
is one logical step. Together they replace reading the full article.

Return ONLY valid JSON with no preamble, no markdown, no backticks.

OUTPUT SCHEMA:
{
  "article_type": <"research" | "industry">,
  "flow_title": <string: 6-10 word title for the flow diagram page>,
  "reading_time_seconds": <integer: estimated seconds to read all blocks>,
  "blocks": [
    {
      "id": <integer: sequential from 1>,
      "type": <string: one of the allowed block types listed below>,
      "heading": <string: 3-6 word label for this block — noun phrase, not a sentence>,
      "body": <string: 1-2 sentences maximum — plain English, no jargon without explanation>,
      "detail": <string: 1-2 additional sentences for students who want more depth — or null>,
      "has_number": <boolean: true if this block contains a specific metric or statistic>,
      "number_callout": <string: if has_number=true, the specific stat isolated e.g. "78% success rate" — else null>
    }
  ],
  "key_takeaway": <string: one sentence — the single most important thing to remember>,
  "prerequisite_concepts": <list of strings: 2-4 concepts a student should know to fully follow this>
}

ALLOWED BLOCK TYPES: problem, limitation, idea, method, data, experiment, result, insight, deployment, impact, context, announcement, next

BLOCK COUNT RULES:
- Research papers: 6-10 blocks
- Industry news: 4-7 blocks
- Never fewer than 4, never more than 12
- Every flow must start with a "problem" or "context" block
- Every flow must end with an "impact" or "next" block
- At least one block must be type "result" for research papers

WRITING RULES:
- Each block heading is a noun phrase: "The Core Problem", "Attention Mechanism", "Real-World Test"
- Body must be readable by a student who hasn't read the paper
- If a concept needs explanation, explain it inline in parentheses
- Never use: "novel", "propose", "framework", "leverage", "utilize", "demonstrate"
- Numbers must be specific: "78%" not "significantly", "3.2ms latency" not "real-time"

EXAMPLE OUTPUT (abbreviated):
{
  "article_type": "research",
  "flow_title": "Teaching Robots Tool Use From YouTube Videos",
  "reading_time_seconds": 90,
  "blocks": [
    {
      "id": 1,
      "type": "problem",
      "heading": "Robots Can't Use Tools",
      "body": "Most robots can only do tasks they were specifically programmed for. Teaching a robot to use a new tool usually requires hours of human demonstration.",
      "detail": "Teleoperation-based demonstration is the current standard. This doesn't scale.",
      "has_number": false,
      "number_callout": null
    },
    {
      "id": 4,
      "type": "result",
      "heading": "Works on 12 Unseen Tools",
      "body": "Tested on tools it had never seen before, the robot succeeded 78% of the time — more than double the 31% for the previous best method.",
      "detail": null,
      "has_number": true,
      "number_callout": "78% success rate vs 31% previous best"
    },
    {
      "id": 5,
      "type": "impact",
      "heading": "Scaling Robot Manipulation",
      "body": "This removes the biggest bottleneck in teaching robots new skills — the need for expert humans to physically guide every task.",
      "detail": null,
      "has_number": false,
      "number_callout": null
    }
  ],
  "key_takeaway": "Robots can now learn to use new tools just by watching videos, with no human guidance needed.",
  "prerequisite_concepts": ["Imitation learning", "Robot kinematics", "Computer vision"]
}
"""


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


def generate_flow(article: dict, full_text: str) -> dict | None:
    """
    Returns a flow breakdown dict for the article detail page.
    Checks SQLite cache first — never regenerates for the same URL.
    Returns None on any failure so the pipeline never breaks.
    """
    url = article.get("url", "")

    cached = db.get_flow(url)
    if cached:
        logger.info(f"[FlowAgent] Cache hit: {article.get('title', '')[:60]}")
        return cached

    text = (full_text or "").strip()[:6000]
    if not text:
        logger.warning(f"[FlowAgent] No text available for: {article.get('title', '')[:60]}")
        return None

    user_message = (
        f"Article title: {article.get('title', '')}\n"
        f"Source: {article.get('_source_key', 'unknown')}\n"
        f"Tags: {', '.join(article.get('tags', []))}\n\n"
        f"Full text:\n{text}"
    )

    try:
        raw = llm.chat(SYSTEM_PROMPT, user_message, max_tokens=2048, temperature=0.2)
        flow = _extract_json(raw)
    except Exception as e:
        logger.error(f"[FlowAgent] Failed for {article.get('title', '')[:60]}: {e}")
        return None

    # Validate block count and types
    n = len(flow.get("blocks", []))
    if n < 4 or n > FLOW_AGENT_MAX_BLOCKS:
        logger.warning(f"[FlowAgent] Block count out of range ({n}): {article.get('title', '')[:60]}")
    for block in flow.get("blocks", []):
        if block.get("type") not in BLOCK_TYPES:
            block["type"] = "method"

    logger.info(f"[FlowAgent] Generated ({n} blocks): {article.get('title', '')[:60]}")

    try:
        db.store_flow(url, flow)
    except Exception as e:
        logger.warning(f"[FlowAgent] Could not cache flow: {e}")

    return flow
