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
    
    # 1. log_data_ingestion
    from store import log_data_ingestion, store_kpi_metrics, update_ingestion_log
    log_id = log_data_ingestion("github", "started", records=len(records), payload=records[:20])
    
    # 2. classify
    enriched = []
    for r in records:
        r_dict = dict(r)
        r_dict['domain'] = 'Operations'
        r_dict['confidence'] = 0.5
        enriched.append(r_dict)
        
    # 3. store_kpi_metrics
    print("Testing store_kpi_metrics:")
    try:
        inserted = store_kpi_metrics(enriched)
        print(f"Inserted: {inserted}")
    except Exception as e:
        import logging; logging.error(f'Error: {e}', exc_info=True)
        print(f"store_kpi_metrics failed: {type(e).__name__}: {e}")
        
    # 4. update_ingestion_log
    print("Testing update_ingestion_log:")
    try:
        update_ingestion_log(log_id, "completed", records=inserted)
        print("Updated OK")
    except Exception as e:
        import logging; logging.error(f'Error: {e}', exc_info=True)
        print(f"update_ingestion_log failed: {type(e).__name__}: {e}")

asyncio.run(test())
