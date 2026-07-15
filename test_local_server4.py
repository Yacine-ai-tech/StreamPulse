import uvicorn
import threading
import time
import urllib.request
import json
import ssl
import hmac
import hashlib
import os

os.environ['POSTGRES_URL'] = 'postgresql://neondb_owner:npg_VygSEAe9Fx2p@ep-lively-lake-agvifdsa.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require'
os.environ['WEBHOOK_SECRET'] = '6e675dc35f02e4cba3813700fc9e66f2edddcee5'

def run_server():
    from api import app
    uvicorn.run(app, host="127.0.0.1", port=8004, log_level="debug")

t = threading.Thread(target=run_server, daemon=True)
t.start()

time.sleep(3)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def sign(body_bytes):
    return 'sha256=' + hmac.new('6e675dc35f02e4cba3813700fc9e66f2edddcee5'.encode(), body_bytes, hashlib.sha256).hexdigest()

gh_body = json.dumps({'action':'opened','issue':{'title':'Revenue anomaly alert','body':'Q3 spike detected'},'repository':{'name':'intelai'}}).encode()
req = urllib.request.Request('http://127.0.0.1:8004/webhook/github', data=gh_body,
    headers={'Content-Type':'application/json','X-Signature-256':sign(gh_body),'User-Agent':'x'}, method='POST')
try:
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        r = json.loads(resp.read().decode())
        print(f'✅ /webhook/github (raw GitHub event): 200 {r}')
except urllib.error.HTTPError as e:
    print(f'❌ /webhook/github: {e.code} {e.read().decode()[:200]}')

