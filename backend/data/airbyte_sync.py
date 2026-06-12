"""Robin — Airbyte OAuth2 Sync Client"""
import asyncio
import time
import httpx
import structlog
from config import settings

log = structlog.get_logger()

AIRBYTE_TOKEN_URL = "https://api.airbyte.com/v1/applications/token"
AIRBYTE_BASE = "https://api.airbyte.com/v1"

_cached_token: str = ""
_token_expires_at: float = 0


async def get_airbyte_token() -> str:
    global _cached_token, _token_expires_at
    if _cached_token and time.time() < _token_expires_at - 60:
        return _cached_token
    if not settings.AIRBYTE_CLIENT_ID:
        return ""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(AIRBYTE_TOKEN_URL, json={
                "client_id": settings.AIRBYTE_CLIENT_ID,
                "client_secret": settings.AIRBYTE_CLIENT_SECRET,
            })
            resp.raise_for_status()
            data = resp.json()
            _cached_token = data.get("access_token", "")
            _token_expires_at = time.time() + data.get("expires_in", 3600)
            return _cached_token
    except Exception as e:
        log.warning("airbyte_token_failed", error=str(e))
        return ""


class AirbyteSyncClient:
    async def _headers(self):
        token = await get_airbyte_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def trigger_sync(self, connection_id: str) -> str:
        if not connection_id:
            return ""
        headers = await self._headers()
        async with httpx.AsyncClient(headers=headers, timeout=10) as client:
            resp = await client.post(
                f"{AIRBYTE_BASE}/jobs",
                json={"connectionId": connection_id, "jobType": "sync"},
            )
            resp.raise_for_status()
            job_id = resp.json().get("jobId", "")
            log.info("airbyte_sync_triggered", connection=connection_id, job_id=job_id)
            return job_id

    async def sync_all(self) -> dict:
        results = {}
        for name, conn_id in [
            ("calendar", settings.AIRBYTE_CALENDAR_CONNECTION_ID),
            ("gmail", settings.AIRBYTE_GMAIL_CONNECTION_ID),
        ]:
            if conn_id:
                try:
                    job_id = await self.trigger_sync(conn_id)
                    results[name] = {"status": "triggered", "job_id": job_id}
                except Exception as e:
                    results[name] = {"status": "failed", "error": str(e)}
            else:
                results[name] = {"status": "not_configured"}
        return results


async def background_sync_loop(client: AirbyteSyncClient):
    while True:
        log.info("airbyte_background_sync_starting")
        try:
            await client.sync_all()
        except Exception as e:
            log.warning("background_sync_error", error=str(e))
        await asyncio.sleep(15 * 60)


airbyte_client = AirbyteSyncClient()
