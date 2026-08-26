"""StreamPulse API tests — offline (health, routes, real classifier wired)."""
import sys
from pathlib import Path

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
    r = client.get("/pipeline/status")
    assert r.status_code == 200

    # When REQUIRE_INTERNAL_TOKEN is true
    monkeypatch.setenv("REQUIRE_INTERNAL_TOKEN", "true")
    monkeypatch.setenv("INTERNAL_TOKEN", "test-secret-token")

    # Missing token -> 403
    r_missing = client.get("/pipeline/status")
    assert r_missing.status_code == 403
    assert r_missing.json()["detail"] == "Missing or invalid X-Internal-Token"

    # Invalid token -> 403
    r_invalid = client.get("/pipeline/status", headers={"X-Internal-Token": "wrong"})
    assert r_invalid.status_code == 403

    # Valid token -> 200
    r_valid = client.get("/pipeline/status", headers={"X-Internal-Token": "test-secret-token"})
    assert r_valid.status_code == 200
