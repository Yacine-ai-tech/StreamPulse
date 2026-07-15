from api import ingest_json, IngestJsonRequest
import asyncio

async def test():
    req = IngestJsonRequest(records=[{'period':'','category':'github','metric':'opened','value':0.0,'unit':None,'confidence':0.9,'source':'github'}], source='github')
    res = await ingest_json(req)
    print(res)

asyncio.run(test())
