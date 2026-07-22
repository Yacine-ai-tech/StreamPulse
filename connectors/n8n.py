"""
n8n integration — restricted to Gmail, Google Drive, Google Sheets, ClickUp.

StreamPulse n8n Integration Orchestrator.
Manages automated workflow execution, credential auto-provisioning, and 
cross-application data flow (Google Workspace, ClickUp, Webhooks).
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


# ── Allowed n8n node catalogue ───────────────────────────────────────────
ALLOWED_NODES = {
    "gmail": {
        "node": "n8n-nodes-base.gmail",
        "account": settings.GMAIL_PRIMARY,
        "desc_en": "Send / receive emails & alerts",
        "desc_fr": "Envoyer / recevoir des emails & alertes",
    },
    "drive": {
        "node": "n8n-nodes-base.googleDrive",
        "account": settings.DRIVE_ACCOUNT,
        "desc_en": "Upload / manage files on Google Drive",
        "desc_fr": "Téléverser / gérer des fichiers sur Google Drive",
    },
    "sheets": {
        "node": "n8n-nodes-base.googleSheets",
        "account": settings.GSHEETS_ACCOUNT,
        "desc_en": "Read / write Google Sheets spreadsheets (replaces Excel)",
        "desc_fr": "Lire / écrire des feuilles Google Sheets (remplace Excel)",
    },
    "clickup": {
        "node": "n8n-nodes-base.clickUp",
        "account": settings.CLICKUP_WORKSPACE_ID,
        "desc_en": "Create tasks, update statuses in ClickUp",
        "desc_fr": "Créer des tâches, mettre à jour les statuts dans ClickUp",
    },
}


@dataclass
class N8NClient:
    """Thin wrapper around the n8n REST / webhook API with full credential support."""

    base_url: str = settings.N8N_BASE_URL
    api_key: str = settings.N8N_API_KEY or ""
    timeout: float = 15.0
    
    # Credentials from .env
    google_client_id: str = settings.GOOGLE_CLIENT_ID
    google_client_secret: str = settings.GOOGLE_CLIENT_SECRET
    clickup_api_key: str = settings.CLICKUP_API_KEY
    clickup_workspace_id: str = settings.CLICKUP_WORKSPACE_ID

    # ── Internal helpers ──────────────────────────────────────────────

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
    
    def _patch(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make PATCH request to n8n API."""
        url = f"{self.base_url.rstrip('/')}{path}"
        try:
            r = httpx.patch(url, json=payload, headers=self._headers(), timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as exc:
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
                "credentials_configured": {
                    "google_oauth": bool(self.google_client_id and self.google_client_secret),
                    "clickup": bool(self.clickup_api_key and self.clickup_workspace_id),
                    "n8n_api": bool(self.api_key),
                }
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def auto_provision(self) -> Dict[str, Any]:
        """Programmatically setup n8n: upload workflows and set credentials."""
        if not self.api_key:
            return {"status": "skipped", "reason": "No N8N_API_KEY configured"}
            
        from pathlib import Path
        results = {"workflows": [], "credentials": [], "errors": []}
        cred_ids = {}
        
        # 1. Auto-provision ClickUp Credentials if available
        if self.clickup_api_key:
            cred_payload = {
                "name": "StreamPulse ClickUp API",
                "type": "clickUpApi",
                "data": {"accessToken": self.clickup_api_key}
            }
            res = self._post("/api/v1/credentials", cred_payload)
            if "error" not in res and res.get("id"):
                results["credentials"].append("clickup")
                cred_ids["clickUpApi"] = res["id"]
                
        # 2. Auto-provision Google OAuth Credentials
        if self.google_client_id and self.google_client_secret:
            for g_type in ["gmailOAuth2", "googleDriveOAuth2", "googleSheetsOAuth2"]:
                cred_payload = {
                    "name": f"StreamPulse {g_type}",
                    "type": g_type,
                    "data": {
                        "clientId": self.google_client_id,
                        "clientSecret": self.google_client_secret
                    }
                }
                res = self._post("/api/v1/credentials", cred_payload)
                if "error" not in res and res.get("id"):
                    results["credentials"].append(g_type)
                    cred_ids[g_type] = res["id"]

        # 3. Upload Custom Workflows
        wf_dir = Path(__file__).resolve().parent / "n8n" / "workflows"
        if wf_dir.exists():
            for wf_file in wf_dir.glob("*.json"):
                try:
                    with open(wf_file, "r") as f:
                        wf_data = json.load(f)
                    
                    payload = wf_data if "nodes" in wf_data else wf_data.get("workflow", wf_data)
                    if "settings" not in payload:
                        payload["settings"] = {}
                        
                    # Inject credential IDs dynamically
                    for node in payload.get("nodes", []):
                        if "credentials" in node:
                            for c_type, c_data in node["credentials"].items():
                                if c_type in cred_ids:
                                    c_data["id"] = cred_ids[c_type]
                                    
                    r = self._post("/api/v1/workflows", payload)
                    if "error" in r:
                        results["errors"].append(f"Upload {wf_file.name} failed: {r['error']}")
                    else:
                        results["workflows"].append(r.get("id") or wf_file.name)
                        if r.get("id"):
                            # Try to activate it (will fail for OAuth if not signed in yet)
                            self.update_workflow_status(r["id"], True)
                except Exception as e:
                    results["errors"].append(str(e))
                    
        return results

    # ── High-level actions ────────────────────────────────────────────

    def send_gmail_alert(
        self,
        subject: str,
        body: str,
        to: Optional[str] = None,
        use_oauth: bool = True,
    ) -> Dict[str, Any]:
        """Trigger a Gmail alert via n8n webhook with OAuth2 support."""
        payload = {
            "to": to or settings.GMAIL_PRIMARY,
            "subject": subject,
            "body": body,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        if use_oauth and self.google_client_id:
            payload["oauth2"] = {
                "client_id": self.google_client_id,
                "client_secret": self.google_client_secret,
            }
        
        return self._post("/webhook/gmail-alert", payload)

    def upload_to_drive(
        self,
        filename: str,
        content_b64: str,
        folder_id: Optional[str] = None,
        use_oauth: bool = True,
    ) -> Dict[str, Any]:
        """Upload a file to Google Drive via n8n webhook with OAuth2 support."""
        payload = {
            "filename": filename,
            "content": content_b64,
            "folder_id": folder_id or "",
            "account": settings.DRIVE_ACCOUNT,
        }
        
        if use_oauth and self.google_client_id:
            payload["oauth2"] = {
                "client_id": self.google_client_id,
                "client_secret": self.google_client_secret,
            }
        
        return self._post("/webhook/drive-upload", payload)

    def push_sheets_data(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        rows: List[Dict[str, Any]],
        use_oauth: bool = True,
    ) -> Dict[str, Any]:
        """Append rows to a Google Sheets spreadsheet via n8n webhook with OAuth2 support."""
        payload = {
            "spreadsheet_id": spreadsheet_id,
            "sheet_name": sheet_name,
            "rows": rows,
            "account": settings.GSHEETS_ACCOUNT,
        }
        
        if use_oauth and self.google_client_id:
            payload["oauth2"] = {
                "client_id": self.google_client_id,
                "client_secret": self.google_client_secret,
            }
        
        return self._post("/webhook/sheets-push", payload)

    def create_clickup_task(
        self,
        list_id: str,
        name: str,
        description: str = "",
        priority: int = 3,
    ) -> Dict[str, Any]:
        """Create a ClickUp task via n8n webhook with API credentials."""
        return self._post("/webhook/clickup-task", {
            "list_id": list_id or self.clickup_workspace_id,
            "name": name,
            "description": description,
            "priority": priority,
            "api_key": self.clickup_api_key,
            "workspace_id": self.clickup_workspace_id,
        })

    # ── Generic webhook ingest ────────────────────────────────────────

    def ingest_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Forward arbitrary data from an n8n webhook into the platform."""
        return self._post("/webhook/ingest", payload)

    # ── Programmatic API Methods (v2.0) ──────────────────────────────

    def list_workflows(self, limit: int = 50, active_only: bool = False) -> Dict[str, Any]:
        """List all n8n workflows with optional filtering."""
        params = f"?limit={limit}"
        if active_only:
            params += "&active=true"
        
        result = self._get(f"/api/v1/workflows{params}")
        
        if result.get("error"):
            log.error(f"Failed to list workflows: {result['error']}")
        
        return result

    def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific workflow."""
        result = self._get(f"/api/v1/workflows/{workflow_id}")
        
        if result.get("error"):
            log.error(f"Failed to get workflow {workflow_id}: {result['error']}")
        
        return result

    def execute_workflow(self, workflow_id: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a workflow with optional input data."""
        payload = {"data": data or {}}
        
        result = self._post(f"/api/v1/workflows/{workflow_id}/execute", payload)
        
        if result.get("error"):
            log.error(f"Failed to execute workflow {workflow_id}: {result['error']}")
        else:
            log.info(f"Executed workflow {workflow_id}: {result.get('id')}")
        
        return result

    def update_workflow_status(self, workflow_id: str, active: bool) -> Dict[str, Any]:
        """Enable or disable a workflow."""
        action = "activate" if active else "deactivate"
        result = self._post(f"/api/v1/workflows/{workflow_id}/{action}", {})
        
        if result.get("error"):
            log.error(f"Failed to update workflow {workflow_id}: {result['error']}")
        else:
            status = "enabled" if active else "disabled"
            log.info(f"Workflow {workflow_id} {status}")
        
        return result

    def list_executions(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List workflow executions with optional filtering.
        
        Args:
            workflow_id: Filter by workflow ID
            status: Filter by status ('success', 'error', 'waiting')
            limit: Max results (default 50)
            offset: Pagination offset (default 0)
        """
        params = f"?limit={limit}"
        
        if workflow_id:
            params += f"&workflowId={workflow_id}"
        if status:
            params += f"&status={status}"
        
        result = self._get(f"/api/v1/executions{params}")
        
        if result.get("error"):
            log.error(f"Failed to list executions: {result['error']}")
        
        return result

    def get_execution(self, execution_id: str) -> Dict[str, Any]:
        """Get detailed information about a workflow execution."""
        result = self._get(f"/api/v1/executions/{execution_id}")
        
        if result.get("error"):
            log.error(f"Failed to get execution {execution_id}: {result['error']}")
        
        return result

    def trigger_webhook(self, webhook_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger a webhook directly (public, no API key needed)."""
        url = f"{self.base_url.rstrip('/')}/webhook/{webhook_id}"
        
        try:
            r = httpx.post(url, json=data, timeout=self.timeout)
            r.raise_for_status()
            return r.json() if r.text else {"status": "success"}
        except httpx.HTTPStatusError as exc:
            log.error("Webhook trigger failed %s: %s", exc.response.status_code, exc.response.text[:200])
            return {"error": str(exc), "status_code": exc.response.status_code}
        except Exception as exc:
            log.error("Webhook trigger failed: %s", exc)
            return {"error": str(exc)}

    def test_workflow_trigger(self, workflow_id: str, test_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Test a workflow trigger with sample data."""
        payload = {"data": test_data or {}}
        
        result = self._post(f"/api/v1/workflows/{workflow_id}/test", payload)
        
        if result.get("error"):
            log.error(f"Workflow test failed: {result['error']}")
        else:
            log.info(f"Workflow test successful")
        
        return result

    def get_workflow_statistics(self, workflow_id: str) -> Dict[str, Any]:
        """Get execution statistics for a workflow."""
        result = self._get(f"/api/v1/workflows/{workflow_id}/stats")
        
        if result.get("error"):
            log.warning(f"Could not get workflow stats: {result['error']}")
        
        return result

    def trigger_webhook_async(self, webhook_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger webhook asynchronously (fire-and-forget)."""
        import threading
        
        def _trigger():
            try:
                self.trigger_webhook(webhook_id, data)
            except Exception as e:
                log.error(f"Async webhook trigger failed: {e}")
        
        thread = threading.Thread(target=_trigger, daemon=True)
        thread.start()
        
        return {"status": "queued", "webhook_id": webhook_id}

    def batch_trigger_webhook(self, webhook_id: str, data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Trigger webhook multiple times with different data."""
        results = []
        
        for data in data_list:
            result = self.trigger_webhook(webhook_id, data)
            results.append(result)
        
        log.info(f"Triggered webhook {webhook_id} {len(data_list)} times")
        return results

    def wait_for_execution(
        self,
        execution_id: str,
        timeout: int = 30,
        poll_interval: int = 2,
    ) -> Dict[str, Any]:
        """Wait for execution to complete with timeout.
        
        Args:
            execution_id: Execution ID to wait for
            timeout: Maximum seconds to wait (default 30)
            poll_interval: Seconds between polls (default 2)
        """
        import time
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            result = self.get_execution(execution_id)
            
            if result.get("error"):
                return result
            
            status = result.get("status")
            
            if status in ["success", "error", "crashed"]:
                log.info(f"Execution {execution_id} completed with status: {status}")
                return result
            
            time.sleep(poll_interval)
        
        return {
            "error": f"Execution timeout after {timeout}s",
            "execution_id": execution_id,
            "status": "timeout"
        }

    # ── Introspection ─────────────────────────────────────────────────

    @staticmethod
    def list_allowed_nodes() -> List[Dict[str, str]]:
        lang = I18N.lang()
        out: List[Dict[str, str]] = []
        for key, info in ALLOWED_NODES.items():
            out.append({
                "key": key,
                "node": info["node"],
                "account": info["account"],
                "description": info[f"desc_{lang}"],
            })
        return out


# ── Convenience singleton ─────────────────────────────────────────────────
n8n = N8NClient()
