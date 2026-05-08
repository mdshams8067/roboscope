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
_PWC_API_URL   = "https://paperswithcode.com/api/v1/papers/?task=robot-manipulation&ordering=-published"

# Robotics relevance terms used to filter HF Daily Papers (covers all of ML)
_ROBOTICS_TERMS = [
    "robot", "manipulation", "locomotion", "humanoid", "reinforcement",
    "slam", "grasp", "legged", "actuator", "end-effector", "dexterous",
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

def _fetch_arxiv(max_results: int = 30) -> list[dict]:
    client = arxiv.Client()
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


def _fetch_rss(source_name: str, feed_url: str, source_key: str) -> list[dict]:
    feed = feedparser.parse(feed_url)
    articles = []
    for entry in feed.entries:
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
            continue

        url = getattr(entry, "link", "")
        if not url or not title:
            continue

        article = _make_article(url, title, "HuggingFace Papers", _parse_date(entry), snippet, "huggingface_daily_papers")
        logger.info(f"Queued [{article['_tier']}] huggingface_daily_papers: {title[:60]}")
        articles.append(article)
    return articles


def _fetch_pwc() -> list[dict]:
    """Papers With Code REST API — top 5 robot-manipulation papers by recency."""
    try:
        resp = requests.get(_PWC_API_URL, timeout=10, params={"limit": 5})
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except requests.RequestException as e:
        logger.warning(f"[SourceWatcher] Papers With Code fetch failed: {e}")
        return []

    articles = []
    for paper in results[:5]:
        url   = paper.get("url_abs") or paper.get("url_pdf", "")
        title = paper.get("title", "")
        snippet = (paper.get("abstract", "") or "")[:500]
        published = paper.get("published", _now_iso())
        if not url or not title:
            continue
        article = _make_article(url, title, "Papers With Code", published, snippet, "papers_with_code")
        logger.info(f"Queued [{article['_tier']}] papers_with_code: {title[:60]}")
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


# ── Public API ────────────────────────────────────────────────────────────────

def fetch() -> list[dict]:
    """
    Collects from all sources → deduplicates → returns clean article queue.
    To add a new source: write a _fetch_xxx() function and extend `raw` below.
    """
    raw = []
    raw.extend(_fetch_arxiv())
    for src in _RSS_SOURCES:
        raw.extend(_fetch_rss(src["name"], src["url"], src["key"]))
    raw.extend(_fetch_hf_papers())
    raw.extend(_fetch_pwc())
    raw.extend(_fetch_hn())
    return _deduplicate(raw)
