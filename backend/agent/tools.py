"""
Robin — Composio Tools via direct REST API (no SDK — Python 3.14 compatible)
Uses https://backend.composio.dev/api/v3.1 directly.
"""
import httpx
import structlog
from config import settings

log = structlog.get_logger()

COMPOSIO_BASE = "https://backend.composio.dev/api/v3.1"

def _headers() -> dict:
    return {"x-api-key": settings.COMPOSIO_API_KEY, "Content-Type": "application/json"}


COMPOSIO_TOOLS = [
    {"type": "function", "function": {
        "name": "GOOGLECALENDAR_EVENTS_LIST",
        "description": "List upcoming Google Calendar events for the user",
        "parameters": {"type": "object", "properties": {
            "maxResults": {"type": "integer", "default": 10},
            "timeMin": {"type": "string", "description": "ISO 8601 datetime"},
        }},
    }},
    {"type": "function", "function": {
        "name": "GOOGLECALENDAR_CREATE_EVENT",
        "description": "Create a new event on Google Calendar",
        "parameters": {"type": "object", "properties": {
            "summary": {"type": "string"},
            "start": {"type": "string"},
            "end": {"type": "string"},
            "description": {"type": "string"},
        }, "required": ["summary", "start", "end"]},
    }},
    {"type": "function", "function": {
        "name": "GMAIL_SEND_EMAIL",
        "description": "Send an email via Gmail",
        "parameters": {"type": "object", "properties": {
            "recipient_email": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
        }, "required": ["recipient_email", "subject", "body"]},
    }},
    {"type": "function", "function": {
        "name": "GMAIL_MESSAGES_LIST",
        "description": "Fetch recent emails from Gmail inbox",
        "parameters": {"type": "object", "properties": {
            "max_results": {"type": "integer", "default": 5},
            "query": {"type": "string"},
        }},
    }},
    {"type": "function", "function": {
        "name": "SERPAPI_GOOGLE_SEARCH",
        "description": "Search the web for any information",
        "parameters": {"type": "object", "properties": {
            "q": {"type": "string", "description": "Search query"},
        }, "required": ["q"]},
    }},
    {"type": "function", "function": {
        "name": "SPOTIFY_PLAY_MUSIC",
        "description": "Play music on Spotify",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Song, artist, or playlist"},
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "SLACK_SEND_MESSAGE",
        "description": "Send a Slack message to a channel",
        "parameters": {"type": "object", "properties": {
            "channel": {"type": "string"},
            "message": {"type": "string"},
        }, "required": ["channel", "message"]},
    }},
    {"type": "function", "function": {
        "name": "GITHUB_CREATE_AN_ISSUE",
        "description": "Create a GitHub issue",
        "parameters": {"type": "object", "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "title": {"type": "string"},
            "body": {"type": "string"},
        }, "required": ["owner", "repo", "title"]},
    }},
]


class RobinToolset:
    def __init__(self, user_id: str = "default"):
        self.user_id = user_id

    def get_openai_tools(self) -> list[dict]:
        if not settings.COMPOSIO_API_KEY:
            return []
        return COMPOSIO_TOOLS

    async def execute_tool_call(self, tool_name: str, tool_input: dict) -> dict:
        if not settings.COMPOSIO_API_KEY:
            return {"success": False, "error": "COMPOSIO_API_KEY not set"}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{COMPOSIO_BASE}/tools/execute/{tool_name}",
                    headers=_headers(),
                    json={"arguments": tool_input, "entity_id": self.user_id},
                )
                resp.raise_for_status()
                data = resp.json()
                log.info("composio_tool_success", tool=tool_name)
                return {"success": True, "result": data.get("response", data)}
        except Exception as e:
            log.error("composio_tool_failed", tool=tool_name, error=str(e))
            return {"success": False, "error": str(e)}

    async def get_auth_url(self, app: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{COMPOSIO_BASE}/auth_configs",
                    headers=_headers(),
                    json={"app_name": app, "entity_id": self.user_id},
                )
                return resp.json().get("redirect_url", "")
        except Exception as e:
            log.error("composio_auth_url_failed", app=app, error=str(e))
            return ""

    async def list_connections(self) -> list:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{COMPOSIO_BASE}/connections",
                    headers=_headers(),
                    params={"entity_id": self.user_id},
                )
                return resp.json().get("items", [])
        except Exception:
            return []
