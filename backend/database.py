"""
database.py — SQLite cache for resolved market data.

Schema:
  resolved_markets  — one row per resolved market, immutable once stored.
  calibration_cache — pre-computed calibration results, invalidated when new markets arrive.

Why SQLite: zero-ops, file-based, sufficient for thousands of markets with simple queries.
"""

import sqlite3
import json
import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "glass.db")

CREATE_RESOLVED_MARKETS = """
CREATE TABLE IF NOT EXISTS resolved_markets (
    topic_id          INTEGER PRIMARY KEY,
    batch_id          TEXT NOT NULL,
    topic_type        TEXT NOT NULL,       -- 'btc', 'eth', 'sol', 'gold'
    category          TEXT,
    end_time_utc      INTEGER,             -- Unix seconds
    resolved_at_utc   INTEGER,             -- Unix seconds (ended_at_utc)
    resolved_option_id INTEGER,            -- winning option_id
    total_amount_in_market INTEGER,        -- millisats
    outcomes_json     TEXT NOT NULL,       -- JSON array of {option_id, name, shares}
    implied_prob      REAL,               -- computed: shares[winner] / sum(shares)
    fetched_at        INTEGER             -- Unix seconds, when we cached this row
);
"""

CREATE_CALIBRATION_CACHE = """
CREATE TABLE IF NOT EXISTS calibration_cache (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id        TEXT NOT NULL,
    topic_type      TEXT NOT NULL,
    computed_at     INTEGER NOT NULL,      -- Unix seconds
    result_json     TEXT NOT NULL          -- full calibration result as JSON
);
"""

CREATE_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_rm_batch_type ON resolved_markets(batch_id, topic_type);",
    "CREATE INDEX IF NOT EXISTS idx_rm_implied_prob ON resolved_markets(implied_prob);",
    "CREATE INDEX IF NOT EXISTS idx_cc_batch_type ON calibration_cache(batch_id, topic_type, computed_at);",
]


def get_connection() -> sqlite3.Connection:
    """Return a thread-local SQLite connection with WAL mode for concurrent reads."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    """Create tables and indices if they don't exist."""
    with get_connection() as conn:
        conn.execute(CREATE_RESOLVED_MARKETS)
        conn.execute(CREATE_CALIBRATION_CACHE)
        for idx in CREATE_INDICES:
            conn.execute(idx)
    logger.info("Database initialised at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Resolved markets
# ---------------------------------------------------------------------------

def upsert_resolved_markets(markets: list[dict]) -> int:
    """
    Insert resolved markets, ignoring duplicates (topic_id is PK).
    Returns the count of newly inserted rows.
    """
    import time

    now = int(time.time())
    inserted = 0

    with get_connection() as conn:
        for m in markets:
            outcomes = m.get("outcomes", [])
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO resolved_markets
                    (topic_id, batch_id, topic_type, category, end_time_utc,
                     resolved_at_utc, resolved_option_id, total_amount_in_market,
                     outcomes_json, implied_prob, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        m["topic_id"],
                        m["batch_id"],
                        m.get("topic_type", "unknown"),
                        m.get("category"),
                        m.get("end_time_utc"),
                        m.get("ended_at_utc") or m.get("end_time_utc"),
                        m.get("resolved_option_id"),
                        m.get("total_amount_in_market"),
                        json.dumps(outcomes),
                        _compute_implied_prob_from_outcomes(outcomes, m.get("resolved_option_id")),
                        now,
                    ),
                )
                if conn.execute(
                    "SELECT changes()"
                ).fetchone()[0]:
                    inserted += 1
            except Exception as exc:
                logger.warning("Failed to upsert market %s: %s", m.get("topic_id"), exc)

    return inserted


def _compute_implied_prob_from_outcomes(
    outcomes: list[dict], resolved_option_id: Optional[int]
) -> Optional[float]:
    """
    Compute implied probability of the winning outcome from final share distribution.
    Returns None if data is missing or total shares is zero.
    """
    if not outcomes or resolved_option_id is None:
        return None

    total_shares = sum(o.get("shares", 0) for o in outcomes)
    if total_shares <= 0:
        return None

    winning = next(
        (o for o in outcomes if o.get("option_id") == resolved_option_id), None
    )
    if winning is None:
        return None

    return winning.get("shares", 0) / total_shares


def get_resolved_markets(
    batch_id: str,
    topic_type: Optional[str] = None,
    min_implied_prob: float = 0.0,
    max_implied_prob: float = 1.0,
) -> list[dict]:
    """Return resolved markets from cache, optionally filtered."""
    query = "SELECT * FROM resolved_markets WHERE batch_id = ?"
    params: list = [batch_id]

    if topic_type:
        query += " AND topic_type = ?"
        params.append(topic_type)

    query += " AND implied_prob IS NOT NULL AND implied_prob BETWEEN ? AND ?"
    params.extend([min_implied_prob, max_implied_prob])

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        d["outcomes"] = json.loads(d.get("outcomes_json") or "[]")
        result.append(d)
    return result


def count_cached_markets(batch_id: str, topic_type: Optional[str] = None) -> int:
    """How many resolved markets do we have cached for this batch?"""
    query = "SELECT COUNT(*) FROM resolved_markets WHERE batch_id = ?"
    params: list = [batch_id]
    if topic_type:
        query += " AND topic_type = ?"
        params.append(topic_type)
    with get_connection() as conn:
        return conn.execute(query, params).fetchone()[0]


def get_latest_topic_id(batch_id: str) -> Optional[int]:
    """Return the highest topic_id we've seen, for incremental fetching."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT MAX(topic_id) FROM resolved_markets WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Calibration cache
# ---------------------------------------------------------------------------

def save_calibration(batch_id: str, topic_type: str, result: dict) -> None:
    import time
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO calibration_cache (batch_id, topic_type, computed_at, result_json)
            VALUES (?, ?, ?, ?)
            """,
            (batch_id, topic_type, int(time.time()), json.dumps(result)),
        )


def get_latest_calibration(batch_id: str, topic_type: str) -> Optional[dict]:
    """Return most-recent cached calibration result, or None."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT result_json FROM calibration_cache
            WHERE batch_id = ? AND topic_type = ?
            ORDER BY computed_at DESC
            LIMIT 1
            """,
            (batch_id, topic_type),
        ).fetchone()
    return json.loads(row[0]) if row else None
