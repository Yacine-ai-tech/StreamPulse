import os
os.environ['POSTGRES_URL'] = 'postgresql://neondb_owner:npg_VygSEAe9Fx2p@ep-lively-lake-agvifdsa.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require'
from core.config import settings
settings.POSTGRES_URL = os.environ['POSTGRES_URL']
from store import update_ingestion_log

print("Testing update_ingestion_log on ID 37")
try:
    update_ingestion_log(37, "error", error="test error")
    print("Success!")
except Exception as e:
    import logging; logging.error(f'Error: {e}', exc_info=True)
    print(f"FAILED: {type(e).__name__}: {e}")
