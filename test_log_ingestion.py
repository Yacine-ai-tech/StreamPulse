import psycopg, json
url = 'postgresql://neondb_owner:npg_VygSEAe9Fx2p@ep-lively-lake-agvifdsa.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require'
try:
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            records_str = json.dumps([{'source': 'github', 'period': '', 'category': 'github', 'metric': 'opened', 'value': 0.0, 'unit': None, 'confidence': 0.9, 'raw': {'action': 'opened'}}])
            cur.execute("""
                INSERT INTO sp_ingestion_log
                  (source, status, records, error, payload, created_at)
                VALUES (%s, %s, %s, %s, %s, now())
                RETURNING id;
            """, ('github', 'started', 1, None, records_str))
            res = cur.fetchone()
            print(f'✅ Log Insert OK! ID: {res[0]}')
            conn.rollback()
except Exception as e:
    import logging; logging.error(f'Error: {e}', exc_info=True)
    print(f'❌ Log error: {type(e).__name__}: {e}')
