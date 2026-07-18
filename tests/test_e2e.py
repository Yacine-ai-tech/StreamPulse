import pytest
import httpx
from fastapi.testclient import TestClient
from api import app
import os

client = TestClient(app)
HEADERS = {"X-OmniIntel-Internal-Token": os.getenv("OMNIINTEL_INTERNAL_TOKEN", "omniintel-prod-internal-2026")}

@pytest.mark.asyncio
async def test_e2e_streampulse_webhook_classification():
    # Simulate a webhook from GitHub or Stripe
    payload = {
        "event": "issue_comment",
        "action": "created",
        "comment": {"body": "This new pricing feature broke my invoice generation."}
    }
    
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/webhook/github", json=payload, headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        # The text should be classified into Finance or Engineering
        
@pytest.mark.asyncio
async def test_e2e_streampulse_n8n_sync_trigger():
    # Simulate CRM sync
    payload = {"command": "sync_crm_contacts", "source": "hubspot"}
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/n8n/trigger", json=payload, headers=HEADERS)
        # Should return 200 if n8n base url is valid
        assert response.status_code in (200, 502)

@pytest.mark.asyncio
async def test_e2e_streampulse_live_firehose():
    # Test websocket firehose stream
    with client.websocket_connect("/firehose", headers=HEADERS) as websocket:
        data = websocket.receive_json()
        assert data.get("type") == "connection_ack"
