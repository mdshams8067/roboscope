import json
import sqlite3
import hashlib
from datetime import datetime, timezone

DB_PATH = "roboscope.db"


def _conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with _conn() as conn:
        # seen_papers: deduplication table — tracks every paper ever published
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_papers (
                url_hash     TEXT PRIMARY KEY,
                title        TEXT NOT NULL,
                conference   TEXT NOT NULL,
                published    TEXT,
                added_at     TEXT NOT NULL
            )
        """)
        # articles: flow diagram cache — keyed by URL
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                url        TEXT PRIMARY KEY,
                title_hash TEXT NOT NULL,
                seen_at    TEXT NOT NULL,
                flow_json  TEXT
            )
        """)
        conn.commit()


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


# ── Deduplication ─────────────────────────────────────────────────────────────

def is_seen(url: str) -> bool:
    with _conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM seen_papers WHERE url_hash = ?", (_url_hash(url),)
        ).fetchone()
    return row is not None


def mark_seen(article: dict):
    """Call ONLY from delivery_agent after successful feed.json write."""
    with _conn() as conn:
        try:
            conn.execute(
                """INSERT INTO seen_papers (url_hash, title, conference, published, added_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    _url_hash(article["url"]),
                    article.get("title", ""),
                    article.get("conference", "unknown"),
                    article.get("published", ""),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # already seen — safe to ignore


def seen_count() -> int:
    with _conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM seen_papers").fetchone()[0]


# ── Flow diagram cache ────────────────────────────────────────────────────────

def get_flow(url: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT flow_json FROM articles WHERE url = ?", (url,)
        ).fetchone()
    if row and row[0]:
        return json.loads(row[0])
    return None


def store_flow(url: str, flow: dict):
    with _conn() as conn:
        conn.execute(
            """INSERT INTO articles (url, title_hash, seen_at, flow_json)
               VALUES (?, '', ?, ?)
               ON CONFLICT(url) DO UPDATE SET flow_json = excluded.flow_json""",
            (url, datetime.now(timezone.utc).isoformat(), json.dumps(flow)),
        )
        conn.commit()
