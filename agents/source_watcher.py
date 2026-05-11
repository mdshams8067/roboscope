"""
SourceWatcher — Agent 1
Fetches accepted papers from configured robotics and ML conferences.

Two access methods:
  - arxiv:       query cs.RO category, detect acceptance in comment field
  - openreview:  query OpenReview API for accepted papers by venue ID

Papers are drawn from the full historical pool (ARXIV_START_YEAR → now).
No recency filter — a paper from 2022 is as eligible as one from today.
"""
import datetime
import logging
import time

import arxiv
import openreview

import core.database as db
from core.config import (
    CONFERENCE_REGISTRY,
    ACTIVE_CONFERENCES,
    PAPERS_PER_CONFERENCE,
    ARXIV_START_YEAR,
    OPENREVIEW_YEARS,
    CREDIBLE_INSTITUTIONS,
    ARXIV_REQUIRES_INSTITUTION_MATCH,
)

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_credible(text: str) -> bool:
    if not ARXIV_REQUIRES_INSTITUTION_MATCH:
        return True
    text_lower = text.lower()
    return any(inst.lower() in text_lower for inst in CREDIBLE_INSTITUTIONS)


def _make_article(
    title: str,
    snippet: str,
    authors: list,
    url: str,
    conference: str,
    tier: int,
    pdf_url: str = "",
    published: str = "",
) -> dict:
    return {
        "title":      title,
        "snippet":    snippet[:500],
        "full_text":  snippet,
        "authors":    [str(a) for a in authors],
        "url":        url,
        "pdf_url":    pdf_url,
        "source":     conference,
        "conference": conference,
        "_source_key": f"conference_{conference.lower()}",
        "_tier":      tier,
        "published":  published,
    }


# ── arXiv fetcher ─────────────────────────────────────────────────────────────

def _fetch_arxiv(conference: str, config: dict) -> list[dict]:
    """
    Searches arXiv using the conference name directly in the comment field (co:)
    so only papers that explicitly declare acceptance are returned.
    Covers all relevant categories, not just cs.RO.
    """
    keywords = config["arxiv_keywords"]
    tier     = config["tier"]
    articles = []

    try:
        # Build query: match any keyword in the comment field across robotics/AI/ML categories
        co_terms  = " OR ".join(f'co:"{kw}"' for kw in keywords)
        cat_terms = "cat:cs.RO OR cat:cs.AI OR cat:cs.LG OR cat:cs.CV OR cat:cs.SY"
        query     = f"({co_terms}) AND ({cat_terms})"

        client = arxiv.Client(page_size=PAPERS_PER_CONFERENCE, delay_seconds=3, num_retries=2)
        search = arxiv.Search(
            query=query,
            max_results=PAPERS_PER_CONFERENCE * 5,
            sort_by=arxiv.SortCriterion.Relevance,
        )

        for paper in client.results(search):
            if len(articles) >= PAPERS_PER_CONFERENCE:
                break

            if paper.published.year < ARXIV_START_YEAR:
                continue

            author_str = " ".join(str(a) for a in paper.authors)
            if not _is_credible(f"{author_str} {paper.summary}"):
                logger.info(f"[{conference}] Dropped (no institution): {paper.title[:60]}")
                continue

            url = paper.entry_id
            if db.is_seen(url):
                logger.info(f"[{conference}] Already seen: {paper.title[:60]}")
                continue

            articles.append(_make_article(
                title=paper.title,
                snippet=paper.summary,
                authors=paper.authors,
                url=url,
                conference=conference,
                tier=tier,
                pdf_url=paper.pdf_url,
                published=paper.published.strftime("%Y-%m-%d"),
            ))
            logger.info(f"[{conference}] Queued: {paper.title[:60]}")
            time.sleep(0.5)

    except Exception as e:
        logger.warning(f"[{conference}] arXiv fetch failed: {e}")

    logger.info(f"[{conference}] arXiv: {len(articles)} new papers")
    return articles


# ── OpenReview fetcher ────────────────────────────────────────────────────────

def _fetch_openreview(conference: str, config: dict) -> list[dict]:
    """
    Fetches accepted papers from OpenReview across all years in OPENREVIEW_YEARS.
    No API key required for public accepted papers.
    """
    tier     = config["tier"]
    articles = []

    try:
        client = openreview.api.OpenReviewClient(baseurl="https://api2.openreview.net")
    except Exception as e:
        logger.warning(f"[{conference}] OpenReview client init failed: {e}")
        return []

    for year in reversed(OPENREVIEW_YEARS):  # most recent first
        if len(articles) >= PAPERS_PER_CONFERENCE:
            break

        venue_id = config["venue_id"].replace("{year}", str(year))
        try:
            submissions = client.get_all_notes(
                invitation=f"{venue_id}/-/Submission",
                details="directReplies",
            )
        except Exception as e:
            logger.info(f"[{conference} {year}] Skipped: {e}")
            continue

        for paper in submissions:
            if len(articles) >= PAPERS_PER_CONFERENCE:
                break

            replies = paper.details.get("directReplies", [])
            accepted = any(
                "Accept" in str(r.get("content", {}).get("decision", ""))
                for r in replies
            )
            if not accepted:
                continue

            content  = paper.content
            title    = content.get("title",    {}).get("value", "")
            abstract = content.get("abstract", {}).get("value", "")
            authors  = content.get("authors",  {}).get("value", [])
            url      = f"https://openreview.net/forum?id={paper.id}"
            pdf_url  = f"https://openreview.net/pdf?id={paper.id}"

            if not title:
                continue

            author_str = " ".join(authors)
            if not _is_credible(f"{author_str} {abstract}"):
                logger.info(f"[{conference}] Dropped (no institution): {title[:60]}")
                continue

            if db.is_seen(url):
                logger.info(f"[{conference}] Already seen: {title[:60]}")
                continue

            # Use actual timestamp from OpenReview if available, fall back to year
            ts = getattr(paper, "pdate", None) or getattr(paper, "cdate", None)
            if ts:
                pub_date = datetime.datetime.fromtimestamp(
                    ts / 1000, tz=datetime.timezone.utc
                ).strftime("%Y-%m-%d")
            else:
                pub_date = str(year)

            articles.append(_make_article(
                title=title,
                snippet=abstract,
                authors=authors,
                url=url,
                conference=conference,
                tier=tier,
                pdf_url=pdf_url,
                published=pub_date,
            ))
            logger.info(f"[{conference} {year}] Queued: {title[:60]}")

    logger.info(f"[{conference}] OpenReview: {len(articles)} new papers")
    return articles


# ── Public API ────────────────────────────────────────────────────────────────

def fetch() -> list[dict]:
    """
    Fetches unseen accepted papers from all ACTIVE_CONFERENCES.
    Returns a raw article queue for CuratorAgent.
    One conference failing never stops the others.
    """
    db.init_db()
    raw = []

    logger.info(f"[SourceWatcher] Active conferences: {ACTIVE_CONFERENCES}")

    for conf in ACTIVE_CONFERENCES:
        if conf not in CONFERENCE_REGISTRY:
            logger.warning(f"[SourceWatcher] Unknown conference: {conf} — skipping")
            continue

        config = CONFERENCE_REGISTRY[conf]
        if config["access"] == "arxiv":
            papers = _fetch_arxiv(conf, config)
        elif config["access"] == "openreview":
            papers = _fetch_openreview(conf, config)
        else:
            logger.warning(f"[SourceWatcher] Unknown access method for {conf}")
            continue

        raw.extend(papers)
        logger.info(f"[SourceWatcher] Queue after {conf}: {len(raw)}")

    logger.info(f"[SourceWatcher] Total unseen papers: {len(raw)}")
    return raw
