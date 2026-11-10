"""SQLite manifest: one row per item with its status, so every phase is resumable.

Statuses move forward: pending -> extracted -> transformed. A failure sets `failed`
and keeps the error text; `--resume` retries failed rows and skips finished ones.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,            -- artwork | writing | archive
    category TEXT,                 -- artwork category (painting, drawing, ...)
    year INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    listing TEXT,                  -- JSON with the metadata taken from the listing
    flags TEXT,                    -- JSON list of sub-pages the site announces
    attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS items_type_status ON items(type, status);
CREATE TABLE IF NOT EXISTS progress (
    key TEXT PRIMARY KEY,          -- e.g. "discover:artwork:1907"
    value TEXT,
    updated_at TEXT
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Manifest:
    """Tiny wrapper over sqlite3 with the handful of queries the pipeline needs."""

    def __init__(self, path: Path = config.INDEX_DIR / "manifest.sqlite") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    # --- items ----------------------------------------------------------------
    def upsert_item(self, item_id: str, item_type: str, year: int | None,
                    listing: dict[str, Any], category: str | None = None) -> None:
        """Insert a discovered item; an existing row keeps its status and flags."""
        self.conn.execute(
            """INSERT INTO items (id, type, category, year, listing, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET listing = excluded.listing,
                   category = COALESCE(excluded.category, items.category),
                   year = excluded.year, updated_at = excluded.updated_at""",
            (item_id, item_type, category, year, json.dumps(listing, ensure_ascii=False), now_iso()),
        )

    def set_flags(self, item_id: str, flags: list[str]) -> None:
        self.conn.execute("UPDATE items SET flags = ?, updated_at = ? WHERE id = ?",
                          (json.dumps(flags), now_iso(), item_id))

    def set_status(self, item_id: str, status: str, error: str | None = None) -> None:
        self.conn.execute(
            """UPDATE items SET status = ?, error = ?, updated_at = ?,
               attempts = attempts + CASE WHEN ? = 'failed' THEN 1 ELSE 0 END WHERE id = ?""",
            (status, error, now_iso(), status, item_id))

    def select(self, item_type: str, years: list[int] | None = None, limit: int | None = None,
               statuses: list[str] | None = None, categories: list[str] | None = None) -> list[dict[str, Any]]:
        """Items of one type ordered by year and id, optionally filtered."""
        sql, args = "SELECT * FROM items WHERE type = ?", [item_type]
        if years:
            sql += f" AND year IN ({','.join('?' * len(years))})"; args += years
        if categories:
            sql += f" AND category IN ({','.join('?' * len(categories))})"; args += categories
        if statuses:
            sql += f" AND status IN ({','.join('?' * len(statuses))})"; args += statuses
        sql += " ORDER BY year, id"
        if limit:
            sql += " LIMIT ?"; args.append(limit)
        return [self._row_to_dict(r) for r in self.conn.execute(sql, args)]

    def get(self, item_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["listing"] = json.loads(d["listing"]) if d["listing"] else {}
        d["flags"] = json.loads(d["flags"]) if d["flags"] else None
        return d

    def counts(self) -> list[dict[str, Any]]:
        """Rows per (type, status) for the final summary."""
        rows = self.conn.execute(
            "SELECT type, status, COUNT(*) AS n FROM items GROUP BY type, status ORDER BY type, status")
        return [dict(r) for r in rows]

    def failures(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id, type, attempts, error FROM items WHERE status = 'failed' ORDER BY updated_at DESC LIMIT ?",
            (limit,))
        return [dict(r) for r in rows]

    # --- progress of listing-level work ---------------------------------------
    def is_done(self, key: str) -> bool:
        return self.conn.execute("SELECT 1 FROM progress WHERE key = ?", (key,)).fetchone() is not None

    def mark_done(self, key: str, value: str = "") -> None:
        self.conn.execute("INSERT OR REPLACE INTO progress (key, value, updated_at) VALUES (?, ?, ?)",
                          (key, value, now_iso()))

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()

    def __enter__(self) -> "Manifest":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
