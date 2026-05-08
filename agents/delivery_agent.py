"""
DeliveryAgent — Agent 5
Joins curated articles, summaries, and images into a single feed.json file
consumed by the React frontend.
"""
import hashlib
import json
from datetime import datetime, timezone


def assemble(articles: list[dict], summaries: list[dict], images: list[dict]):
    # STUB — basic implementation, you can enhance this
    summary_map = {s["article_id"]: s for s in summaries}
    image_map   = {i["article_id"]: i for i in images}

    cards = []
    for article in articles:
        article_id = hashlib.sha256(article["url"].encode()).hexdigest()[:8]
        summary = summary_map.get(article_id, {})
        image   = image_map.get(article_id, {})

        cards.append({
            "id":               article_id,
            "headline":         summary.get("headline", article["title"]),
            "digest":           summary.get("digest", ""),
            "tags":             summary.get("tags", []),
            "source":           article["source"],
            "published":        article["published"],
            "source_url":       article["url"],
            "image_url":        image.get("image_url", ""),
            "image_is_fallback": image.get("is_fallback", True),
            "breakthrough":     article.get("breakthrough", False),
            "breakthrough_reason": article.get("breakthrough_reason"),
        })

    feed = {
        "generated_at":  datetime.now(timezone.utc).isoformat(),
        "article_count": len(cards),
        "articles":      cards,
    }

    with open("feed.json", "w") as f:
        json.dump(feed, f, indent=2)
