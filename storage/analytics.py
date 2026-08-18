"""
DuckDB analytics engine for StreamPulse.

This module provides OLAP-style analytics queries using DuckDB for high-performance
analytical processing of StreamPulse data. Inert unless ENABLE_DUCKDB=true (off by
default) -- exercised end-to-end (including a live import_from_postgres() against
the real shared Postgres) on 2026-08-10; every method returns real data.
import_from_postgres() requires DuckDB's postgres extension, which is downloaded
on first use (INSTALL postgres) -- that needs outbound network access once.
"""
from __future__ import annotations

import os
import duckdb
from typing import Any, Dict, Optional
import pandas as pd

from core.config import settings
from core.logger import get_logger

log = get_logger(__name__)


class AnalyticsEngine:
    """DuckDB-based analytics engine for StreamPulse."""

    def __init__(self):
        self._enabled = settings.ENABLE_DUCKDB
        self._db_path = settings.DUCKDB_PATH
        self._conn = None
        
        if self._enabled:
            self._initialize_duckdb()
        else:
            log.info("DuckDB analytics disabled (ENABLE_DUCKDB=false)")

    def _initialize_duckdb(self):
        """Initialize DuckDB connection and schema."""
        try:
            self._conn = duckdb.connect(self._db_path)
            
            # Create analytics schema
            self._conn.execute("""
                CREATE SCHEMA IF NOT EXISTS analytics
            """)
            
            # Create fact table for classified records
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS analytics.classified_records (
                    id INTEGER PRIMARY KEY,
                    source VARCHAR(100),
                    domain VARCHAR(50),
                    metric_name VARCHAR(200),
                    metric_value DOUBLE,
                    confidence DOUBLE,
                    classification_method VARCHAR(50),
                    timestamp TIMESTAMP,
                    ingestion_timestamp TIMESTAMP,
                    metadata JSON,
                    owner_session_id VARCHAR
                )
            """)
            # Idempotent migration for the DB file created before owner_session_id existed
            # (mirrors store.py's own ALTER TABLE ADD COLUMN IF NOT EXISTS pattern).
            self._conn.execute("""
                ALTER TABLE analytics.classified_records ADD COLUMN IF NOT EXISTS owner_session_id VARCHAR
            """)
            
            # Create aggregate fact table for domain summaries
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS analytics.domain_summary (
                    summary_date DATE,
                    domain VARCHAR(50),
                    record_count INTEGER,
                    avg_confidence DOUBLE,
                    method_distribution JSON,
                    top_metrics JSON,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (summary_date, domain)
                )
            """)
            
            # Create performance tracking table
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS analytics.classifier_performance (
                    evaluation_date DATE,
                    method VARCHAR(50),
                    total_classifications INTEGER,
                    avg_confidence DOUBLE,
                    avg_latency_ms DOUBLE,
                    cache_hit_rate DOUBLE,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            log.info("DuckDB analytics initialized at %s", self._db_path)
            
        except Exception as e:
            log.error("Failed to initialize DuckDB analytics: %s", e)
            self._enabled = False

    def import_from_postgres(self, query: str = None) -> int:
        """Import data from PostgreSQL's sp_kpi_metrics into DuckDB for analytics,
        via DuckDB's postgres scanner extension (attached read-only, detached after)."""
        if not self._enabled or not self._conn:
            return 0

        pg_url = (getattr(settings, "POSTGRES_URL", "") or "").strip()
        if not pg_url:
            log.warning("import_from_postgres: POSTGRES_URL not set, nothing to import")
            return 0

        try:
            self._conn.execute("INSTALL postgres")
            self._conn.execute("LOAD postgres")
            # pg_url comes from our own settings, not user input -- same trust level as
            # the INTERVAL '{days} days' f-strings already used elsewhere in this class.
            self._conn.execute(f"ATTACH '{pg_url}' AS pg_source (TYPE POSTGRES, READ_ONLY)")
            try:
                # Default query: sp_kpi_metrics is the real shared-Postgres table name
                # (see store.py) -- "kpi_metrics" (unprefixed) belongs to the platform's
                # own seed data, not StreamPulse's.
                if query is None:
                    # created_at is stored as TEXT (ISO-8601, see store.py) on the
                    # Postgres side, not a real TIMESTAMP column -- needs an explicit
                    # cast before it can be compared to CURRENT_TIMESTAMP.
                    # owner_session_id carries straight over from sp_kpi_metrics so this
                    # DuckDB copy can be scoped the same way the Postgres original is
                    # (see store.py's owner_session_id docstring) -- it was dropped here
                    # before, which is why /analytics/* had no visitor scoping at all.
                    query = """
                        SELECT
                            id, source, category AS domain, metric AS metric_name, value AS metric_value,
                            confidence, CAST(created_at AS TIMESTAMP) AS ingestion_timestamp,
                            CURRENT_TIMESTAMP AS timestamp,
                            'imported' AS classification_method,
                            '{}'::JSON AS metadata,
                            owner_session_id
                        FROM pg_source.sp_kpi_metrics
                        WHERE CAST(created_at AS TIMESTAMP) > CURRENT_TIMESTAMP - INTERVAL '30 days'
                    """

                # OR REPLACE keeps this safely re-runnable on the same rows (id is the
                # DuckDB-side primary key) instead of failing on a second import.
                # Explicit column list -- relying on positional order between this
                # SELECT and the table's declared column order is what caused the
                # classification_method/timestamp/ingestion_timestamp values to land
                # in each other's columns previously.
                self._conn.execute(f"""
                    INSERT OR REPLACE INTO analytics.classified_records
                        (id, source, domain, metric_name, metric_value, confidence,
                         ingestion_timestamp, timestamp, classification_method, metadata,
                         owner_session_id)
                    {query}
                """)

                count = self._conn.execute("SELECT COUNT(*) FROM analytics.classified_records").fetchone()[0]
                log.info("Imported from PostgreSQL; classified_records now has %d rows", count)
                return count
            finally:
                self._conn.execute("DETACH pg_source")

        except Exception as e:
            log.error("Failed to import from PostgreSQL: %s", e)
            return 0

    def get_domain_summary(self, days: int = 7, session_id: Optional[str] = None) -> pd.DataFrame:
        """Get domain-level summary for analytics.

        session_id=None (real external callers, e.g. n8n) sees only global/seeded rows
        (owner_session_id IS NULL) -- same "no scope, no visibility into anyone's demo
        data" default as store.py's owner_session_id docstring, not "see everything"."""
        if not self._enabled or not self._conn:
            return pd.DataFrame()

        try:
            query = f"""
                SELECT
                    domain,
                    COUNT(*) as record_count,
                    AVG(confidence) as avg_confidence,
                    classification_method,
                    COUNT(DISTINCT source) as source_count
                FROM analytics.classified_records
                WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '{days} days'
                  AND (owner_session_id IS NULL OR owner_session_id = ?)
                GROUP BY domain, classification_method
                ORDER BY domain, record_count DESC
            """

            return self._conn.execute(query, [session_id]).df()

        except Exception as e:
            log.error("Failed to get domain summary: %s", e)
            return pd.DataFrame()

    def get_classification_trends(self, days: int = 30, session_id: Optional[str] = None) -> pd.DataFrame:
        """Get classification trends over time. See get_domain_summary for session_id."""
        if not self._enabled or not self._conn:
            return pd.DataFrame()

        try:
            query = f"""
                SELECT
                    DATE(timestamp) as classification_date,
                    classification_method,
                    COUNT(*) as total_classifications,
                    AVG(confidence) as avg_confidence
                FROM analytics.classified_records
                WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '{days} days'
                  AND (owner_session_id IS NULL OR owner_session_id = ?)
                GROUP BY classification_date, classification_method
                ORDER BY classification_date DESC, classification_method
            """

            return self._conn.execute(query, [session_id]).df()

        except Exception as e:
            log.error("Failed to get classification trends: %s", e)
            return pd.DataFrame()

    def get_source_performance(self, days: int = 7) -> pd.DataFrame:
        """Get performance metrics by data source."""
        if not self._enabled or not self._conn:
            return pd.DataFrame()
            
        try:
            query = f"""
                SELECT 
                    source,
                    COUNT(*) as record_count,
                    AVG(confidence) as avg_confidence,
                    COUNT(DISTINCT domain) as domain_diversity,
                    MODE(classification_method) as dominant_method
                FROM analytics.classified_records
                WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '{days} days'
                GROUP BY source
                ORDER BY record_count DESC
            """
            
            return self._conn.execute(query).df()
            
        except Exception as e:
            log.error("Failed to get source performance: %s", e)
            return pd.DataFrame()

    def run_custom_query(self, query: str) -> pd.DataFrame:
        """Run a custom DuckDB analytics query."""
        if not self._enabled or not self._conn:
            return pd.DataFrame()
            
        try:
            return self._conn.execute(query).df()
        except Exception as e:
            log.error("Failed to run custom query: %s", e)
            return pd.DataFrame()

    def refresh_materialized_views(self) -> bool:
        """Refresh materialized views for faster analytics."""
        if not self._enabled or not self._conn:
            return False
            
        try:
            # DuckDB's ON CONFLICT ... DO UPDATE SET rejects a bare CURRENT_TIMESTAMP
            # on the right-hand side (misbinds it as a column reference), so this
            # refresh clears today's row first and re-inserts rather than upserting.
            self._conn.execute("DELETE FROM analytics.domain_summary WHERE summary_date = CURRENT_DATE")

            # Update domain summary. json_group_object(col, COUNT(*)) can't nest an
            # aggregate inside an aggregate directly, so the per-(domain, method) and
            # per-(domain, metric) counts are computed in their own GROUP BY first,
            # then re-aggregated into JSON per domain.
            self._conn.execute("""
                INSERT INTO analytics.domain_summary
                    (summary_date, domain, record_count, avg_confidence, method_distribution, top_metrics)
                WITH method_counts AS (
                    SELECT domain, classification_method, COUNT(*) AS cnt
                    FROM analytics.classified_records
                    WHERE DATE(timestamp) = CURRENT_DATE
                    GROUP BY domain, classification_method
                ),
                metric_counts AS (
                    SELECT domain, metric_name, COUNT(*) AS cnt
                    FROM analytics.classified_records
                    WHERE DATE(timestamp) = CURRENT_DATE
                    GROUP BY domain, metric_name
                ),
                method_json AS (
                    SELECT domain, json_group_object(classification_method, cnt) AS method_distribution
                    FROM method_counts
                    GROUP BY domain
                ),
                metric_json AS (
                    SELECT domain, json_group_object(metric_name, cnt) AS top_metrics
                    FROM metric_counts
                    GROUP BY domain
                ),
                totals AS (
                    SELECT domain, COUNT(*) AS record_count, AVG(confidence) AS avg_confidence
                    FROM analytics.classified_records
                    WHERE DATE(timestamp) = CURRENT_DATE
                    GROUP BY domain
                )
                SELECT
                    CURRENT_DATE AS summary_date,
                    t.domain,
                    t.record_count,
                    t.avg_confidence,
                    m.method_distribution,
                    mt.top_metrics
                FROM totals t
                JOIN method_json m ON m.domain = t.domain
                JOIN metric_json mt ON mt.domain = t.domain
            """)
            
            log.info("Materialized views refreshed successfully")
            return True
            
        except Exception as e:
            log.error("Failed to refresh materialized views: %s", e)
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get analytics engine statistics."""
        if not self._enabled or not self._conn:
            return {"enabled": False}
            
        try:
            # Get table sizes
            classified_count = self._conn.execute("SELECT COUNT(*) FROM analytics.classified_records").fetchone()[0]
            summary_count = self._conn.execute("SELECT COUNT(*) FROM analytics.domain_summary").fetchone()[0]

            # DuckDB has no pg_database_size() (that's Postgres) — the on-disk file size
            # is the DuckDB-native equivalent.
            try:
                db_size_bytes = os.path.getsize(self._db_path)
            except OSError:
                db_size_bytes = None

            return {
                "enabled": True,
                "db_path": self._db_path,
                "db_size_bytes": db_size_bytes,
                "classified_records": classified_count,
                "domain_summaries": summary_count,
                "storage_backend": "duckdb"
            }
            
        except Exception as e:
            log.error("Failed to get analytics stats: %s", e)
            return {"enabled": True, "error": str(e)}

    def close(self):
        """Close DuckDB connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


# Global instance
_analytics_engine: Optional[AnalyticsEngine] = None


def get_analytics_engine() -> AnalyticsEngine:
    """Get or create the global analytics engine instance."""
    global _analytics_engine
    if _analytics_engine is None:
        _analytics_engine = AnalyticsEngine()
    return _analytics_engine