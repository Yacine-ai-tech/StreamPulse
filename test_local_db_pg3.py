import os
os.environ['POSTGRES_URL'] = 'postgresql://neondb_owner:npg_VygSEAe9Fx2p@ep-lively-lake-agvifdsa.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require'

from core.config import settings
settings.POSTGRES_URL = os.environ['POSTGRES_URL']

import asyncio
from api import ingest_json, IngestJsonRequest
from connectors.webhook_receiver import WebhookReceiver
import json

async def test():
    gh_body = json.loads('{"action":"opened","issue":{"title":"Revenue anomaly alert","body":"Q3 spike detected"},"repository":{"name":"intelai"}}')
    records = WebhookReceiver.parse_payload(gh_body, "github")
    req = IngestJsonRequest(records=list(records), source="github")
    try:
        res = await ingest_json(req)
        print(f"Ingest result: {res}")
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(test())
