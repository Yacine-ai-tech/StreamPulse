"""
DuckDB analytics engine for StreamPulse.

This module provides OLAP-style analytics queries using DuckDB for high-performance
analytical processing of StreamPulse data.

NOT PRODUCTION-VERIFIED — inert unless ENABLE_DUCKDB=true (off by default).
Known issues before relying on this: get_stats() calls pg_database_size(), a
PostgreSQL function DuckDB doesn't have; refresh_materialized_views()'s
ON CONFLICT clause needs a UNIQUE/PRIMARY KEY on (summary_date, domain) that
domain_summary's CREATE TABLE doesn't declare; import_from_postgres()'s default
query reads FROM kpi_metrics, but the shared production Postgres schema uses
sp_kpi_metrics-prefixed table names. Fix these before flipping ENABLE_DUCKDB on.
"""
from __future__ import annotations

import duckdb
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
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
                    metadata JSON
                )
            """)
            
            # Create aggregate fact table for domain summaries
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS analytics.domain_summary (
                    summary_date DATE,
                    domain VARCHAR(50),
                    record_count INTEGER,
                    avg_confidence DOUBLE,
                    method_distribution JSONB,
                    top_metrics JSONB,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        """Import data from PostgreSQL into DuckDB for analytics."""
        if not self._enabled or not self._conn:
            return 0
            
        try:
            # Default query to import recent classified records
            if query is None:
                query = """
                    SELECT 
                        id, source, domain, metric_name, metric_value, 
                        confidence, timestamp as ingestion_timestamp,
                        CURRENT_TIMESTAMP as timestamp,
                        'imported' as classification_method,
                        '{}'::json as metadata
                    FROM kpi_metrics 
                    WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '30 days'
                """
            
            # Import using duckdb's postgres scanner
            import_query = f"""
                INSERT INTO analytics.classified_records
                {query}
            """
            
            self._conn.execute(import_query)
            
            # Get row count
            result = self._conn.execute("SELECT COUNT(*) FROM analytics.classified_records")
            count = result.fetchone()[0]
            
            log.info("Imported %d records from PostgreSQL to DuckDB", count)
            return count
            
        except Exception as e:
            log.error("Failed to import from PostgreSQL: %s", e)
            return 0

    def get_domain_summary(self, days: int = 7) -> pd.DataFrame:
        """Get domain-level summary for analytics."""
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
                GROUP BY domain, classification_method
                ORDER BY domain, record_count DESC
            """
            
            return self._conn.execute(query).df()
            
        except Exception as e:
            log.error("Failed to get domain summary: %s", e)
            return pd.DataFrame()

    def get_classification_trends(self, days: int = 30) -> pd.DataFrame:
        """Get classification trends over time."""
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
                GROUP BY classification_date, classification_method
                ORDER BY classification_date DESC, classification_method
            """
            
            return self._conn.execute(query).df()
            
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
            # Update domain summary
            self._conn.execute("""
                INSERT INTO analytics.domain_summary
                SELECT 
                    CURRENT_DATE as summary_date,
                    domain,
                    COUNT(*) as record_count,
                    AVG(confidence) as avg_confidence,
                    json_group_object(classification_method, COUNT(*)) as method_distribution,
                    json_group_object(metric_name, COUNT(*)) as top_metrics
                FROM analytics.classified_records
                WHERE DATE(timestamp) = CURRENT_DATE
                GROUP BY domain
                ON CONFLICT (summary_date, domain) 
                DO UPDATE SET 
                    record_count = EXCLUDED.record_count,
                    avg_confidence = EXCLUDED.avg_confidence,
                    method_distribution = EXCLUDED.method_distribution,
                    top_metrics = EXCLUDED.top_metrics,
                    updated_at = CURRENT_TIMESTAMP
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
            
            # Get database size
            db_size = self._conn.execute("SELECT pg_database_size('analytics')").fetchone()[0]
            
            return {
                "enabled": True,
                "db_path": self._db_path,
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