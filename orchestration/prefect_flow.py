"""
StreamPulse Prefect 3 flow — retried, observable, schedulable.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

try:
    from prefect import flow, task, get_run_logger  # type: ignore
    _PREFECT = True
except ImportError:
    _PREFECT = False


if _PREFECT:
    @task(retries=3, retry_delay_seconds=30)
    def classify_batch(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Classify each record into a domain. Retried on transient failures."""
        from pipeline.classifier import classify
        logger = get_run_logger()
        out: List[Dict[str, Any]] = []
        for r in records:
            try:
                result = classify(r.get("metric", "") + " " + str(r.get("raw", "")))
                merged = {**r, **(result if isinstance(result, dict) else {})}
                out.append(merged)
            except Exception as e:
                logger.warning("classify failed: %s", e)
                out.append({**r, "domain": "Unknown", "confidence": 0.0})
        return out

    @task(retries=3, retry_delay_seconds=10)
    def persist(records: List[Dict[str, Any]]) -> int:
        from store import store_kpi_metrics
        return store_kpi_metrics(records)

    @flow(name="streampulse-realtime-pipeline")
    def pipeline_flow(records: List[Dict[str, Any]]) -> Dict[str, Any]:
        classified = classify_batch(records)
        inserted = persist(classified)
        return {"records_in": len(records), "records_inserted": inserted}
else:
    def pipeline_flow(records):  # type: ignore
        return {"records_in": len(records or []), "records_inserted": 0, "stub": True}
