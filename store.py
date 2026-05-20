"""
StreamPulse slim store — KPI metrics + ingestion logs only.

NOTE: Extracted from OmniIntelOS pg_store.py with only the functions
this project needs. Chat, OCR, voice, OAuth, user functions are removed.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import settings
from core.logger import get_logger

log = get_logger(__name__)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS kpi_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT NOT NULL,
    category TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT,
    source TEXT,
    confidence REAL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kpi_cat ON kpi_metrics(category);
CREATE INDEX IF NOT EXISTS idx_kpi_period ON kpi_metrics(period);

CREATE TABLE IF NOT EXISTS ingestion_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    records INTEGER DEFAULT 0,
    error TEXT,
    payload TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


_DB_PATH = Path("streampulse.db")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    """Initialize tables (idempotent)."""
    with _conn() as c:
        c.executescript(_SCHEMA)


def store_kpi_metrics(records: List[Dict[str, Any]]) -> int:
    """Persist a batch of KPI records. Returns count inserted."""
    init_db()
    count = 0
    now = datetime.utcnow().isoformat()
    with _conn() as c:
        for r in records:
            try:
                c.execute(
                    """
                    INSERT INTO kpi_metrics
                      (period, category, metric, value, unit, source, confidence, created_at)
                    VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (
                        r.get("period", ""), r.get("category", ""), r.get("metric", ""),
                        float(r.get("value", 0) or 0), r.get("unit"), r.get("source"),
                        float(r.get("confidence", 1.0) or 1.0), now,
                    ),
                )
                count += 1
            except Exception as e:
                log.warning("skip record %s: %s", r.get("metric"), e)
    return count


def get_kpi_metrics(
    category: Optional[str] = None,
    metric_filter: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """Fetch KPI records, optionally filtered."""
    init_db()
    sql = "SELECT * FROM kpi_metrics"
    where: List[str] = []
    params: List[Any] = []
    if category:
        where.append("category = ?"); params.append(category)
    if metric_filter:
        where.append("metric LIKE ?"); params.append(f"%{metric_filter}%")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ?"; params.append(limit)
    with _conn() as c:
        rows = c.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def log_data_ingestion(source: str, status: str, records: int = 0,
                       error: Optional[str] = None, payload: Optional[Any] = None) -> int:
    """Log an ingestion event. Returns the ID."""
    init_db()
    now = datetime.utcnow().isoformat()
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO ingestion_log (source, status, records, error, payload, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (source, status, records, error,
             json.dumps(payload)[:5000] if payload else None, now, now),
        )
        return cur.lastrowid or 0


def update_ingestion_log(log_id: int, status: str, records: int = 0,
                         error: Optional[str] = None) -> None:
    init_db()
    now = datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute(
            "UPDATE ingestion_log SET status=?, records=?, error=?, updated_at=? WHERE id=?",
            (status, records, error, now, log_id),
        )


def get_pipeline_history(limit: int = 100) -> List[Dict[str, Any]]:
    init_db()
    with _conn() as c:
        rows = c.execute("SELECT * FROM ingestion_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
