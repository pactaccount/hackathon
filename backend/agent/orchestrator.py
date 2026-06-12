"""Robin — Agent Orchestrator
Strategy: Don't pass tool schemas to the LLM (makes Llama 3.1 very slow).
Instead: System prompt describes capabilities. Response is parsed for Mac actions.
Composio cloud tools are still called when intent is detected in the response.
"""
import uuid
import json
import re
import asyncio
import structlog

from agent.gateway import gateway
from agent.mac_tools import MAC_TOOL_NAMES, execute_mac_tool
from agent.tools import RobinToolset
from memory.clickhouse import ch_client
from memory.profile import build_system_prompt
from config import settings

log = structlog.get_logger()

MAX_ITERATIONS = 3

# ── Mac intent patterns ───────────────────────────────────────────────────────
# These let us detect when Robin said it will do something, and actually do it.
MAC_PATTERNS = [
    # WhatsApp (accepting saying/that/to/etc. and various prepositions like on/in/through/via/using)
    (r"(?:send\s+)?(?:a\s+)?message\s+to\s+([\w\s]+?)\s+(?:saying|that|to)\s+(.+?)\s+(?:on|in|through|via|using)\s+whatsapp", "send_whatsapp_message", lambda m: {"contact": m.group(1).strip(), "message": m.group(2).strip()}),
    (r"(?:send\s+)?(?:a\s+)?message\s+to\s+([\w\s]+?)\s+(?:on|in|through|via|using)\s+whatsapp\s+(?:saying|that|to)\s+(.+)", "send_whatsapp_message", lambda m: {"contact": m.group(1).strip(), "message": m.group(2).strip()}),
    (r"whatsapp\s+to\s+([\w\s]+?)\s+(?:saying|that|to)\s+(.+)", "send_whatsapp_message", lambda m: {"contact": m.group(1).strip(), "message": m.group(2).strip()}),
    
    # Email composing
    (r"(?:compose|send)\s+(?:an\s+)?email\s+to\s+([\w\s\.\@]+?)\s+with\s+subject\s+(.+?)\s+and\s+body\s+(.+)", "compose_email", lambda m: {"recipient": m.group(1).strip(), "subject": m.group(2).strip(), "body": m.group(3).strip()}),
    (r"(?:compose|send)\s+(?:an\s+)?email\s+to\s+([\w\s\.\@]+?)\s+(?:saying|that|to)\s+(.+)", "compose_email", lambda m: {"recipient": m.group(1).strip(), "subject": "Message from Robin", "body": m.group(2).strip()}),
    
    (r"set.*?volume.*?(\d+)", "set_volume", lambda m: {"level": int(m.group(1))}),
    (r"open\s+([\w\s]+?)(?:\s+app|\s+application|$|\.|,)", "open_application", lambda m: {"app_name": re.sub(r"^(?:the|a|an)\s+", "", m.group(1).strip(), flags=re.IGNORECASE)}),
    (r"search\s+(?:the\s+web\s+)?(?:for\s+)?(.+)", "web_search", lambda m: {"query": m.group(1).strip()}),
    (r"(?:google|look up|search for)\s+(.+)", "web_search", lambda m: {"query": m.group(1).strip()}),
    (r"take\s+(?:a\s+)?screenshot", "take_screenshot", lambda m: {}),
    (r"lock\s+(?:the\s+)?(?:screen|mac)", "lock_screen", lambda m: {}),
    (r"empty\s+(?:the\s+)?trash", "empty_trash", lambda m: {}),
    (r"battery\s+(?:status|level|info)", "get_battery_status", lambda m: {}),
    (r"(?:install|download)\s+([\w\s\-]+?)(?:\s+using|\s+with|$|\.|,)", "install_homebrew_app", lambda m: {"app_name": re.sub(r"^(?:the|a|an)\s+", "", m.group(1).strip(), flags=re.IGNORECASE)}),
    # Close browser tabs — "close gemini tab in chrome", "close the youtube tab", "close active tab"
    (r"close\s+(?:the\s+)?([\w]+?)\s+tab(?:\s+(?:in|on|from)\s+(chrome|safari|firefox))?", "close_browser_tab",
     lambda m: {"keyword": m.group(1).strip() if m.group(1).lower() not in ["the", "active", "current"] else "",
                "browser": (m.group(2) or "Chrome").capitalize().replace("Chrome", "Google Chrome")}),
    (r"close\s+(?:the\s+)?(?:active|current)\s+tab(?:\s+(?:in|on|from)\s+(chrome|safari|firefox))?", "close_browser_tab",
     lambda m: {"keyword": "", "browser": (m.group(1) or "Chrome").capitalize().replace("Chrome", "Google Chrome")}),
]


def detect_and_execute_intent(response_text: str):
    """Return (tool_name, tool_input) if response implies a Mac action, else (None, None)."""
    lowered = response_text.lower()
    for pattern, tool_name, extractor in MAC_PATTERNS:
        m = re.search(pattern, lowered)
        if m:
            try:
                return tool_name, extractor(m)
            except Exception:
                pass
    return None, None


class RobinOrchestrator:
    async def run(self, user_id: str, message: str, smart_mode: bool = False) -> dict:
        run_id   = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        log.info("chat_request", user=user_id, smart_mode=smart_mode)

        # Build conversation with personal context (no tool schemas — keeps LLM fast)
        system_prompt = build_system_prompt(user_id)
        history       = ch_client.get_history(user_id, limit=8)
        messages = [{"role": "system", "content": system_prompt}] + history
        messages.append({"role": "user", "content": message})

        # Save user message
        ch_client.save_message(user_id, session_id, "user", message, str(uuid.uuid4()))

        # ── Pre-LLM Tool Execution: Check if user message implies an action/query ──
        tool_result = None
        tool_name, tool_input = detect_and_execute_intent(message)
        
        if tool_name:
            log.info("mac_tool_executing_pre_llm", tool=tool_name, input=tool_input)
            tool_result = await execute_mac_tool(tool_name, tool_input)
            if tool_result.get("success"):
                log.info("mac_tool_success_pre_llm", tool=tool_name)
                # Prepend the tool result to the user's message to force the LLM to use it
                messages[-1]["content"] = f"[System Context: {tool_result.get('result')}]\n{message}"
            else:
                log.warning("mac_tool_failed_pre_llm", tool=tool_name, error=tool_result.get("error"))

        # Get LLM response — keeps response time ~1-2s
        log.info("agent_iteration", iteration=0, run_id=run_id)
        llm_resp = await gateway.chat(messages=messages, tools=None, smart_mode=smart_mode)
        response_text = llm_resp.content or ""

        log.info("llm_response",
                 latency_ms=round(llm_resp.latency_ms, 1),
                 provider=str(llm_resp.provider),
                 tokens=llm_resp.completion_tokens)

        # ── Post-LLM Fallback: If no tool was executed yet, check LLM response for actions ──
        if not tool_name:
            tool_name, tool_input = detect_and_execute_intent(response_text)
            if tool_name:
                log.info("mac_tool_executing_post_llm", tool=tool_name, input=tool_input)
                tool_result = await execute_mac_tool(tool_name, tool_input)
                if tool_result.get("success"):
                    log.info("mac_tool_success_post_llm", tool=tool_name)
                else:
                    log.warning("mac_tool_failed_post_llm", tool=tool_name, error=tool_result.get("error"))

        # ── Composio tools (calendar, email, search) ──────────────────────────
        composio_result = None
        msg_lower = message.lower()
        toolset = RobinToolset(user_id=user_id)

        if any(kw in msg_lower for kw in ["calendar", "schedule", "event", "appointment"]):
            composio_result = await toolset.execute_tool_call(
                "GOOGLECALENDAR_EVENTS_LIST", {"maxResults": 5})
            if composio_result.get("success"):
                cal_data = json.dumps(composio_result.get("result", {}))[:500]
                response_text += f"\n\n📅 Calendar data: {cal_data}"

        elif any(kw in msg_lower for kw in ["email", "gmail", "inbox", "mail"]):
            composio_result = await toolset.execute_tool_call(
                "GMAIL_MESSAGES_LIST", {"max_results": 3})
            if composio_result.get("success"):
                email_data = json.dumps(composio_result.get("result", {}))[:500]
                response_text += f"\n\n📧 Email data: {email_data}"

        elif any(kw in msg_lower for kw in ["search", "look up", "find", "news"]):
            composio_result = await toolset.execute_tool_call(
                "SERPAPI_GOOGLE_SEARCH", {"q": message})
            if composio_result.get("success"):
                search_data = json.dumps(composio_result.get("result", {}))[:500]
                response_text += f"\n\n🔍 Search result: {search_data}"

        # Save assistant response
        ch_client.save_message(user_id, session_id, "assistant", response_text, str(uuid.uuid4()))

        return {
            "response": response_text,
            "provider": str(llm_resp.provider.value if hasattr(llm_resp.provider, 'value') else llm_resp.provider),
            "run_id": run_id,
            "duration_ms": float(llm_resp.latency_ms),
            "tool_executed": tool_name,
        }


orchestrator = RobinOrchestrator()
