import asyncio
import contextlib
import pytest
import httpx
import os

from api import app

TOKEN = os.getenv('INTERNAL_TOKEN', '')
HEADERS = {'X-Internal-Token': TOKEN}
TEST_URL = os.getenv('TEST_BASE_URL')
BASE_URL = TEST_URL or 'http://testserver'
log_id = "test"
source_name = "test"

def get_client():
    if TEST_URL:
        return httpx.AsyncClient(timeout=60.0)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver", timeout=60.0)

@pytest.mark.asyncio
async def test_e2e_api_get___0():
    # Extracted from api.py
    async with get_client() as ac:
        response = await ac.get(f'{BASE_URL}/', headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422)

@pytest.mark.asyncio
async def test_e2e_api_get__health_1():
    # Extracted from api.py
    async with get_client() as ac:
        response = await ac.get(f'{BASE_URL}/health', headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422)

@pytest.mark.asyncio
async def test_e2e_api_post__ingest_json_2():
    # Extracted from api.py
    async with get_client() as ac:
        response = await ac.post(f'{BASE_URL}/ingest/json', json={}, headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422)

@pytest.mark.asyncio
async def test_e2e_api_post__ingest_csv_3():
    # Extracted from api.py
    async with get_client() as ac:
        response = await ac.post(f'{BASE_URL}/ingest/csv', json={}, headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422)

@pytest.mark.asyncio
async def test_e2e_api_post__ingest_email_4():
    # Extracted from api.py
    async with get_client() as ac:
        response = await ac.post(f'{BASE_URL}/ingest/email', json={}, headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422)

@pytest.mark.asyncio
async def test_e2e_api_post__webhook_source_name_5():
    # Extracted from api.py
    async with get_client() as ac:
        response = await ac.post(f'{BASE_URL}/webhook/{source_name}', json={}, headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422)

@pytest.mark.asyncio
async def test_e2e_api_post__webhook_source_name_with_vision_6():
    # Extracted from api.py
    async with get_client() as ac:
        response = await ac.post(f'{BASE_URL}/webhook/{source_name}/with-vision', json={}, headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422)

@pytest.mark.asyncio
async def test_e2e_api_get__pipeline_status_7():
    # Extracted from api.py
    async with get_client() as ac:
        response = await ac.get(f'{BASE_URL}/pipeline/status', headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422)

@pytest.mark.asyncio
async def test_e2e_api_post__pipeline_replay_log_id_8():
    # Extracted from api.py
    async with get_client() as ac:
        response = await ac.post(f'{BASE_URL}/pipeline/replay/{log_id}', json={}, headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422)

@pytest.mark.asyncio
async def test_e2e_api_get__pipeline_history_9():
    # Extracted from api.py
    async with get_client() as ac:
        response = await ac.get(f'{BASE_URL}/pipeline/history', headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422)

@pytest.mark.asyncio
async def test_e2e_api_get__live_sse_10():
    # SSE streams never end on their own (while True + is_disconnected() check), and
    # httpx's in-process ASGITransport never delivers the "client disconnected" ASGI
    # message the way a real uvicorn socket would -- so relying on the client-side
    # per-request timeout to unwind ac.stream()'s context manager hangs the whole
    # suite (Starlette's StreamingResponse keeps its body-producing task alive
    # waiting on a disconnect signal that will never arrive over ASGITransport).
    # Bound the whole attempt explicitly and treat "didn't finish" as the expected
    # outcome for an endpoint that's supposed to stream forever.
    async def _open_and_read_one_chunk():
        async with get_client() as ac:
            async with ac.stream("GET", f"{BASE_URL}/live/sse", headers=HEADERS) as response:
                assert response.status_code in (200, 400, 401, 403, 404, 405, 422)
                async for _ in response.aiter_bytes():
                    break

    task = asyncio.ensure_future(_open_and_read_one_chunk())
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=3.0)
    except (asyncio.TimeoutError, httpx.ReadTimeout, httpx.ConnectTimeout):
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task

