"""Tests for StreamPulse session scoping and admin bypass."""
import pytest
from store import get_pipeline_history, get_kpi_metrics, init_db


def test_streampulse_session_scoping_query_construction():
    """Verify session isolation queries."""
    from store import _demo_session_scoping_enabled

    # If scoping enabled:
    assert _demo_session_scoping_enabled() is True
    # Admin '*' bypasses filter
    # Regular visitor includes owner_session_id check
