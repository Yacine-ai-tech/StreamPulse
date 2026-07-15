import os
os.environ['POSTGRES_URL'] = 'postgresql://neondb_owner:npg_VygSEAe9Fx2p@ep-lively-lake-agvifdsa.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require'
os.environ['STREAMPULSE_HYBRID_LLM'] = '1'
os.environ['GROQ_API_KEY'] = 'invalid_key'

from core.config import settings
settings.POSTGRES_URL = os.environ['POSTGRES_URL']
settings.GROQ_API_KEY = 'invalid_key'

from fastapi.testclient import TestClient
from api import app
import json

client = TestClient(app)

print("Sending webhook test with INVALID Groq key...")
gh_body = {"action":"opened","issue":{"title":"Revenue anomaly alert","body":"Q3 spike detected"},"repository":{"name":"intelai"}}

import hmac, hashlib
secret = '6e675dc35f02e4cba3813700fc9e66f2edddcee5'
gh_body_str = json.dumps(gh_body)
sig = 'sha256=' + hmac.new(secret.encode(), gh_body_str.encode(), hashlib.sha256).hexdigest()

response = client.post("/webhook/github", content=gh_body_str, headers={"X-Signature-256": sig, "Content-Type": "application/json"})
print(f"Status: {response.status_code}")
print(f"Body: {response.text}")
