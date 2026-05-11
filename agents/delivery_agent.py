"""
DeliveryAgent — Agent 5
Joins curated articles, summaries, images, and flow diagrams into feed.json.
"""
import hashlib
import json
import logging
import os
from datetime import datetime, timezone

from agents.flow_agent import generate_flow
import core.database as db
from core.config import PAPERS_PER_DAY

logger = logging.getLogger(__name__)


def assemble(articles: list[dict], summaries: list[dict], images: list[dict]):
    summary_map = {s["article_id"]: s for s in summaries}
    image_map   = {i["article_id"]: i for i in images}

    # Enforce daily paper ceiling before assembling cards
    articles = articles[:PAPERS_PER_DAY]

    cards = []
    for article in articles:
        article_id = hashlib.sha256(article["url"].encode()).hexdigest()[:8]
        s     = summary_map.get(article_id, {})
        image = image_map.get(article_id, {})

        # Flow diagram — cached in SQLite; None if generation fails
        text = article.get("_context_text") or article.get("full_text") or article.get("snippet", "")
        # Pass tags from the summary (curator may not have added them to article)
        article_with_tags = {**article, "tags": s.get("tags", article.get("tags", []))}
        flow = generate_flow(article_with_tags, text)

        cards.append({
            "id":                article_id,
            "headline":          s.get("headline", article["title"]),
            "tags":              s.get("tags", []),
            "research_theme":    article.get("research_theme", ""),
            "why_this_matters":  article.get("why_this_matters", ""),
            "source":            article["source"],
            "published":         article["published"],
            "source_url":        article["url"],
            "image_url":         image.get("image_url", ""),
            "image_is_fallback": image.get("is_fallback", True),
            "breakthrough":      article.get("breakthrough", False),
            "breakthrough_reason": article.get("breakthrough_reason"),
            "summary": {
                "hook":            s.get("hook", ""),
                "what_it_does":    s.get("what_it_does", ""),
                "key_idea":        s.get("key_idea", ""),
                "core_challenge":  s.get("core_challenge", ""),
                "key_assumption":  s.get("key_assumption", ""),
                "result":          s.get("result", ""),
                "what_it_enables": s.get("what_it_enables", ""),
                "open_source":     s.get("open_source", None),
                "tldr":            s.get("tldr", ""),
            },
            "flow": flow,
        })

    feed = {
        "generated_at":  datetime.now(timezone.utc).isoformat(),
        "article_count": len(cards),
        "articles":      cards,
    }

    out_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "feed.json")
    with open(out_path, "w") as f:
        json.dump(feed, f, indent=2)

    # Mark every published article as seen — only after successful write
    for article in articles:
        db.mark_seen(article)

    flow_count = sum(1 for c in cards if c["flow"] is not None)
    logger.info(f"[DeliveryAgent] {len(cards)} cards written, {flow_count} with flow diagrams")
    return flow_count
