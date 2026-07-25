import asyncio


try:
    import httpx
    _HAS_HTTPX = True
except Exception:
    import requests
    _HAS_HTTPX = False

_headers = {'Accept': 'text/vnd.wap.wml'}

async def request_wap(url: str):
    if _HAS_HTTPX:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=_headers)
            text = resp.text
            status = resp.status_code
    else:
        loop = asyncio.get_event_loop()

        def blocking_get(u):
            r = requests.get(u, headers=_headers, timeout=10.0)
            return r.status_code, r.text

        status, text = await loop.run_in_executor(None, blocking_get, url)
    return (int(status), text)