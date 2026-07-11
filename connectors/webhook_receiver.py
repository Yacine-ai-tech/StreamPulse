"""
WebhookReceiver — HMAC-verified webhook ingestion + pipeline routing.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Dict, List, Optional

from core.config import settings
from core.logger import get_logger

log = get_logger(__name__)


class DataRecord(dict):
    """Plain-dict record (kept as dict for JSON-friendly serialization)."""


class WebhookReceiver:
    """Verify, parse, and route webhook payloads."""

    @staticmethod
    def verify_signature(payload: bytes, signature: str, secret: Optional[str] = None) -> bool:
        """Verify HMAC-SHA256 of payload against `X-Signature-256` header."""
        secret = secret or settings.WEBHOOK_SECRET
        if not signature:
            return False
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        sig = signature.replace("sha256=", "")
        return hmac.compare_digest(expected, sig)

    @staticmethod
    def parse_payload(raw_json: Any, source_name: str) -> List[DataRecord]:
        """Normalize an incoming JSON payload into a list of DataRecord dicts.

        For non-KPI payloads (e.g. GitHub events, Slack notifications) the
        required ``metric``, ``value``, ``period``, ``category`` columns are
        derived from available text so the store never receives a NULL in a
        NOT-NULL column.
        """
        if isinstance(raw_json, dict) and "records" in raw_json:
            items = raw_json["records"]
        elif isinstance(raw_json, list):
            items = raw_json
        else:
            items = [raw_json]

        records: List[DataRecord] = []
        for r in items:
            if isinstance(r, dict):
                # Try KPI fields directly; fall back to text derived from event
                raw_text = (
                    r.get("text") or r.get("title") or r.get("body") or
                    r.get("action") or r.get("subject") or
                    str(list(r.values())[0]) if r else "event"
                )
                records.append(DataRecord({
                    "source":     source_name,
                    "period":     r.get("period", ""),
                    "category":   r.get("category", source_name),
                    "metric":     r.get("metric") or raw_text[:100],
                    "value":      float(r.get("value") or 0),
                    "unit":       r.get("unit"),
                    "confidence": float(r.get("confidence", 0.9)),
                    "raw":        r,
                }))
            else:
                records.append(DataRecord({
                    "source": source_name, "period": "", "category": source_name,
                    "metric": str(r)[:100], "value": 0.0,
                    "unit": None, "confidence": 0.9, "raw": r,
                }))
        return records
