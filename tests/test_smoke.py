"""Smoke tests for StreamPulse."""
import json
import pytest
from fastapi.testclient import TestClient


def test_imports():
    from core import config, logger
    from connectors.webhook_receiver import WebhookReceiver
    from store import init_db, store_kpi_metrics, get_kpi_metrics
    assert config.settings is not None


def test_app_creates():
    from api import app
    assert app.title == "StreamPulse"


def test_health_endpoint():
    from api import app
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "streampulse"


def test_webhook_signature_verify():
    from connectors.webhook_receiver import WebhookReceiver
    import hmac, hashlib
    secret = 'REDACTED'
    body = b'{"records": []}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert WebhookReceiver.verify_signature(body, sig, secret=secret) is True
    assert WebhookReceiver.verify_signature(body, "sha256=bogus", secret=secret) is False


def test_payload_parser():
    from connectors.webhook_receiver import WebhookReceiver
    out = WebhookReceiver.parse_payload({"records": [{"metric": "revenue", "value": 100}]}, "test")
    assert len(out) == 1
    assert out[0]["source"] == "test"


def test_store_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import store
    store._initialized = False
    from store import store_kpi_metrics, get_kpi_metrics, init_db
    init_db()
    n = store_kpi_metrics([{"period": "2026-05", "category": "Finance", "metric": "revenue", "value": 100, "unit": "USD"}])
    assert n == 1
    rows = get_kpi_metrics(category="Finance")
    assert len(rows) >= 1


def test_ingest_json_endpoint():
    from api import app
    client = TestClient(app)
    r = client.post("/ingest/json", json={"records": [{"metric": "revenue", "value": 1000}], "source": "test"})
    # 200 = success (no auth required)
    # 401/403 = auth required (correct security behavior)
    assert r.status_code in (200, 401, 403), f"Unexpected status: {r.status_code}"
    if r.status_code == 200:
        assert r.json()["records_in"] == 1
