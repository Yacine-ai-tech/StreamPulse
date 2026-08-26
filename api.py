"""
StreamPulse API — Real-time multi-source data pipeline.
"""
from __future__ import annotations
import base64
import hmac
import os as _os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import time
import os
import threading
import uuid as _uuid

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
    get_ingestion_row,
    get_pipeline_history,
    init_db,
    log_data_ingestion,
    store_kpi_metrics,
    store_stats,
    update_ingestion_log,
)

# Import optional storage backends
try:
    from storage import get_vector_cache, get_analytics_engine
    _storage_available = True
except ImportError:
    _storage_available = False

log = get_logger(__name__)

app = FastAPI(title="StreamPulse", version="0.1.0",
              description="Real-time business data pipeline.")

# Where the anonymous startup ping goes when the deployer hasn't set TELEMETRY_URL.
# Telemetry is ON BY DEFAULT and documented in TELEMETRY.md; TELEMETRY_OPT_OUT=true
# disables it completely, and setting TELEMETRY_URL="" also disables it.
DEFAULT_TELEMETRY_URL = "https://gateway.ysiddo-ai-projects.app/telemetry"




def _telemetry_instance_id() -> str:
    """
    A random, locally-generated install ID — NOT derived from MAC address or any other
    hardware fingerprint. Persisted under LOGS_DIR so repeat startups of the same install
    report the same ID (for dedup on the receiving end); delete the file to reset it.
    See TELEMETRY.md for why this is a random UUID rather than a hardware-derived value.
    """
    id_file = os.path.join(settings.LOGS_DIR, ".telemetry_instance_id")
    try:
        if os.path.exists(id_file):
            existing = open(id_file).read().strip()
            if existing:
                return existing
    except Exception:
        pass
    new_id = _uuid.uuid4().hex[:16]
    try:
        with open(id_file, "w") as f:
            f.write(new_id)
    except Exception:
        pass
    return new_id


def _send_telemetry():
    """
    One anonymous startup ping per ~6h to TELEMETRY_URL, so the project can count distinct
    installs. Sends only {service, event, version, instance_id} — no ingested records,
    filenames, IPs, or other request data. See TELEMETRY.md.

    On by default: TELEMETRY_URL defaults to the project's own collector. Disable entirely
    with TELEMETRY_OPT_OUT=true, which returns before any file access or network call is
    made (no DNS lookup, no request), or repoint TELEMETRY_URL at your own collector.
    """
    if os.environ.get("TELEMETRY_OPT_OUT", "").strip().lower() in ("1", "true", "yes"):
        return

    telemetry_url = os.environ.get("TELEMETRY_URL", DEFAULT_TELEMETRY_URL).strip()
    if not telemetry_url:
        return

    lock_file = os.path.join(settings.LOGS_DIR, ".telemetry_last_ping")
    try:
        if os.path.exists(lock_file) and time.time() - os.path.getmtime(lock_file) < 21600:
            return
        with open(lock_file, "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass

    try:
        log.info("Anonymous telemetry ping to %s (set TELEMETRY_OPT_OUT=true to disable).", telemetry_url)
        httpx.post(
            telemetry_url,
            json={
                "service": "StreamPulse",
                "event": "startup",
                "version": app.version,
                "instance_id": _telemetry_instance_id(),
            },
            timeout=2,
        )
    except Exception:
        pass


threading.Thread(target=_send_telemetry, daemon=True).start()
# -------------------------


class InternalTokenMiddleware:
    """Pure-ASGI middleware (not BaseHTTPMiddleware) so it can sit in front of
    StreamingResponse routes (/live/sse) without buffering/bridging their body
    through an extra anyio task. BaseHTTPMiddleware's call_next() wraps the
    downstream response in a task-group-bound task; a long-lived generator
    response (SSE's `while True: yield ...`) makes that task never resolve
    cleanly on early client disconnect, hanging the request. See
    https://github.com/encode/starlette/discussions/1527 for the same class
    of bug upstream — the fix is to not use @app.middleware("http") for
    anything that guards a streaming route."""

    EXEMPT_EXACT = {"/", "/health", "/docs", "/openapi.json", "/api/redoc",
                     "/favicon.png", "/favicon.ico", "/mark.png", "/logo.png"}
    EXEMPT_PREFIX = ("/api/v1/auth/", "/assets/", "/static/")

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope, receive=receive)
        path = request.url.path
        if request.method == "OPTIONS" or path in self.EXEMPT_EXACT or path.startswith(self.EXEMPT_PREFIX):
            return await self.app(scope, receive, send)

        token = (
            request.headers.get("X-StreamPulse-Internal-Token")
            or request.headers.get("X-Internal-Token")
            or request.headers.get("X-OmniIntel-Internal-Token")
            or (request.headers.get("Authorization", "").replace("Bearer ", "") if request.headers.get("Authorization", "").startswith("Bearer ") else "")
        )
        expected_tokens = [
            t for t in (
                _os.environ.get("STREAMPULSE_INTERNAL_TOKEN"),
                _os.environ.get("INTERNAL_TOKEN"),
                _os.environ.get("OMNIINTEL_INTERNAL_TOKEN"),
            ) if t
        ]

        if _os.environ.get("REQUIRE_INTERNAL_TOKEN", "false").lower() == "true":
            if not token or not any(hmac.compare_digest(token, exp) for exp in expected_tokens):
                response = JSONResponse(status_code=403, content={"detail": "Missing or invalid X-Internal-Token"})
                return await response(scope, receive, send)

        return await self.app(scope, receive, send)


app.add_middleware(InternalTokenMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ALLOWED_ORIGINS or ["*"],
                   allow_methods=["*"], allow_headers=["*"])


try:
    _assets_dir = _os.path.join(_os.path.dirname(__file__), "frontend", "dist", "assets")
    if _os.path.exists(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")
except Exception as e:
    log.warning("assets mount failed: %s", e)


@app.get("/", include_in_schema=False)
async def dashboard():
    """Serve the accessible StreamPulse dashboard at the root."""
    import os
    root = os.path.dirname(__file__)
    spa = os.path.join(root, "frontend", "dist", "index.html")
    if os.path.exists(spa):
        return FileResponse(spa)
    return {"service": "streampulse", "docs": "/docs"}

try:
    init_db()
except Exception as e:
    log.warning("init_db at import failed: %s", e)


@app.on_event("startup")
async def startup_event():
    import threading
    from connectors.n8n import n8n


# Try to import upgraded classifier; gracefully degrade
try:
    from pipeline.classifier import classify  # type: ignore
except Exception:
    def classify(content: str, fast_only: bool = False) -> Dict[str, Any]:  # type: ignore
        c = (content or "").lower()
        if any(k in c for k in ("revenue", "profit", "ebitda")):
            return {"domain": "Finance", "confidence": 0.8}
        if any(k in c for k in ("customer", "mrr", "arr")):
            return {"domain": "Growth", "confidence": 0.7}
        if any(k in c for k in ("headcount", "hr", "turnover")):
            return {"domain": "People", "confidence": 0.7}
        if any(k in c for k in ("uptime", "incident")):
            return {"domain": "IT_Ops", "confidence": 0.7}
        if any(k in c for k in ("carbon", "esg")):
            return {"domain": "ESG", "confidence": 0.7}
        return {"domain": "Operations", "confidence": 0.5}


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket clients & Message Broker (Redis/Kafka)
# ─────────────────────────────────────────────────────────────────────────────

_clients: Set[WebSocket] = set()

_MESSAGE_BROKER = os.getenv("MESSAGE_BROKER", "redis").lower()
_REDIS_URL = os.getenv("REDIS_URL")
_KAFKA_BROKER_URL = os.getenv("KAFKA_BROKER_URL")

_redis_pubsub = None
_kafka_producer = None
_kafka_consumer = None


async def _setup_broker():
    if _MESSAGE_BROKER == "redis":
        await _setup_redis()
    elif _MESSAGE_BROKER == "kafka":
        await _setup_kafka()
    else:
        log.warning(f"Unknown MESSAGE_BROKER: {_MESSAGE_BROKER}")


async def _setup_redis():
    global _redis_pubsub
    if not _REDIS_URL:
        log.warning("MESSAGE_BROKER=redis but REDIS_URL is not set")
        return
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(_REDIS_URL)
        _redis_pubsub = r.pubsub()
        await _redis_pubsub.subscribe("streampulse_ingest")
        log.info("✅ Redis PubSub broker enabled for multi-node broadcast")

        async def _listen():
            async for message in _redis_pubsub.listen():
                if message["type"] == "message":
                    payload = json.loads(message["data"])
                    await _local_broadcast(payload)

        asyncio.create_task(_listen())
    except Exception as e:
        log.warning(f"Failed to setup Redis broker: {e}")


async def _setup_kafka():
    global _kafka_producer, _kafka_consumer
    if not _KAFKA_BROKER_URL:
        log.warning("MESSAGE_BROKER=kafka but KAFKA_BROKER_URL is not set")
        return
    try:
        from aiokafka import AIOKafkaProducer, AIOKafkaConsumer  # type: ignore
        _kafka_producer = AIOKafkaProducer(bootstrap_servers=_KAFKA_BROKER_URL)
        await _kafka_producer.start()

        _kafka_consumer = AIOKafkaConsumer(
            "streampulse_ingest",
            bootstrap_servers=_KAFKA_BROKER_URL,
            group_id="streampulse-group"
        )
        await _kafka_consumer.start()
        log.info("✅ Kafka broker enabled for multi-node broadcast")

        async def _listen():
            async for msg in _kafka_consumer:
                payload = json.loads(msg.value.decode("utf-8"))
                await _local_broadcast(payload)

        asyncio.create_task(_listen())
    except Exception as e:
        log.warning(f"Failed to setup Kafka broker: {e}")


async def _local_broadcast(payload: Dict[str, Any]) -> None:
    dead: List[WebSocket] = []
    for ws in list(_clients):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _clients.discard(ws)


async def _broadcast(payload: Dict[str, Any]) -> None:
    # Always broadcast locally
    await _local_broadcast(payload)

    msg_str = json.dumps(payload)

    if _MESSAGE_BROKER == "redis" and _REDIS_URL:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(_REDIS_URL)
            await r.publish("streampulse_ingest", msg_str)
        except Exception as e:
            log.warning(f"Redis publish failed: {e}")

    elif _MESSAGE_BROKER == "kafka" and _kafka_producer:
        try:
            await _kafka_producer.send_and_wait("streampulse_ingest", msg_str.encode("utf-8"))
        except Exception as e:
            log.warning(f"Kafka publish failed: {e}")


@app.on_event("startup")
async def startup_broker():
    await _setup_broker()


async def _dispatch_external_webhook(records: List[Dict[str, Any]]) -> None:
    """Forward classified records to an external system (e.g. IntelAI) enforcing strict schema."""
    if not settings.EXTERNAL_WEBHOOK_URL:
        return

    import httpx
    # Wrap the records exactly as IntelAI (or any generic strict system) expects
    payload = {
        "source": "StreamPulse",
        "schema_type": settings.EXTERNAL_WEBHOOK_SCHEMA_TYPE,
        "data": records
    }

    # Pass along the internal mesh token if targeting another internal microservice
    import os
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Token": os.environ.get("INTERNAL_TOKEN", "")
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(settings.EXTERNAL_WEBHOOK_URL, json=payload, headers=headers)
            if resp.status_code >= 400:
                log.error(f"External Webhook Failed: {resp.status_code} - {resp.text}")
            else:
                log.info(f"Successfully pushed {len(records)} records to {settings.EXTERNAL_WEBHOOK_URL}")
    except Exception as e:
        log.error(f"External Webhook Dispatch Error: {e}")


# ─────────────────────────────────────────────────────────────────────────────

class IngestJsonRequest(BaseModel):
    records: List[Dict[str, Any]]
    source: str = "manual_json"


_last_db_check = 0.0
_cached_db_status = "ok"


@app.get("/health")
async def health() -> Dict[str, Any]:
    global _last_db_check, _cached_db_status
    import time
    now = time.time()
    if now - _last_db_check > 10:
        try:
            from store import _conn
            with _conn() as conn:
                conn.execute("SELECT 1")
            _cached_db_status = "ok"
        except Exception as e:
            _cached_db_status = f"error: {str(e)}"
        _last_db_check = now
    return {"status": "ok" if _cached_db_status == "ok" else "degraded", "service": "streampulse", "version": "0.1.0", "database": _cached_db_status}


@app.post("/ingest/json")
async def ingest_json(
    req: IngestJsonRequest,
    x_demo_session_id: Optional[str] = Header(default=None, alias="X-Demo-Session-Id"),
) -> Dict[str, Any]:
    """x_demo_session_id: the visitor's browser id (if any). None for genuine external
    webhooks/n8n/CRM sources, whose data stays visible to everyone by design — see
    store_kpi_metrics for the anonymous demo-isolation rationale."""
    # payload stored (truncated in store) so events can be inspected and replayed
    log_id = log_data_ingestion(req.source, "started", records=len(req.records), payload=req.records[:20], owner_session_id=x_demo_session_id)

    async def _classify_record(r):
        text_to_classify = r.get("metric", "") + " " + str(r.get("raw", ""))
        c = await asyncio.to_thread(classify, text_to_classify)
        return {"source": req.source, **r, **c}

    try:
        enriched = await asyncio.gather(*[_classify_record(r) for r in req.records])
        inserted = store_kpi_metrics(enriched, owner_session_id=x_demo_session_id)
    except Exception as e:
        update_ingestion_log(log_id, "failed", error=str(e)[:2000])
        raise
    update_ingestion_log(log_id, "completed", records=inserted)

    # Broadcast to local WebSockets
    asyncio.create_task(_broadcast({"event": "ingest", "source": req.source, "records": enriched}))

    # Dispatch Outbound Webhook to IntelAI or custom CRM
    asyncio.create_task(_dispatch_external_webhook(enriched))

    return {"source": req.source, "records_in": len(req.records), "records_inserted": inserted, "log_id": log_id}


@app.post("/ingest/csv")
async def ingest_csv(
    file: UploadFile = File(...),
    source: str = Form("csv_upload"),
    x_demo_session_id: Optional[str] = Header(default=None, alias="X-Demo-Session-Id"),
) -> Dict[str, Any]:
    import csv
    import io
    content = await file.read()
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8"))))
    return await ingest_json(IngestJsonRequest(records=rows, source=source), x_demo_session_id=x_demo_session_id)


@app.post("/ingest/email")
async def ingest_email(
    payload: Dict[str, Any],
    x_demo_session_id: Optional[str] = Header(default=None, alias="X-Demo-Session-Id"),
) -> Dict[str, Any]:
    """Accept a Gmail-style payload and treat as a single record."""
    records = [{"source": "email", "raw": payload, "metric": payload.get("subject", "")}]
    return await ingest_json(IngestJsonRequest(records=records, source="email"), x_demo_session_id=x_demo_session_id)


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
    # No X-Demo-Session-Id here on purpose: real external webhook callers aren't browsers,
    # so their data stays globally visible — that's the point of a public ingestion demo.
    return await ingest_json(IngestJsonRequest(records=list(records), source=source_name), x_demo_session_id=None)


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
                        # Send the shared internal token if this deployment sets one — DocIntel's
                        # own internal-token gate exempts /classify-image, but the header costs
                        # nothing when unset and keeps this working if that exemption ever changes.
                        vision_headers = {}
                        internal_token = _os.environ.get("INTERNAL_TOKEN", "")
                        if internal_token:
                            vision_headers["X-Internal-Token"] = internal_token
                        resp = await client.post(f"{settings.DOCINTEL_URL}/classify-image", files=files, data=data, headers=vision_headers)
                        r["image_category"] = resp.json().get("category")
                        r["image_confidence"] = resp.json().get("confidence")
                    except Exception as e:
                        log.warning("vision compose failed: %s", e)
                enriched.append(dict(r))
        return await ingest_json(IngestJsonRequest(records=enriched, source=source_name), x_demo_session_id=None)
    except Exception as e:
        log.warning("with-vision processing failed: %s", e)
        raise HTTPException(status_code=400, detail="invalid_payload")


@app.get("/pipeline/status")
async def pipeline_status(
    x_demo_session_id: Optional[str] = Header(default=None, alias="X-Demo-Session-Id"),
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"status": "ok", "connected_clients": len(_clients)}
    try:
        out.update(store_stats(session_id=x_demo_session_id))
    except Exception as e:
        log.warning("store_stats failed: %s", e)
    return out


@app.post("/pipeline/replay/{log_id}")
async def pipeline_replay(
    log_id: int,
    x_demo_session_id: Optional[str] = Header(default=None, alias="X-Demo-Session-Id"),
) -> Dict[str, Any]:
    """Re-ingest the stored payload of a past ingestion event (real replay). Ownership is
    enforced in get_ingestion_row: a log_id from a different visitor's session 404s instead
    of replaying their stored payload — this used to be replayable by anyone who guessed a
    sequential id, regardless of who ingested it."""
    row = get_ingestion_row(log_id, session_id=x_demo_session_id)
    if not row:
        raise HTTPException(status_code=404, detail="event_not_found")
    try:
        records = json.loads(row.get("payload") or "null")
    except json.JSONDecodeError:
        records = None
    if not records:
        raise HTTPException(status_code=422, detail="no_stored_payload")
    return await ingest_json(IngestJsonRequest(records=records, source=f"replay:{row['source']}"), x_demo_session_id=x_demo_session_id)


@app.get("/pipeline/history")
async def pipeline_history(
    limit: int = 100,
    x_demo_session_id: Optional[str] = Header(default=None, alias="X-Demo-Session-Id"),
) -> Dict[str, Any]:
    return {"history": get_pipeline_history(limit=limit, session_id=x_demo_session_id)}


@app.websocket("/live")
async def ws_live(ws: WebSocket):
    await ws.accept()
    _clients.add(ws)
    try:
        import asyncio
        import json
        from datetime import datetime, timezone
        while True:
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                try:
                    await ws.send_text(json.dumps({"type": "ping", "timestamp": datetime.now(timezone.utc).isoformat()}))
                except Exception:
                    break
    except WebSocketDisconnect:
        _clients.discard(ws)


@app.get("/live/sse")
async def live_sse(request: Request, session_id: Optional[str] = None) -> StreamingResponse:
    """Server-Sent Events — simpler one-way push for clients that can't use WebSocket.
    Browsers' native EventSource can't set custom headers, so this accepts the demo
    session id as a query param; the header still wins if a client sends both."""
    session_id = request.headers.get("X-Demo-Session-Id") or session_id

    async def gen():
        while True:
            if await request.is_disconnected():
                break
            recent = get_pipeline_history(limit=5, session_id=session_id)
            yield f"data: {json.dumps(recent)}\n\n"
            await asyncio.sleep(5)
    return StreamingResponse(gen(), media_type="text/event-stream")


# ── Analytics & Storage Endpoints ───────────────────────

@app.get("/analytics/cache-stats")
async def get_cache_stats() -> Dict[str, Any]:
    """Get classification cache performance statistics."""
    try:
        from pipeline.classifier import get_cache_stats
        return get_cache_stats()
    except Exception as e:
        log.error("Failed to get cache stats: %s", e)
        return {"error": str(e), "cache_hits": 0, "cache_misses": 0, "hit_rate": 0.0}

@app.get("/analytics/storage-stats")
async def get_storage_stats() -> Dict[str, Any]:
    """Get storage backend statistics (pgvector, DuckDB)."""
    stats = {}
    
    if _storage_available:
        try:
            from storage import get_vector_cache, get_analytics_engine
            
            vector_cache = get_vector_cache()
            stats["vector_cache"] = vector_cache.get_stats()
            
            analytics_engine = get_analytics_engine()
            stats["analytics"] = analytics_engine.get_stats()
        except Exception as e:
            log.error("Failed to get storage stats: %s", e)
            stats["error"] = str(e)
    else:
        stats["storage_available"] = False
    
    return stats

@app.get("/analytics/domain-summary")
async def get_domain_summary(
    days: int = 7,
    x_demo_session_id: Optional[str] = Header(default=None, alias="X-Demo-Session-Id"),
) -> Dict[str, Any]:
    """Get domain-level summary using DuckDB analytics. Scoped the same way
    /pipeline/history etc. are -- see x_demo_session_id's docstring there."""
    if not _storage_available:
        return {"error": "Storage backend not available"}

    try:
        from storage import get_analytics_engine
        analytics = get_analytics_engine()
        df = analytics.get_domain_summary(days=days, session_id=x_demo_session_id)
        return {
            "data": df.to_dict(orient="records"),
            "count": len(df),
            "period_days": days
        }
    except Exception as e:
        log.error("Failed to get domain summary: %s", e)
        return {"error": str(e)}

@app.get("/analytics/classification-trends")
async def get_classification_trends(
    days: int = 30,
    x_demo_session_id: Optional[str] = Header(default=None, alias="X-Demo-Session-Id"),
) -> Dict[str, Any]:
    """Get classification method trends over time. See get_domain_summary for scoping."""
    if not _storage_available:
        return {"error": "Storage backend not available"}

    try:
        from storage import get_analytics_engine
        analytics = get_analytics_engine()
        df = analytics.get_classification_trends(days=days, session_id=x_demo_session_id)
        return {
            "data": df.to_dict(orient="records"),
            "count": len(df),
            "period_days": days
        }
    except Exception as e:
        log.error("Failed to get classification trends: %s", e)
        return {"error": str(e)}

@app.post("/analytics/refresh")
async def refresh_analytics() -> Dict[str, Any]:
    """Refresh analytics data and materialized views."""
    if not _storage_available:
        return {"error": "Storage backend not available"}
    
    try:
        from storage import get_analytics_engine
        analytics = get_analytics_engine()
        
        # Import fresh data from PostgreSQL
        imported = analytics.import_from_postgres()
        
        # Refresh materialized views
        refreshed = analytics.refresh_materialized_views()
        
        return {
            "success": True,
            "records_imported": imported,
            "views_refreshed": refreshed
        }
    except Exception as e:
        log.error("Failed to refresh analytics: %s", e)
        return {"error": str(e), "success": False}


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    """Catch-all so direct navigation, refresh, or a bookmarked/shared link to
    any frontend route (e.g. /analytics, /events, /api-docs) serves the SPA
    instead of a raw 404 -- React Router then resolves the route client-side.
    Declared last so every real API/WS route above still wins.

    Real static files in frontend/dist/ (favicon, logo, sw.js, ...) are
    served directly rather than falling back to index.html for them.
    """
    root = _os.path.dirname(__file__)
    dist = _os.path.realpath(_os.path.join(root, "frontend", "dist"))
    candidate = _os.path.realpath(_os.path.join(dist, full_path))
    if candidate.startswith(dist + _os.sep) and _os.path.isfile(candidate):
        return FileResponse(candidate)
    spa = _os.path.join(dist, "index.html")
    if _os.path.exists(spa):
        return FileResponse(spa)
    raise HTTPException(status_code=404, detail="Not Found")
