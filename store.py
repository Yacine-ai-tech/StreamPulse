"""
StreamPulse slim store — KPI metrics + ingestion logs only.

Dual backend, selected at import time:
  - PostgreSQL when POSTGRES_URL is set (production — durable across restarts/deploys).
    Tables are prefixed ``sp_`` because the database is shared with other portfolio
    services that own the unprefixed ``kpi_metrics`` seed data.
  - SQLite fallback otherwise (zero-infrastructure local runs).

Chat, OCR, voice, OAuth, user functions are intentionally out of scope.
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

_PG_URL = (getattr(settings, "POSTGRES_URL", "") or "").strip()
_PG = False
if _PG_URL:
    try:
        import psycopg
        from psycopg.rows import dict_row
        _PG = True
    except ImportError:
        log.warning("POSTGRES_URL set but psycopg not installed — falling back to SQLite")

_T_KPI = "sp_kpi_metrics" if _PG else "kpi_metrics"
_T_LOG = "sp_ingestion_log" if _PG else "ingestion_log"

_SCHEMA_SQLITE = """
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

_SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS sp_kpi_metrics (
    id BIGSERIAL PRIMARY KEY,
    period TEXT NOT NULL,
    category TEXT NOT NULL,
    metric TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit TEXT,
    source TEXT,
    confidence DOUBLE PRECISION,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sp_kpi_cat ON sp_kpi_metrics(category);
CREATE INDEX IF NOT EXISTS idx_sp_kpi_period ON sp_kpi_metrics(period);

CREATE TABLE IF NOT EXISTS sp_ingestion_log (
    id BIGSERIAL PRIMARY KEY,
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
_initialized = False


def _conn():
    if _PG:
        return psycopg.connect(_PG_URL, row_factory=dict_row)
    c = sqlite3.connect(_DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _q(sql: str) -> str:
    """Translate sqlite-style placeholders for the active backend."""
    return sql.replace("?", "%s") if _PG else sql


def init_db() -> None:
    """Initialize tables (idempotent)."""
    global _initialized
    if _initialized:
        return
    with _conn() as c:
        if _PG:
            with c.cursor() as cur:
                cur.execute(_SCHEMA_PG)
        else:
            c.executescript(_SCHEMA_SQLITE)
    _initialized = True
    log.info("store ready (backend=%s)", "postgres" if _PG else "sqlite")


def store_kpi_metrics(records: List[Dict[str, Any]]) -> int:
    """Persist a batch of KPI records. Returns count inserted."""
    init_db()
    count = 0
    now = datetime.utcnow().isoformat()
    with _conn() as c:
        for r in records:
            try:
                c.execute(
                    _q(f"""
                    INSERT INTO {_T_KPI}
                      (period, category, metric, value, unit, source, confidence, created_at)
                    VALUES (?,?,?,?,?,?,?,?)
                    """),
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
    sql = f"SELECT * FROM {_T_KPI}"
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
        rows = c.execute(_q(sql), params).fetchall()
    return [dict(r) for r in rows]


def log_data_ingestion(source: str, status: str, records: int = 0,
                       error: Optional[str] = None, payload: Optional[Any] = None) -> int:
    """Log an ingestion event. Returns the ID."""
    init_db()
    now = datetime.utcnow().isoformat()
    args = (source, status, records, error,
            json.dumps(payload)[:5000] if payload else None, now, now)
    with _conn() as c:
        if _PG:
            row = c.execute(
                _q(f"INSERT INTO {_T_LOG} (source, status, records, error, payload, created_at, updated_at) "
                   "VALUES (?,?,?,?,?,?,?) RETURNING id"), args).fetchone()
            return int(row["id"])
        cur = c.execute(
            f"INSERT INTO {_T_LOG} (source, status, records, error, payload, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)", args)
        return cur.lastrowid or 0


def update_ingestion_log(log_id: int, status: str, records: int = 0,
                         error: Optional[str] = None) -> None:
    init_db()
    now = datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute(
            _q(f"UPDATE {_T_LOG} SET status=?, records=?, error=?, updated_at=? WHERE id=?"),
            (status, records, error, now, log_id),
        )


def get_pipeline_history(limit: int = 100) -> List[Dict[str, Any]]:
    init_db()
    with _conn() as c:
        rows = c.execute(_q(f"SELECT * FROM {_T_LOG} ORDER BY id DESC LIMIT ?"), (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_ingestion_row(log_id: int) -> Optional[Dict[str, Any]]:
    init_db()
    with _conn() as c:
        row = c.execute(_q(f"SELECT * FROM {_T_LOG} WHERE id = ?"), (log_id,)).fetchone()
    return dict(row) if row else None


def store_stats() -> Dict[str, Any]:
    """Aggregate counters for /pipeline/status (real, from the persistent store)."""
    init_db()
    with _conn() as c:
        events = c.execute(_q(f"SELECT COUNT(*) AS n FROM {_T_LOG}")).fetchone()
        fails = c.execute(_q(f"SELECT COUNT(*) AS n FROM {_T_LOG} WHERE status != ? OR error IS NOT NULL"), ("completed",)).fetchone()
        kpis = c.execute(_q(f"SELECT COUNT(*) AS n FROM {_T_KPI}")).fetchone()
        srcs = c.execute(_q(f"SELECT COUNT(DISTINCT source) AS n FROM {_T_LOG}")).fetchone()
    g = lambda r: (r["n"] if isinstance(r, dict) else r[0]) or 0
    return {
        "ingestion_events": g(events),
        "failed_events": g(fails),
        "records_stored": g(kpis),
        "distinct_sources": g(srcs),
        "backend": "postgres" if _PG else "sqlite",
    }
