"""StreamPulse API tests — offline (health, routes, real classifier wired)."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _client():
    from api import app
    return TestClient(app)


def test_health():
    r = _client().get("/health")
    assert r.status_code == 200 and r.json()["service"] == "streampulse"


def test_routes_registered():
    from api import app
    paths = {r.path for r in app.routes}
    for p in ("/ingest/json", "/ingest/csv", "/webhook/{source_name}",
              "/webhook/{source_name}/with-vision", "/pipeline/status", "/live/sse"):
        assert p in paths, p


def test_real_classifier_is_wired():
    # The non-degraded classifier must import (integrations made optional).
    import importlib
    import api
    importlib.reload(api)
    from pipeline.classifier import classify
    assert classify("revenue ebitda margin")["domain"] == "Finance"


def test_internal_token_auth(monkeypatch):
    from api import app
    client = TestClient(app)

    # When REQUIRE_INTERNAL_TOKEN is false (default)
    monkeypatch.setenv("REQUIRE_INTERNAL_TOKEN", "false")
    r = client.get("/pipeline/status?session_id=visitor-test")
    assert r.status_code == 200

    # When REQUIRE_INTERNAL_TOKEN is true
    monkeypatch.setenv("REQUIRE_INTERNAL_TOKEN", "true")
    monkeypatch.setenv("INTERNAL_TOKEN", "test-secret-token")

    # Missing token -> 403
    r_missing = client.get("/pipeline/status?session_id=visitor-test")
    assert r_missing.status_code == 403
    assert r_missing.json()["detail"] == "Missing or invalid X-Internal-Token"

    # Invalid token -> 403
    r_invalid = client.get("/pipeline/status?session_id=visitor-test", headers={"X-Internal-Token": "wrong"})
    assert r_invalid.status_code == 403

    # Valid token -> 200
    r_valid = client.get("/pipeline/status?session_id=visitor-test", headers={"X-Internal-Token": "test-secret-token"})
    assert r_valid.status_code == 200


def test_pipeline_status_does_not_expose_global_counters(monkeypatch):
    monkeypatch.setenv("REQUIRE_INTERNAL_TOKEN", "false")
    client = _client()

    assert client.get("/pipeline/status").status_code == 401
    assert client.get("/pipeline/status?session_id=*").status_code == 403


def test_pipeline_status_cannot_opt_into_global_seed_stats(monkeypatch):
    import api

    monkeypatch.setenv("REQUIRE_INTERNAL_TOKEN", "false")
    captured = {}
    monkeypatch.setattr(api, "store_stats", lambda **kwargs: captured.update(kwargs) or {})

    response = _client().get("/pipeline/status?session_id=visitor-test&include_seed=true")

    assert response.status_code == 200
    assert captured == {"session_id": "visitor-test", "include_seed": False}


def test_pipeline_history_requires_visitor_session(monkeypatch):
    monkeypatch.setenv("REQUIRE_INTERNAL_TOKEN", "false")
    client = _client()

    assert client.get("/pipeline/history").status_code == 401
    assert client.get("/pipeline/history?session_id=*").status_code == 403


def test_pipeline_history_admin_is_explicit(monkeypatch):
    import api

    monkeypatch.setenv("ADMIN_TOKEN", "admin-test-token")
    monkeypatch.setattr(api, "get_pipeline_history", lambda **kwargs: [kwargs])
    response = _client().get(
        "/pipeline/history?session_id=*",
        headers={"X-Admin-Token": "admin-test-token"},
    )

    assert response.status_code == 200
    assert response.json()["history"][0]["is_admin"] is True


def test_pipeline_replay_requires_session_or_admin(monkeypatch):
    monkeypatch.setenv("REQUIRE_INTERNAL_TOKEN", "false")
    response = _client().post("/pipeline/replay/1")

    assert response.status_code == 401
    assert response.json()["detail"] == "visitor_session_required"


@pytest.mark.parametrize(
    ("path", "request_kwargs"),
    [
        ("/ingest/json", {"json": {"records": [{"metric": "revenue"}], "source": "test"}}),
        ("/ingest/csv", {"data": {"source": "test"}, "files": {"file": ("records.csv", "metric,value\nrevenue,1", "text/csv")}}),
        ("/ingest/email", {"json": {"subject": "test"}}),
    ],
)
def test_global_ingestion_requires_service_token(monkeypatch, path, request_kwargs):
    monkeypatch.setenv("REQUIRE_INTERNAL_TOKEN", "false")
    for name in ("STREAMPULSE_INTERNAL_TOKEN", "INTERNAL_TOKEN", "OMNIINTEL_INTERNAL_TOKEN"):
        monkeypatch.delenv(name, raising=False)

    response = _client().post(path, **request_kwargs)

    assert response.status_code == 401
    assert response.json()["detail"] == "internal_token_required_for_global_ingestion"


@pytest.mark.parametrize(
    ("path", "request_kwargs"),
    [
        ("/ingest/json", {"json": {"records": [{"metric": "revenue"}], "source": "test"}}),
        ("/ingest/csv", {"data": {"source": "test"}, "files": {"file": ("records.csv", "metric,value\nrevenue,1", "text/csv")}}),
        ("/ingest/email", {"json": {"subject": "test"}}),
    ],
)
def test_service_token_allows_global_ingestion(monkeypatch, path, request_kwargs):
    import api

    monkeypatch.setenv("REQUIRE_INTERNAL_TOKEN", "false")
    monkeypatch.setenv("STREAMPULSE_INTERNAL_TOKEN", "service-test-token")
    monkeypatch.setattr(api, "_ingest_records", AsyncMock(return_value={"records_inserted": 1}))

    response = _client().post(
        path,
        headers={"X-StreamPulse-Internal-Token": "service-test-token"},
        **request_kwargs,
    )

    assert response.status_code == 200


def test_demo_session_ingestion_does_not_require_service_token(monkeypatch):
    import api

    monkeypatch.setenv("REQUIRE_INTERNAL_TOKEN", "false")
    for name in ("STREAMPULSE_INTERNAL_TOKEN", "INTERNAL_TOKEN", "OMNIINTEL_INTERNAL_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    ingest = AsyncMock(return_value={"records_inserted": 1})
    monkeypatch.setattr(api, "_ingest_records", ingest)

    response = _client().post(
        "/ingest/json",
        json={"records": [{"metric": "revenue"}], "source": "test"},
        headers={"X-Demo-Session-Id": "visitor-test"},
    )

    assert response.status_code == 200
    assert ingest.await_args.args[1] == "visitor-test"


def test_demo_wildcard_session_cannot_create_global_records(monkeypatch):
    monkeypatch.setenv("REQUIRE_INTERNAL_TOKEN", "false")

    response = _client().post(
        "/ingest/json",
        json={"records": [{"metric": "revenue"}], "source": "test"},
        headers={"X-Demo-Session-Id": "*"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "admin_required_for_unscoped_access"


@pytest.mark.asyncio
async def test_live_broadcast_is_scoped_to_owner_session(monkeypatch):
    import api

    class RecordingSocket:
        def __init__(self):
            self.messages = []

        async def send_json(self, payload):
            self.messages.append(payload)

    owner = RecordingSocket()
    other = RecordingSocket()
    monkeypatch.setattr(api, "_clients", {owner, other})
    monkeypatch.setattr(api, "_client_sessions", {owner: "visitor-a", other: "visitor-b"})

    await api._local_broadcast({
        "event": "ingest",
        "records": [{"metric": "revenue"}],
        "_owner_session_id": "visitor-a",
    })
    await api._local_broadcast({
        "event": "ingest",
        "records": [{"metric": "webhook"}],
        "_owner_session_id": None,
    })

    assert owner.messages == [
        {"event": "ingest", "records": [{"metric": "revenue"}]},
        {"event": "ingest", "records": [{"metric": "webhook"}]},
    ]
    assert other.messages == [{"event": "ingest", "records": [{"metric": "webhook"}]}]


def test_live_websocket_requires_demo_session():
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as disconnected:
        with _client().websocket_connect("/live"):
            pass

    assert disconnected.value.code == 4401


def test_vision_webhook_accepts_internal_token_or_signature(monkeypatch):
    monkeypatch.setenv("REQUIRE_INTERNAL_TOKEN", "true")
    monkeypatch.setenv("INTERNAL_TOKEN", "test-secret-token")
    client = _client()
    body = b"{}"

    # Wrong token never reaches the route (global middleware).
    assert client.post("/webhook/demo/with-vision", content=body,
                       headers={"X-Internal-Token": "wrong"}).status_code == 403

    # A valid internal token passes authentication without any signature.
    ok = client.post("/webhook/demo/with-vision", content=body,
                     headers={"X-OmniIntel-Internal-Token": "test-secret-token"})
    assert ok.status_code not in (401, 403)

    # With the middleware relaxed, an unsigned request without a token is refused by the route.
    monkeypatch.setenv("REQUIRE_INTERNAL_TOKEN", "false")
    assert client.post("/webhook/demo/with-vision", content=body).status_code == 401


def test_internal_pipeline_status_requires_internal_token(monkeypatch):
    monkeypatch.setenv("REQUIRE_INTERNAL_TOKEN", "false")
    monkeypatch.setenv("INTERNAL_TOKEN", "test-secret-token")
    client = _client()
    assert client.get("/internal/pipeline/status").status_code == 403
    assert client.get("/internal/pipeline/status",
                      headers={"X-Internal-Token": "wrong"}).status_code == 403
    ok = client.get("/internal/pipeline/status",
                    headers={"X-Internal-Token": "test-secret-token"})
    assert ok.status_code == 200 and ok.json()["status"] == "ok"


def test_downstream_calls_never_carry_this_services_own_token(monkeypatch):
    import inspect
    import api
    src = inspect.getsource(api)
    # Neither outgoing path may read the service's own INTERNAL_TOKEN to forward it.
    assert 'vision_headers["X-Internal-Token"]' not in src
    assert '"X-Internal-Token": os.environ.get("INTERNAL_TOKEN"' not in src
    assert "DOCINTEL_INTERNAL_TOKEN" in src and "EXTERNAL_WEBHOOK_TOKEN" in src


def test_ingest_response_reports_classification(client=None):
    from fastapi.testclient import TestClient
    import api as api_mod

    c = TestClient(api_mod.app)
    headers = {"X-Demo-Session-Id": "audit-classification-session"}
    r = c.post("/ingest/json", json={"source": "audit", "records": [
        {"metric": "Revenue", "value": 12.5, "unit": "USD"},
    ]}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["records_in"] == 1
    assert body["classification"]["by_domain"], body
    assert len(body["classification"]["records"]) == 1


def test_analytics_summary_uses_primary_store_when_engine_disabled(monkeypatch):
    from fastapi.testclient import TestClient
    import api as api_mod

    monkeypatch.setattr(api_mod.settings, "ENABLE_DUCKDB", False, raising=False)
    c = TestClient(api_mod.app)
    headers = {"X-Demo-Session-Id": "audit-analytics-session"}
    c.post("/ingest/json", json={"source": "audit", "records": [
        {"metric": "Headcount", "value": 41, "unit": "people"},
    ]}, headers=headers)
    r = c.get("/analytics/domain-summary?days=7", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["engine"] == "primary_store"
    assert body["count"] >= 1 and body["data"][0]["record_count"] >= 1
