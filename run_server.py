import uvicorn
import os

os.environ['POSTGRES_URL'] = 'postgresql://neondb_owner:***ROTATED-SECRET***@ep-lively-lake-agvifdsa.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require'
os.environ['WEBHOOK_SECRET'] = '***ROTATED-SECRET***'

from api import app
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8004, log_level="debug")
