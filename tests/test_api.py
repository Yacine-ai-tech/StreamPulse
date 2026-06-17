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
