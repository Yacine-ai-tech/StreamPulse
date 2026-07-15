import asyncio
from api import ingest_json, IngestJsonRequest
import logging

logging.basicConfig(level=logging.DEBUG)

async def run():
    req = IngestJsonRequest(records=[{'source': 'github', 'period': '', 'category': 'github', 'metric': 'opened', 'value': 0.0, 'unit': None, 'confidence': 0.9, 'raw': {'action': 'opened', 'issue': {'title': 'Revenue anomaly alert', 'body': 'Q3 spike detected'}, 'repository': {'name': 'intelai'}}}], source="github")
    try:
        res = await ingest_json(req)
        print("Success:", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(run())
