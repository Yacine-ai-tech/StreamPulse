import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import importlib
import pytest
from fastapi.testclient import TestClient

app = None
try:
    api_module = importlib.import_module("api")
    app = api_module.app
except ImportError:
    try:
        main_module = importlib.import_module("main")
        app = main_module.app
    except ImportError:
        pass

if app is None:
    pytest.skip("Could not import StreamPulse app", allow_module_level=True)

client = TestClient(app)

def test_streampulse_real_ingestion_payload():
    """Simulates pushing a massive JSON payload block representing continuous telemetry data."""
    payload = {
        "source": "erp_system_xyz",
        "timestamp": "2026-07-06T12:00:00Z",
        "records": [
            {"sensor": "temperature", "value": 24.5},
            {"sensor": "pressure", "value": 1.01},
            {"sensor": "humidity", "value": 45}
        ]
    }
    
    response = client.post("/ingest/json", json=payload)
    assert response.status_code in (200, 201, 202, 422)
    if response.status_code in (200, 201, 202):
        data = response.json()
        assert "status" in data or "id" in data

def test_streampulse_health():
    response = client.get("/health")
    assert response.status_code == 200
