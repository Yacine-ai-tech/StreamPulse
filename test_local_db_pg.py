import asyncio
from api import ingest_json, IngestJsonRequest
from connectors.webhook_receiver import WebhookReceiver
import json

async def test():
    # Keep the real Postgres DB url to reproduce what Render sees exactly
    gh_body = json.loads('{"action":"opened","issue":{"title":"Revenue anomaly alert","body":"Q3 spike detected"},"repository":{"name":"intelai"}}')
    records = WebhookReceiver.parse_payload(gh_body, "github")
    req = IngestJsonRequest(records=list(records), source="github")
    try:
        res = await ingest_json(req)
        print(f"Ingest result: {res}")
    except Exception as e:
        import logging; logging.error(f'Error: {e}', exc_info=True)
        print(f"ERROR: {type(e).__name__}: {e}")

asyncio.run(test())
