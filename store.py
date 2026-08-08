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
import os
import sqlite3
from datetime import datetime, timezone
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

_T_KPI = "sp_kpi_metrics"
_T_LOG = "sp_ingestion_log"

_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS sp_kpi_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT NOT NULL,
    category TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT,
    source TEXT,
    confidence REAL,
    owner_session_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sp_kpi_cat ON sp_kpi_metrics(category);
CREATE INDEX IF NOT EXISTS idx_sp_kpi_period ON sp_kpi_metrics(period);

CREATE TABLE IF NOT EXISTS sp_ingestion_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    records INTEGER DEFAULT 0,
    error TEXT,
    payload TEXT,
    owner_session_id TEXT,
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
    owner_session_id TEXT,
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
    owner_session_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

from contextlib import contextmanager

_DB_PATH = Path("streampulse.db")
_initialized = False


@contextmanager
def _conn():
    if _PG:
        conn = psycopg.connect(_PG_URL, row_factory=dict_row)
        try:
            with conn:
                yield conn
        finally:
            conn.close()
    else:
        c = sqlite3.connect(_DB_PATH)
        c.row_factory = sqlite3.Row
        c.executescript(_SCHEMA_SQLITE)
        try:
            with c:
                yield c
        finally:
            c.close()


def _clean_row(r: Any) -> Dict[str, Any]:
    if not r:
        return {}
    d = dict(r)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


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
                # Idempotent migration for tables created before owner_session_id existed.
                cur.execute(f"ALTER TABLE {_T_KPI} ADD COLUMN IF NOT EXISTS owner_session_id TEXT")
                cur.execute(f"ALTER TABLE {_T_LOG} ADD COLUMN IF NOT EXISTS owner_session_id TEXT")
        else:
            c.executescript(_SCHEMA_SQLITE)
            for table in (_T_KPI, _T_LOG):
                try:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN owner_session_id TEXT")
                except sqlite3.OperationalError:
                    pass  # column already exists
    _initialized = True
    log.info("store ready (backend=%s)", "postgres" if _PG else "sqlite")


def _demo_session_scoping_enabled() -> bool:
    return os.environ.get("DEMO_SESSION_SCOPING", "true").lower() == "true"


def store_kpi_metrics(records: List[Dict[str, Any]], owner_session_id: Optional[str] = None) -> int:
    """Persist a batch of KPI records. Returns count inserted.

    owner_session_id=None writes rows visible to every visitor (the default for real
    external webhooks/n8n/CRM sources — that's the point of a public ingestion demo).
    A visitor testing ingestion through the frontend UI gets their browser's
    X-Demo-Session-Id here instead, so their test data isn't shown to other visitors.
    Anonymous demo isolation, not production auth — see DEMO_SESSION_SCOPING."""
    init_db()
    count = 0
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        for r in records:
            try:
                val = r.get("value")
                try:
                    num_val = float(val) if val is not None else 0.0
                except (ValueError, TypeError):
                    num_val = 0.0

                conf = r.get("confidence")
                try:
                    num_conf = float(conf) if conf is not None else 1.0
                except (ValueError, TypeError):
                    num_conf = 1.0

                params = (
                    str(r.get("period") or "N/A"),
                    str(r.get("category") or "General"),
                    str(r.get("metric") or "metric"),
                    num_val,
                    str(r.get("unit")) if r.get("unit") is not None else None,
                    str(r.get("source")) if r.get("source") is not None else None,
                    num_conf,
                    owner_session_id,
                    now,
                )

                if _PG:
                    with c.transaction():
                        c.execute(
                            _q(f"""
                            INSERT INTO {_T_KPI}
                              (period, category, metric, value, unit, source, confidence, owner_session_id, created_at)
                            VALUES (?,?,?,?,?,?,?,?,?)
                            """),
                            params,
                        )
                else:
                    c.execute(
                        _q(f"""
                        INSERT INTO {_T_KPI}
                          (period, category, metric, value, unit, source, confidence, owner_session_id, created_at)
                        VALUES (?,?,?,?,?,?,?,?,?)
                        """),
                        params,
                    )
                count += 1
            except Exception as e:
                log.warning("skip record %s: %s", r.get("metric"), e)
    return count


def get_kpi_metrics(
    category: Optional[str] = None,
    metric_filter: Optional[str] = None,
    limit: int = 200,
    session_id: Optional[str] = None,
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
    if _demo_session_scoping_enabled():
        where.append("(owner_session_id IS NULL OR owner_session_id = ?)")
        params.append(session_id)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ?"; params.append(limit)
    with _conn() as c:
        rows = c.execute(_q(sql), params).fetchall()
    return [_clean_row(r) for r in rows]


def log_data_ingestion(source: str, status: str, records: int = 0,
                       error: Optional[str] = None, payload: Optional[Any] = None,
                       owner_session_id: Optional[str] = None) -> int:
    """Log an ingestion event. Returns the ID. See store_kpi_metrics for owner_session_id."""
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    args = (source, status, records, error,
            json.dumps(payload)[:5000] if payload else None, owner_session_id, now, now)
    with _conn() as c:
        if _PG:
            row = c.execute(
                _q(f"INSERT INTO {_T_LOG} (source, status, records, error, payload, owner_session_id, created_at, updated_at) "
                   "VALUES (?,?,?,?,?,?,?,?) RETURNING id"), args).fetchone()
            return int(row["id"])
        cur = c.execute(
            f"INSERT INTO {_T_LOG} (source, status, records, error, payload, owner_session_id, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)", args)
        return cur.lastrowid or 0


def update_ingestion_log(log_id: int, status: str, records: int = 0,
                         error: Optional[str] = None) -> None:
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        c.execute(
            _q(f"UPDATE {_T_LOG} SET status=?, records=?, error=?, updated_at=? WHERE id=?"),
            (status, records, error, now, log_id),
        )


def get_pipeline_history(limit: int = 100, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    init_db()
    sql = f"SELECT * FROM {_T_LOG}"
    params: List[Any] = []
    if _demo_session_scoping_enabled():
        sql += " WHERE (owner_session_id IS NULL OR owner_session_id = ?)"
        params.append(session_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with _conn() as c:
        rows = c.execute(_q(sql), params).fetchall()
    return [_clean_row(r) for r in rows]


def get_ingestion_row(log_id: int, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """session_id enforces ownership for /pipeline/replay: a log_id belonging to a
    different visitor's session returns None instead of that visitor's stored payload."""
    init_db()
    sql = f"SELECT * FROM {_T_LOG} WHERE id = ?"
    params: List[Any] = [log_id]
    if _demo_session_scoping_enabled():
        sql += " AND (owner_session_id IS NULL OR owner_session_id = ?)"
        params.append(session_id)
    with _conn() as c:
        row = c.execute(_q(sql), params).fetchone()
    return _clean_row(row) if row else None


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
