"""
StreamPulse declarative sources via dlt.

Each @dlt.source is a generator of KPI records that the dlt pipeline can
incrementally load into PostgreSQL or DuckDB. Wire to Prefect for scheduling.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List

try:
    import dlt  # type: ignore
    _DLT = True
except ImportError:
    _DLT = False


if _DLT:
    @dlt.source(name="gmail_source")
    def gmail_source(query: str = "label:invoices is:unread") -> Iterable[Dict[str, Any]]:
        """Yield parsed invoice metadata from Gmail (stub — wire to gmail API)."""
        # Production: query Gmail API for matching messages
        return []  # type: ignore

    @dlt.source(name="gsheet_source")
    def gsheet_source(sheet_id: str = "") -> Iterable[Dict[str, Any]]:
        """Yield rows from a Google Sheet (stub)."""
        return []  # type: ignore

    @dlt.source(name="webhook_source")
    def webhook_source(records: List[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
        """Pass through pre-collected webhook records."""
        for r in records or []:
            yield r
else:
    def gmail_source(*a, **kw): return []
    def gsheet_source(*a, **kw): return []
    def webhook_source(records=None, *a, **kw): return records or []
