"""
role_brief_store.py
--------------------
SQLite table holding one researched "brief" per dropdown job title. Plain
sqlite3 (stdlib) — no new dependency, survives restarts, and a one-file DB is
plenty for ~85 rows written weekly. Every call opens its own short-lived
connection, so it is safe to call from worker threads (asyncio.to_thread).
"""

import json
import sqlite3
from pathlib import Path
from typing import Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS role_briefs (
    slug         TEXT PRIMARY KEY,
    brief_json   TEXT,            -- validated brief; NULL until the first successful refresh
    sources_json TEXT,            -- [{url, title}] the brief was built from, for auditing
    refreshed_at REAL,            -- epoch seconds of the last SUCCESSFUL refresh
    attempted_at REAL,            -- epoch seconds of the last attempt (success or not)
    last_error   TEXT
)
"""


class RoleBriefStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self._ready = False

    def _conn(self) -> sqlite3.Connection:
        # The schema is created on first use, so no code path depends on init()
        # having been called first (tests, scripts, a deleted DB file).
        if not self._ready:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.path, timeout=10) as setup:
                setup.execute(_SCHEMA)
            self._ready = True
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        self._conn().close()

    def get(self, slug: str) -> Optional[dict]:
        """The stored row as a dict (brief decoded), or None if never attempted."""
        with self._conn() as c:
            row = c.execute("SELECT * FROM role_briefs WHERE slug = ?", (slug,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["brief"] = json.loads(d.pop("brief_json")) if d["brief_json"] else None
        d["sources"] = json.loads(d.pop("sources_json")) if d["sources_json"] else []
        return d

    def claim(self, slug: str, now: float, min_gap_seconds: float) -> bool:
        """
        Atomically mark a refresh attempt. Returns False if another attempt
        started within `min_gap_seconds` — this stops a failing role being
        retried every scheduler tick and keeps two processes from researching
        the same role at once.
        """
        with self._conn() as c:
            c.execute("INSERT OR IGNORE INTO role_briefs (slug) VALUES (?)", (slug,))
            cur = c.execute(
                "UPDATE role_briefs SET attempted_at = ? "
                "WHERE slug = ? AND (attempted_at IS NULL OR attempted_at < ?)",
                (now, slug, now - min_gap_seconds),
            )
            return cur.rowcount == 1

    def save_brief(self, slug: str, brief: dict, sources: list[dict], now: float) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO role_briefs (slug, brief_json, sources_json, refreshed_at, last_error) "
                "VALUES (?, ?, ?, ?, NULL) "
                "ON CONFLICT(slug) DO UPDATE SET brief_json = excluded.brief_json, "
                "sources_json = excluded.sources_json, refreshed_at = excluded.refreshed_at, last_error = NULL",
                (slug, json.dumps(brief), json.dumps(sources), now),
            )

    def record_failure(self, slug: str, error: str) -> None:
        """Keeps any previous brief in place — a bad week never overwrites a good brief."""
        with self._conn() as c:
            c.execute(
                "INSERT INTO role_briefs (slug, last_error) VALUES (?, ?) "
                "ON CONFLICT(slug) DO UPDATE SET last_error = excluded.last_error",
                (slug, error[:500]),
            )

    def status(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT slug, refreshed_at, attempted_at, last_error, "
                "json_extract(brief_json, '$.confidence') AS confidence FROM role_briefs"
            ).fetchall()
        return [dict(r) for r in rows]
