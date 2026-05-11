"""
RoboScope pipeline entry point.
Run with: python run.py
"""
import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

import core.database as db
from core.logger import RunLogger

from agents.source_watcher import fetch as fetch_articles
from agents.curator_agent import curate
from agents.summarizer_agent import summarize
from agents.image_agent import generate_images
from agents.delivery_agent import assemble
from core.config import PAPERS_PER_DAY


def main():
    logger = RunLogger()
    db.init_db()

    print("[RoboScope] Starting pipeline...")

    articles = fetch_articles()
    logger.log("SourceWatcher", "fetched", {"count": len(articles)})
    print(f"[SourceWatcher] {len(articles)} new articles")

    curated = curate(articles)[:PAPERS_PER_DAY]
    logger.log("CuratorAgent", "curated", {"count": len(curated)})
    print(f"[CuratorAgent] {len(curated)} articles selected")

    summaries = summarize(curated)
    logger.log("SummarizerAgent", "summarized", {"count": len(summaries)})
    print(f"[SummarizerAgent] {len(summaries)} summaries generated")

    images = generate_images(summaries, curated)
    fallbacks = sum(1 for i in images if i["is_fallback"])
    logger.log("ImageAgent", "generated", {"count": len(images), "fallbacks": fallbacks})
    print(f"[ImageAgent] {len(images)} images ({fallbacks} fallbacks)")

    flow_count = assemble(curated, summaries, images)
    logger.log("DeliveryAgent", "assembled", {"output": "feed.json", "flow_diagrams": flow_count})
    print(f"[FlowAgent] {flow_count}/{len(summaries)} flow diagrams generated")
    print("[DeliveryAgent] feed.json written")

    logger.finalize({"total_articles": len(curated), "fallback_images": fallbacks})
    print("[RoboScope] Pipeline complete.")


if __name__ == "__main__":
    main()
