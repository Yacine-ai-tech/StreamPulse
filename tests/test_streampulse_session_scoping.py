"""Tests for StreamPulse session scoping and admin bypass."""
import pytest
from store import get_pipeline_history, get_kpi_metrics, init_db


def test_streampulse_session_scoping_query_construction():
    """Verify session isolation queries."""
    from store import _demo_session_scoping_enabled, store_stats, get_pipeline_history, get_kpi_metrics

    # If scoping enabled:
    assert _demo_session_scoping_enabled() is True

    # Fresh session with unique ID has 0 rows and 0 scoped stats
    session_id = "test_unique_visitor_xyz987"
    stats = store_stats(session_id=session_id)
    assert stats["session_scoped"] is True
    assert stats["ingestion_events"] == 0
    assert stats["records_stored"] == 0

    history = get_pipeline_history(limit=50, session_id=session_id)
    assert len(history) == 0

    kpis = get_kpi_metrics(session_id=session_id)
    assert len(kpis) == 0

    # Admin wildcard bypasses scoping
    admin_stats = store_stats(session_id="*")
    assert admin_stats["session_scoped"] is False


def test_pipeline_history_fails_closed_without_admin_or_session(monkeypatch):
    import store

    def fail_if_database_is_used():
        raise AssertionError("unscoped visitor history must not query the database")

    monkeypatch.setattr(store, "init_db", fail_if_database_is_used)
    assert get_pipeline_history(session_id=None) == []
    assert get_pipeline_history(session_id="*") == []
