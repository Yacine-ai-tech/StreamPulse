import uvicorn
import os

os.environ['POSTGRES_URL'] = 'postgresql://neondb_owner:npg_VygSEAe9Fx2p@ep-lively-lake-agvifdsa.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require'
os.environ['WEBHOOK_SECRET'] = '6e675dc35f02e4cba3813700fc9e66f2edddcee5'

from api import app
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8004, log_level="debug")
