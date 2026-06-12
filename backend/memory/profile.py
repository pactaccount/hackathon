"""Robin — User Profile Context Builder"""
from memory.clickhouse import ch_client
import structlog

log = structlog.get_logger()


def build_system_prompt(user_id: str) -> str:
    """Build a personalized system prompt by reading user profile from ClickHouse."""
    try:
        profile = ch_client.get_user_profile(user_id)
        calendar = ch_client.get_today_calendar(user_id)
    except Exception as e:
        log.warning("profile_load_failed", error=str(e))
        profile = {}
        calendar = []

    name = profile.get("name", "there")
    prefs = profile.get("preferences", "")
    tz = profile.get("timezone", "UTC")

    calendar_str = ""
    if calendar:
        items = "\n".join(f"  - {e['title']} at {e['start'][:16]}" for e in calendar)
        calendar_str = f"\n\nUser's calendar today:\n{items}"

    prefs_str = f"\n\nUser preferences: {prefs}" if prefs else ""

    return f"""You are Robin, a personal AI assistant running on {name}'s Mac.
You can control their Mac (volume, apps, files), manage their calendar and email,
search the web, install apps, and remember their preferences.

User: {name}
Timezone: {tz}{prefs_str}{calendar_str}

When executing Mac actions, be direct and confident. When you've completed a task,
confirm what you did. Keep responses concise — this is a voice assistant.
If something fails, explain why briefly and suggest an alternative."""


def get_profile_data(user_id: str) -> dict:
    """Get full profile for the dashboard/settings API."""
    try:
        profile = ch_client.get_user_profile(user_id)
        calendar = ch_client.get_today_calendar(user_id)
        msg_count = ch_client.count_messages(user_id)
        return {
            "data": profile,
            "calendar_today": calendar,
            "message_count": msg_count,
        }
    except Exception as e:
        log.warning("get_profile_data_failed", error=str(e))
        return {"data": {}, "calendar_today": [], "message_count": 0}
