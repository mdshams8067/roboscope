"""
SourceWatcher — Agent 1
Fetches raw articles from all configured sources, applies institution and tier
filters on arXiv, deduplicates against SQLite, and returns a clean article queue.
"""
import logging
import re
from datetime import datetime, timezone
from time import mktime

import arxiv
import feedparser
import requests

import core.database as db
from core.config import (
    HN_KEYWORDS,
    CREDIBLE_INSTITUTIONS, ARXIV_REQUIRES_INSTITUTION_MATCH,
    SOURCE_TIERS, TIER1_CONFERENCES,
)

logger = logging.getLogger(__name__)

# ── Source registry — every RSS/API source with its tier key ──────────────────
# Defined here (not config.py) so source_watcher owns its own source list.

_RSS_SOURCES = [
    # Tier 1
    {"name": "Google DeepMind Blog",    "url": "https://deepmind.google/blog/rss.xml",                            "key": "google_deepmind_blog"},
    # Tier 2
    {"name": "IEEE Spectrum",           "url": "https://spectrum.ieee.org/feeds/robotics",                        "key": "ieee_spectrum"},
    {"name": "The Robot Report",        "url": "https://www.therobotreport.com/feed/",                            "key": "the_robot_report"},
    {"name": "MIT News",                "url": "https://news.mit.edu/rss/topic/robotics-mit",                     "key": "mit_news"},
    {"name": "TechCrunch Robotics",     "url": "https://techcrunch.com/tag/robotics/feed/",                       "key": "techcrunch_robotics"},
    {"name": "New Atlas Robotics",      "url": "https://feeds.feedburner.com/NewAtlasRobotics",                   "key": "new_atlas_robotics"},
    {"name": "ScienceDaily Robotics",   "url": "https://www.sciencedaily.com/rss/computers_math/robotics.xml",    "key": "sciencedaily_robotics"},
    {"name": "NVIDIA Isaac Blog",       "url": "https://blogs.nvidia.com/blog/tag/robotics/feed/",                "key": "nvidia_isaac_blog"},
    {"name": "Boston Dynamics Blog",    "url": "https://bostondynamics.com/blog/feed/",                           "key": "boston_dynamics_blog"},
]

_HF_PAPERS_RSS = "https://papers.takara.ai/api/feed"

# Robotics relevance terms used to filter HF Daily Papers (covers all of ML)
_ROBOTICS_TERMS = [
    # Sub-fields and hardware
    "robot", "humanoid", "bipedal", "legged", "quadruped", "wheeled",
    "drone", "uav", "quadrotor", "aerial", "exoskeleton", "prosthetic",
    "surgical robot", "soft robot", "gripper", "actuator", "end-effector",
    # Tasks and skills
    "manipulation", "grasping", "grasp", "dexterous", "locomotion",
    "navigation", "trajectory", "planning", "teleoperation",
    # Sensing and perception
    "tactile", "haptic", "lidar", "point cloud", "pose estimation",
    "slam",
    # Learning paradigms
    "imitation learning", "reinforcement", "sim-to-real", "policy",
    "embodied", "physical intelligence", "world model",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_article(url: str, title: str, source: str, published: str,
                  snippet: str, source_key: str) -> dict:
    """Single factory for all article dicts. Internal tier/key fields use _ prefix."""
    return {
        "url":         url,
        "title":       title,
        "source":      source,
        "published":   published,
        "snippet":     snippet,
        "full_text":   None,
        "_source_key": source_key,
        "_tier":       SOURCE_TIERS.get(source_key, 2),
    }


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()


def _parse_date(entry) -> str:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc).isoformat()
    return _now_iso()


# ── Layer 1: arXiv credibility + conference detection ─────────────────────────

def is_credible_arxiv(paper) -> bool:
    """Institution allowlist check. RSS sources skip this entirely."""
    if not ARXIV_REQUIRES_INSTITUTION_MATCH:
        return True
    text = " ".join([str(paper.authors), paper.summary]).lower()
    return any(inst.lower() in text for inst in CREDIBLE_INSTITUTIONS)


def detect_conference_acceptance(paper) -> str | None:
    """
    Checks the arXiv comment field for conference acceptance.
    Authors upload accepted papers to arXiv and note acceptance in comments,
    e.g. "Accepted to ICRA 2026". Returns the matched conference name or None.
    We never scrape conference websites — this is the correct detection method.
    """
    comment = getattr(paper, "comment", "") or ""
    for conf in TIER1_CONFERENCES:
        if conf.lower() in comment.lower():
            return conf
    return None


# ── Source fetchers ───────────────────────────────────────────────────────────

def _fetch_arxiv(max_results: int = 20) -> list[dict]:
    client = arxiv.Client(page_size=max_results, delay_seconds=3, num_retries=2)
    search = arxiv.Search(
        query="cat:cs.RO",
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
    )
    articles = []
    for result in client.results(search):
        if not is_credible_arxiv(result):
            logger.info(f"Dropped (no institution match): {result.title}")
            continue

        conference = detect_conference_acceptance(result)
        source_key = "arxiv_conference_accepted" if conference else "arxiv_preprint"

        if conference:
            logger.info(f"Conference-accepted ({conference}): {result.title[:60]}")

        article = _make_article(
            url=result.entry_id,
            title=result.title,
            source="arXiv",
            published=result.published.isoformat(),
            snippet=result.summary[:500],
            source_key=source_key,
        )
        logger.info(f"Queued [{article['_tier']}] {source_key}: {result.title[:60]}")
        articles.append(article)
    return articles


def _fetch_rss(source_name: str, feed_url: str, source_key: str, max_entries: int = 5) -> list[dict]:
    feed = feedparser.parse(feed_url)
    articles = []
    for entry in feed.entries[:max_entries]:
        url     = getattr(entry, "link", "")
        title   = getattr(entry, "title", "Untitled")
        snippet = _strip_html(getattr(entry, "summary", "") or getattr(entry, "description", ""))[:500]
        if not url or not title:
            continue
        article = _make_article(url, title, source_name, _parse_date(entry), snippet, source_key)
        logger.info(f"Queued [{article['_tier']}] {source_key}: {title[:60]}")
        articles.append(article)
    return articles


def _fetch_hf_papers() -> list[dict]:
    """
    HuggingFace Daily Papers via unofficial RSS (papers.takara.ai).
    Covers all of ML — we filter to robotics-relevant entries only.
    """
    feed = feedparser.parse(_HF_PAPERS_RSS)
    articles = []
    for entry in feed.entries:
        title   = getattr(entry, "title", "")
        snippet = _strip_html(getattr(entry, "summary", ""))[:500]
        combined = (title + " " + snippet).lower()

        # Keep only if robotics-related
        if not any(term in combined for term in _ROBOTICS_TERMS):
            logger.debug(f"HF dropped (no term match): {title[:80]}")
            continue

        url = getattr(entry, "link", "")
        if not url or not title:
            continue

        article = _make_article(url, title, "HuggingFace Papers", _parse_date(entry), snippet, "huggingface_daily_papers")
        logger.info(f"Queued [{article['_tier']}] huggingface_daily_papers: {title[:60]}")
        articles.append(article)
    return articles



def _fetch_hn() -> list[dict]:
    keywords = " ".join(HN_KEYWORDS)
    url = f"http://hn.algolia.com/api/v1/search?query={keywords}&tags=story&hitsPerPage=20"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
    except requests.RequestException as e:
        logger.warning(f"[SourceWatcher] HN fetch failed: {e}")
        return []

    articles = []
    for hit in hits:
        hn_url  = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        title   = hit.get("title", "")
        published = hit.get("created_at", _now_iso())
        if not title:
            continue
        article = _make_article(hn_url, title, "HN", published, title, "hacker_news")
        logger.info(f"Queued [{article['_tier']}] hacker_news: {title[:60]}")
        articles.append(article)
    return articles


# ── Deduplication ─────────────────────────────────────────────────────────────

def _deduplicate(articles: list[dict]) -> list[dict]:
    seen_urls = set()
    new_articles = []
    for article in articles:
        url, title = article["url"], article["title"]
        if url in seen_urls or db.is_seen(url, title):
            continue
        db.mark_seen(url, title)
        seen_urls.add(url)
        new_articles.append(article)
    return new_articles


# Research sources get a higher cap — this is a research portal.
# News/editorial sources are capped lower to prevent crowding out papers.
_MAX_ARXIV_PER_RUN   = 10   # arXiv cs.RO papers
_MAX_HF_PER_RUN      = 3    # HuggingFace Daily Papers (already filtered to robotics)
_MAX_NEWS_PER_SOURCE = 2    # IEEE Spectrum, TechCrunch, etc.


# ── Public API ────────────────────────────────────────────────────────────────

def fetch(curator_limit: int = 20) -> list[dict]:
    """
    Collects from all sources → deduplicates → per-source cap → tier sort → top N.

    Per-source cap ensures every source gets representation even when arXiv or
    HuggingFace Papers have many matching articles. Tier sort within the capped
    pool still surfaces the highest-quality articles across all sources.
    """
    from collections import defaultdict

    raw = []
    raw.extend(_fetch_arxiv())
    for src in _RSS_SOURCES:
        raw.extend(_fetch_rss(src["name"], src["url"], src["key"]))
    raw.extend(_fetch_hf_papers())
    raw.extend(_fetch_hn())

    deduped = _deduplicate(raw)
    logger.info(f"[SourceWatcher] {len(deduped)} unique articles after dedup")

    # Group by human-readable source name so "arXiv" conference-accepted and
    # preprints share one budget, not two separate ones.
    by_source: dict[str, list] = defaultdict(list)
    for article in deduped:
        by_source[article["source"]].append(article)

    # Within each source prefer higher tier (lower number), then cap.
    _source_cap = {"arXiv": _MAX_ARXIV_PER_RUN, "HuggingFace Papers": _MAX_HF_PER_RUN}
    capped = []
    for source_name, articles in by_source.items():
        cap = _source_cap.get(source_name, _MAX_NEWS_PER_SOURCE)
        articles.sort(key=lambda a: a.get("_tier", 2))
        kept = articles[:cap]
        capped.extend(kept)
        if len(articles) > cap:
            logger.info(f"[SourceWatcher] {source_name}: capped at {cap}/{len(articles)}")

    # Final tier sort across all sources, take top N
    capped.sort(key=lambda a: a.get("_tier", 2))
    selected = capped[:curator_limit]

    source_counts: dict[str, int] = defaultdict(int)
    for a in selected:
        source_counts[a["source"]] += 1
    logger.info(f"[SourceWatcher] {len(selected)} articles selected: {dict(source_counts)}")
    return selected
