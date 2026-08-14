"""
StreamPulse n8n Integration Layer (Public Integration Only)
Agnostic webhook bridge and REST API wrapper for connecting StreamPulse to external n8n instances.

This is the PUBLIC integration layer that allows users to connect their own n8n instances
to StreamPulse.

Users define workflows in their private n8n instance and push data to StreamPulse webhooks.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from core.config import settings
from core.i18n import I18N, t
from core.logger import get_logger

log = get_logger(__name__)


@dataclass
class N8NClient:
    """Thin generic wrapper around the n8n REST API."""

    base_url: str = settings.N8N_BASE_URL
    api_key: str = settings.N8N_API_KEY or ""
    timeout: float = 15.0

    def _headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            h["X-N8N-API-KEY"] = self.api_key
        return h

    def _get(self, path: str) -> Dict[str, Any]:
        """Make GET request to n8n API."""
        url = f"{self.base_url.rstrip('/')}{path}"
        try:
            r = httpx.get(url, headers=self._headers(), timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as exc:
            log.error("n8n HTTP error %s: %s", exc.response.status_code, exc.response.text[:200])
            return {"error": str(exc), "status_code": exc.response.status_code}
        except Exception as exc:
            log.error("n8n request failed: %s", exc)
            return {"error": str(exc)}

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}{path}"
        try:
            r = httpx.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 400:
                log.warning("n8n HTTP 400 (expected if credentials missing): %s", exc.response.text[:200])
            else:
                log.error("n8n HTTP error %s: %s", exc.response.status_code, exc.response.text[:200])
            return {"error": str(exc), "status_code": exc.response.status_code}
        except Exception as exc:
            log.error("n8n request failed: %s", exc)
            return {"error": str(exc)}
            
    def test_connection(self) -> Dict[str, Any]:
        """Test n8n connection and return status."""
        try:
            r = httpx.get(f"{self.base_url.rstrip('/')}/healthz", timeout=5.0)
            return {
                "status": "healthy" if r.status_code == 200 else "unhealthy",
                "url": self.base_url,
                "n8n_api_configured": bool(self.api_key),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ── Generic webhook ingest ────────────────────────────────────────

    def ingest_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Forward arbitrary data from an n8n webhook into the platform."""
        return self._post("/webhook/ingest", payload)

    # ── Programmatic API Methods ──────────────────────────────

    def list_workflows(self, limit: int = 50, active_only: bool = False) -> Dict[str, Any]:
        params = f"?limit={limit}"
        if active_only:
            params += "&active=true"
        return self._get(f"/api/v1/workflows{params}")

    def execute_workflow(self, workflow_id: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._post(f"/api/v1/workflows/{workflow_id}/execute", {"data": data or {}})

    def trigger_webhook(self, webhook_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger a webhook directly (public, no API key needed)."""
        url = f"{self.base_url.rstrip('/')}/webhook/{webhook_id}"
        try:
            r = httpx.post(url, json=data, timeout=self.timeout)
            r.raise_for_status()
            return r.json() if r.text else {"status": "success"}
        except httpx.HTTPStatusError as exc:
            return {"error": str(exc), "status_code": exc.response.status_code}
        except Exception as exc:
            return {"error": str(exc)}

# ── Convenience singleton ─────────────────────────────────────────────────
n8n = N8NClient()
