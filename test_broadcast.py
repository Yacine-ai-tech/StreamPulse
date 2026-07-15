import asyncio
from api import _broadcast

async def test():
    try:
        await _broadcast({"event": "ingest", "source": "github", "records": []})
        print("Broadcast OK")
    except Exception as e:
        import logging; logging.error(f'Error: {e}', exc_info=True)
        print(f"Broadcast error: {type(e).__name__}: {e}")

asyncio.run(test())
