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
        """Normalize an incoming JSON payload into a list of DataRecord dicts."""
        if isinstance(raw_json, dict) and "records" in raw_json:
            items = raw_json["records"]
        elif isinstance(raw_json, list):
            items = raw_json
        else:
            items = [raw_json]
        return [
            DataRecord({
                "source": source_name,
                "period": r.get("period") if isinstance(r, dict) else None,
                "category": r.get("category") if isinstance(r, dict) else None,
                "metric": r.get("metric") if isinstance(r, dict) else None,
                "value": r.get("value") if isinstance(r, dict) else None,
                "unit": r.get("unit") if isinstance(r, dict) else None,
                "confidence": r.get("confidence", 0.9) if isinstance(r, dict) else 0.9,
                "raw": r,
            })
            for r in items
        ]
