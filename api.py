"""
StreamPulse API — Real-time multi-source data pipeline.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional, Set

import httpx
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from core.config import settings
from core.logger import get_logger
from connectors.webhook_receiver import WebhookReceiver
from store import (
    get_kpi_metrics,
    get_pipeline_history,
    init_db,
    log_data_ingestion,
    store_kpi_metrics,
    update_ingestion_log,
)

log = get_logger(__name__)

app = FastAPI(title="StreamPulse", version="0.1.0",
              description="Real-time business data pipeline.")
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ALLOWED_ORIGINS or ["*"],
                   allow_methods=["*"], allow_headers=["*"])

try:  # browser demo UI (served by the backend, no separate deploy)
    from fastapi.staticfiles import StaticFiles
    app.mount("/demo", StaticFiles(directory="demo", html=True), name="demo")
except RuntimeError:
    log.warning("demo/ directory not found — /demo will not be served")


@app.get("/", include_in_schema=False)
async def dashboard():
    """Serve the accessible StreamPulse dashboard at the root."""
    import os
    root = os.path.dirname(__file__)
    spa = os.path.join(root, "frontend", "dist", "index.html")
    if os.path.exists(spa):
        return FileResponse(spa)
    path = os.path.join(root, "demo", "index.html")
    return FileResponse(path) if os.path.exists(path) else {"service": "streampulse", "docs": "/docs"}

try:
    init_db()
except Exception as e:
    log.warning("init_db at import failed: %s", e)


# Try to import upgraded classifier; gracefully degrade
try:
    from pipeline.classifier import classify  # type: ignore
except Exception:
    def classify(content: str, fast_only: bool = False) -> Dict[str, Any]:  # type: ignore
        c = (content or "").lower()
        if any(k in c for k in ("revenue", "profit", "ebitda")): return {"domain": "Finance", "confidence": 0.8}
        if any(k in c for k in ("customer", "mrr", "arr")): return {"domain": "Growth", "confidence": 0.7}
        if any(k in c for k in ("headcount", "hr", "turnover")): return {"domain": "People", "confidence": 0.7}
        if any(k in c for k in ("uptime", "incident")): return {"domain": "IT_Ops", "confidence": 0.7}
        if any(k in c for k in ("carbon", "esg")): return {"domain": "ESG", "confidence": 0.7}
        return {"domain": "Operations", "confidence": 0.5}


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket clients
# ─────────────────────────────────────────────────────────────────────────────

_clients: Set[WebSocket] = set()


async def _broadcast(payload: Dict[str, Any]) -> None:
    dead: List[WebSocket] = []
    for ws in list(_clients):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _clients.discard(ws)


# ─────────────────────────────────────────────────────────────────────────────

class IngestJsonRequest(BaseModel):
    records: List[Dict[str, Any]]
    source: str = "manual_json"


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "service": "streampulse", "version": "0.1.0"}


@app.post("/ingest/json")
async def ingest_json(req: IngestJsonRequest) -> Dict[str, Any]:
    log_id = log_data_ingestion(req.source, "started", records=len(req.records))
    enriched = []
    for r in req.records:
        c = classify(r.get("metric", "") + " " + str(r.get("raw", "")))
        enriched.append({**r, **c})
    inserted = store_kpi_metrics(enriched)
    update_ingestion_log(log_id, "completed", records=inserted)
    asyncio.create_task(_broadcast({"event": "ingest", "source": req.source, "records": enriched}))
    return {"source": req.source, "records_in": len(req.records), "records_inserted": inserted, "log_id": log_id}


@app.post("/ingest/csv")
async def ingest_csv(file: UploadFile = File(...), source: str = Form("csv_upload")) -> Dict[str, Any]:
    import csv, io
    content = await file.read()
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8"))))
    return await ingest_json(IngestJsonRequest(records=rows, source=source))


@app.post("/ingest/email")
async def ingest_email(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Accept a Gmail-style payload and treat as a single record."""
    records = [{"source": "email", "raw": payload, "metric": payload.get("subject", "")}]
    return await ingest_json(IngestJsonRequest(records=records, source="email"))


@app.post("/webhook/{source_name}")
async def webhook_generic(
    source_name: str,
    request: Request,
    x_signature_256: Optional[str] = Header(default=None, alias="X-Signature-256"),
) -> Dict[str, Any]:
    body = await request.body()
    if not WebhookReceiver.verify_signature(body, x_signature_256 or ""):
        raise HTTPException(status_code=401, detail="invalid_signature")
    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid_json")
    records = WebhookReceiver.parse_payload(payload, source_name)
    return await ingest_json(IngestJsonRequest(records=list(records), source=source_name))


@app.post("/webhook/{source_name}/with-vision")
async def webhook_with_vision(
    source_name: str,
    request: Request,
    x_signature_256: Optional[str] = Header(default=None, alias="X-Signature-256"),
) -> Dict[str, Any]:
    """Compose StreamPulse with DocIntel /classify-image for image-bearing webhooks."""
    body = await request.body()
    if not WebhookReceiver.verify_signature(body, x_signature_256 or ""):
        raise HTTPException(status_code=401, detail="invalid_signature")
    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid_json")

    try:
        records = WebhookReceiver.parse_payload(payload, source_name)
        enriched: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for r in records:
                raw = r.get("raw")
                # image_url lives at the record top level (parse_payload stores the
                # original item under "raw"); tolerate a missing/odd shape gracefully.
                img_url = raw.get("image_url") if isinstance(raw, dict) else None
                if img_url:
                    try:
                        img_bytes = (await client.get(img_url)).content
                        files = {"file": ("img.jpg", img_bytes, "image/jpeg")}
                        data = {"categories": ",".join(["tractor", "lathe", "crane", "forklift", "excavator", "other"])}
                        resp = await client.post(f"{settings.DOCINTEL_URL}/classify-image", files=files, data=data)
                        r["image_category"] = resp.json().get("category")
                        r["image_confidence"] = resp.json().get("confidence")
                    except Exception as e:
                        log.warning("vision compose failed: %s", e)
                enriched.append(dict(r))
        return await ingest_json(IngestJsonRequest(records=enriched, source=source_name))
    except Exception as e:
        log.warning("with-vision processing failed: %s", e)
        raise HTTPException(status_code=400, detail="invalid_payload")


@app.get("/pipeline/status")
async def pipeline_status() -> Dict[str, Any]:
    return {"status": "ok", "connected_clients": len(_clients)}


@app.get("/pipeline/history")
async def pipeline_history(limit: int = 100) -> Dict[str, Any]:
    return {"history": get_pipeline_history(limit=limit)}


@app.websocket("/live")
async def ws_live(ws: WebSocket):
    await ws.accept()
    _clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        _clients.discard(ws)


@app.get("/live/sse")
async def live_sse(request: Request) -> StreamingResponse:
    """Server-Sent Events — simpler one-way push for clients that can't use WebSocket."""
    async def gen():
        while True:
            if await request.is_disconnected():
                break
            recent = get_pipeline_history(limit=5)
            yield f"data: {json.dumps(recent)}\n\n"
            await asyncio.sleep(5)
    return StreamingResponse(gen(), media_type="text/event-stream")


# ─── SPA serving (registered last so every API route above wins) ─────────────
import os as _os
from fastapi.staticfiles import StaticFiles as _StaticFiles

_DIST = _os.path.join(_os.path.dirname(__file__), "frontend", "dist")
if _os.path.isdir(_os.path.join(_DIST, "assets")):
    app.mount("/assets", _StaticFiles(directory=_os.path.join(_DIST, "assets")), name="spa_assets")

    @app.get("/{spa_path:path}", include_in_schema=False)
    async def spa_fallback(spa_path: str):
        candidate = _os.path.join(_DIST, spa_path)
        if spa_path and _os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(_os.path.join(_DIST, "index.html"))
