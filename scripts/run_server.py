import uvicorn
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from api import app
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8004, log_level="debug")
