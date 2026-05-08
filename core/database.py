import json
import sqlite3
import hashlib
from datetime import datetime, timezone

DB_PATH = "roboscope.db"


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                url        TEXT PRIMARY KEY,
                title_hash TEXT NOT NULL,
                seen_at    TEXT NOT NULL
            )
        """)
        # Add flow_json column if it doesn't exist yet (idempotent migration)
        try:
            conn.execute("ALTER TABLE articles ADD COLUMN flow_json TEXT")
        except Exception:
            pass  # column already exists
        conn.commit()


def _hash(title: str) -> str:
    return hashlib.sha256(title.lower().strip().encode()).hexdigest()[:16]


def is_seen(url: str, title: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT 1 FROM articles WHERE url = ? OR title_hash = ?",
            (url, _hash(title)),
        ).fetchone()
    return row is not None


def mark_seen(url: str, title: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO articles (url, title_hash, seen_at) VALUES (?, ?, ?)",
            (url, _hash(title), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()


def seen_count() -> int:
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]


def get_flow(url: str) -> dict | None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT flow_json FROM articles WHERE url = ?", (url,)
        ).fetchone()
    if row and row[0]:
        return json.loads(row[0])
    return None


def store_flow(url: str, flow: dict):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE articles SET flow_json = ? WHERE url = ?",
            (json.dumps(flow), url),
        )
        conn.commit()
