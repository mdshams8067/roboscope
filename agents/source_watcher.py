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
    MIN_NEW_PER_CONFERENCE,
    ARXIV_START_YEAR,
    OPENREVIEW_YEARS,
    OPENREVIEW_USERNAME,
    OPENREVIEW_PASSWORD,
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

def _arxiv_pass(
    conference: str,
    query: str,
    sort_by: arxiv.SortCriterion,
    max_results: int,
    tier: int,
    articles: list,
    seen_urls: set,
) -> None:
    """Single arXiv search pass; appends new unseen papers into articles in-place."""
    try:
        client = arxiv.Client(page_size=100, delay_seconds=3, num_retries=2)
        search = arxiv.Search(query=query, max_results=max_results, sort_by=sort_by)

        for paper in client.results(search):
            if len(articles) >= PAPERS_PER_CONFERENCE:
                break
            if paper.published.year < ARXIV_START_YEAR:
                continue

            url = paper.entry_id
            if url in seen_urls:
                continue
            seen_urls.add(url)

            author_str = " ".join(str(a) for a in paper.authors)
            if not _is_credible(f"{author_str} {paper.summary}"):
                logger.info(f"[{conference}] Dropped (no institution): {paper.title[:60]}")
                continue
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


def _fetch_arxiv(conference: str, config: dict) -> list[dict]:
    """
    Searches arXiv using the conference name in the comment field (co:).
    Pass 1: relevance-sorted, moderate depth.
    Pass 2: date-sorted, deeper scan — only runs if pass 1 yields < MIN_NEW_PER_CONFERENCE.
    """
    keywords  = config["arxiv_keywords"]
    tier      = config["tier"]
    articles: list[dict] = []
    seen_urls: set[str]  = set()

    co_terms  = " OR ".join(f'co:"{kw}"' for kw in keywords)
    cat_terms = "cat:cs.RO OR cat:cs.AI OR cat:cs.LG OR cat:cs.CV OR cat:cs.SY"
    query     = f"({co_terms}) AND ({cat_terms})"

    _arxiv_pass(conference, query, arxiv.SortCriterion.Relevance,
                PAPERS_PER_CONFERENCE * 5, tier, articles, seen_urls)

    if len(articles) < MIN_NEW_PER_CONFERENCE:
        logger.info(f"[{conference}] Pass 1 found {len(articles)} — expanding to date-sorted deep scan")
        _arxiv_pass(conference, query, arxiv.SortCriterion.SubmittedDate,
                    PAPERS_PER_CONFERENCE * 20, tier, articles, seen_urls)

    if len(articles) < MIN_NEW_PER_CONFERENCE:
        logger.warning(f"[{conference}] Only {len(articles)} new papers after deep scan — pool may be exhausted")

    logger.info(f"[{conference}] arXiv: {len(articles)} new papers")
    return articles


# ── OpenReview fetcher ────────────────────────────────────────────────────────

def _process_openreview_note(
    paper, year: int, conference: str, tier: int, articles: list
) -> bool:
    """Parse one OpenReview note and append to articles if new. Returns True if added."""
    content  = paper.content
    title    = content.get("title",    {}).get("value", "")
    abstract = content.get("abstract", {}).get("value", "")
    authors  = content.get("authors",  {}).get("value", [])
    url     = f"https://openreview.net/forum?id={paper.id}"
    pdf_url = ""  # OpenReview PDF endpoint requires auth; abstract is sufficient

    if not title:
        return False

    author_str = " ".join(str(a) for a in authors)
    if not _is_credible(f"{author_str} {abstract}"):
        logger.info(f"[{conference}] Dropped (no institution): {title[:60]}")
        return False

    if db.is_seen(url):
        logger.info(f"[{conference}] Already seen: {title[:60]}")
        return False

    ts = getattr(paper, "pdate", None) or getattr(paper, "cdate", None)
    pub_date = (
        datetime.datetime.fromtimestamp(ts / 1000, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
        if ts else str(year)
    )

    articles.append(_make_article(
        title=title, snippet=abstract, authors=authors, url=url,
        conference=conference, tier=tier, pdf_url=pdf_url, published=pub_date,
    ))
    logger.info(f"[{conference} {year}] Queued: {title[:60]}")
    return True


def _fetch_openreview(conference: str, config: dict) -> list[dict]:
    """
    Fetches accepted papers from OpenReview across all years in OPENREVIEW_YEARS.

    Primary method: query by venueid — accepted papers carry this field directly.
    This is the only reliable approach for conferences like RSS that do not publish
    explicit decision notes (which the fallback submission+decision method requires).
    Fallback: filter all submissions by "Accept" in directReplies decision field.
    """
    tier     = config["tier"]
    articles: list[dict] = []

    try:
        client = openreview.api.OpenReviewClient(
            baseurl="https://api2.openreview.net",
            username=OPENREVIEW_USERNAME or None,
            password=OPENREVIEW_PASSWORD or None,
        )
    except Exception as e:
        logger.warning(f"[{conference}] OpenReview client init failed: {e}")
        return []

    for year in reversed(OPENREVIEW_YEARS):  # most recent first
        if len(articles) >= PAPERS_PER_CONFERENCE:
            break

        venue_id = config["venue_id"].replace("{year}", str(year))
        accepted_notes = []

        # Primary: query accepted papers directly by venue ID (works for RSS and others
        # that don't publish explicit decision notes)
        try:
            accepted_notes = client.get_all_notes(content={"venueid": venue_id})
            if accepted_notes:
                logger.info(f"[{conference} {year}] venueid query: {len(accepted_notes)} accepted papers")
        except Exception as e:
            logger.warning(f"[{conference} {year}] venueid query failed: {e}")

        # Fallback: filter submissions by "Accept" in decision notes (CoRL, ICLR, etc.)
        if not accepted_notes:
            try:
                submissions = client.get_all_notes(
                    invitation=f"{venue_id}/-/Submission",
                    details="directReplies",
                )
                for paper in submissions:
                    replies = paper.details.get("directReplies", [])
                    if any(
                        "Accept" in str(r.get("content", {}).get("decision", ""))
                        for r in replies
                    ):
                        accepted_notes.append(paper)
                logger.info(f"[{conference} {year}] submission filter: {len(accepted_notes)} accepted papers")
            except Exception as e:
                logger.warning(f"[{conference} {year}] submission query failed: {e}")
                time.sleep(2)
                continue

        time.sleep(1)  # avoid triggering OpenReview rate limiting between years

        for paper in accepted_notes:
            if len(articles) >= PAPERS_PER_CONFERENCE:
                break
            _process_openreview_note(paper, year, conference, tier, articles)

    if len(articles) < MIN_NEW_PER_CONFERENCE:
        logger.warning(f"[{conference}] Only {len(articles)} new papers — pool may be exhausted")

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
