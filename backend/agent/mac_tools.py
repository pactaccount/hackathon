"""
Robin — Mac Native Tools
AppleScript + shell commands for direct Mac system control.
"""
import asyncio
import subprocess
import structlog

log = structlog.get_logger()

MAC_TOOLS = [
    {"type": "function", "function": {
        "name": "set_volume",
        "description": "Set the Mac system volume (0-100)",
        "parameters": {"type": "object", "properties": {
            "level": {"type": "integer", "description": "Volume level 0-100"},
        }, "required": ["level"]},
    }},
    {"type": "function", "function": {
        "name": "open_application",
        "description": "Open a Mac application by name",
        "parameters": {"type": "object", "properties": {
            "app_name": {"type": "string", "description": "Application name e.g. Spotify, Safari"},
        }, "required": ["app_name"]},
    }},
    {"type": "function", "function": {
        "name": "install_homebrew_app",
        "description": "Install a macOS application using Homebrew Cask",
        "parameters": {"type": "object", "properties": {
            "app_name": {"type": "string", "description": "Homebrew cask name e.g. arc, notion"},
        }, "required": ["app_name"]},
    }},
    {"type": "function", "function": {
        "name": "take_screenshot",
        "description": "Take a screenshot of the current screen",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "default": "~/Desktop/screenshot.png"},
        }},
    }},
    {"type": "function", "function": {
        "name": "run_shell_command",
        "description": "Run a safe shell command on the Mac (git, python, npm, etc.)",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
        }, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "send_imessage",
        "description": "Send an iMessage to a contact",
        "parameters": {"type": "object", "properties": {
            "phone_or_email": {"type": "string"},
            "message": {"type": "string"},
        }, "required": ["phone_or_email", "message"]},
    }},
    {"type": "function", "function": {
        "name": "get_battery_status",
        "description": "Get the Mac battery level and charging status",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "lock_screen",
        "description": "Lock the Mac screen",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "empty_trash",
        "description": "Empty the Mac Trash",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search the web using Google in the default browser",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "The search query"},
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "send_whatsapp_message",
        "description": "Send a WhatsApp message to a contact",
        "parameters": {"type": "object", "properties": {
            "contact": {"type": "string", "description": "The name of the contact"},
            "message": {"type": "string", "description": "The message to send"},
        }, "required": ["contact", "message"]},
    }},
    {"type": "function", "function": {
        "name": "compose_email",
        "description": "Compose an email draft on the Mac",
        "parameters": {"type": "object", "properties": {
            "recipient": {"type": "string", "description": "Email address or contact name"},
            "subject": {"type": "string", "description": "Subject of the email"},
            "body": {"type": "string", "description": "Body content of the email"},
        }, "required": ["recipient", "body"]},
    }},
    {"type": "function", "function": {
        "name": "close_browser_tab",
        "description": "Close a browser tab in Chrome, Safari or Firefox. Can close by tab title/URL keyword or just the active tab.",
        "parameters": {"type": "object", "properties": {
            "keyword": {"type": "string", "description": "Optional keyword to match in tab title or URL (e.g. 'gemini', 'youtube'). If omitted, closes the active tab."},
            "browser": {"type": "string", "description": "Browser name: 'Chrome', 'Safari', or 'Firefox'. Defaults to 'Chrome'."},
        }},
    }},
]


async def execute_mac_tool(tool_name: str, tool_input: dict) -> dict:
    try:
        if tool_name == "set_volume":
            level = max(0, min(100, int(tool_input.get("level", 50))))
            subprocess.run(["osascript", "-e", f"set volume output volume {level}"], check=True)
            return {"success": True, "result": f"Volume set to {level}%"}

        elif tool_name == "open_application":
            import re
            import urllib.parse
            app = tool_input.get("app_name", "").strip()
            
            # Common website shortcuts
            WEBSITES = {
                "gmail": "https://mail.google.com",
                "youtube": "https://youtube.com",
                "google": "https://google.com",
                "github": "https://github.com",
                "facebook": "https://facebook.com",
                "twitter": "https://twitter.com",
                "x": "https://x.com",
                "reddit": "https://reddit.com",
                "netflix": "https://netflix.com",
                "chatgpt": "https://chatgpt.com",
            }
            
            browser = None
            app_lower = app.lower()
            # Detect requests like "open gmail on chrome" or "open youtube in safari"
            for b_name in ["chrome", "google chrome", "safari", "firefox", "edge", "arc"]:
                if f" on {b_name}" in app_lower or f" in {b_name}" in app_lower:
                    browser = "Google Chrome" if b_name in ["chrome", "google chrome"] else b_name.title()
                    app = re.sub(rf"\s+(?:on|in)\s+{b_name}", "", app, flags=re.IGNORECASE).strip()
                    break
            
            app_lower = app.lower()
            
            # 1. Check if it's a known website shortcut
            if app_lower in WEBSITES:
                url = WEBSITES[app_lower]
                if browser:
                    subprocess.run(["open", "-a", browser, url], check=True)
                else:
                    subprocess.run(["open", url], check=True)
                return {"success": True, "result": f"Opened {app} website in browser"}
            
            # 2. Check if it's a direct URL (e.g. "sjsu.edu" or "google.com")
            if "." in app and " " not in app and not app.startswith("http"):
                url = "https://" + app
                if browser:
                    subprocess.run(["open", "-a", browser, url], check=True)
                else:
                    subprocess.run(["open", url], check=True)
                return {"success": True, "result": f"Opened URL: {url}"}
            
            if browser and app_lower in ["chrome", "google chrome", "safari", "firefox", "edge", "arc"]:
                subprocess.run(["open", "-a", browser], check=True)
                return {"success": True, "result": f"Opened {browser}"}
            
            # 3. Try opening as a local Mac application, fallback to Google Search if not found
            try:
                subprocess.run(["open", "-a", app], check=True)
                return {"success": True, "result": f"Opened {app}"}
            except Exception as e:
                # Fallback: Open web search for the target
                encoded = urllib.parse.quote(app)
                search_url = f"https://www.google.com/search?q={encoded}"
                if browser:
                    subprocess.run(["open", "-a", browser, search_url], check=True)
                else:
                    subprocess.run(["open", search_url], check=True)
                return {"success": True, "result": f"Application '{app}' not found; performed web search instead"}

        elif tool_name == "web_search":
            query = tool_input.get("query", "")
            import urllib.parse
            encoded = urllib.parse.quote(query)
            subprocess.run(["open", f"https://www.google.com/search?q={encoded}"], check=True)
            return {"success": True, "result": f"Searched the web for '{query}'"}

        elif tool_name == "install_homebrew_app":
            app = tool_input.get("app_name", "")
            # Try cask first (for GUI apps like Chrome, Slack, etc.)
            result = subprocess.run(
                ["brew", "install", "--cask", app],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                # Fallback to standard formula (for CLI tools like git, python, etc.)
                result = subprocess.run(
                    ["brew", "install", app],
                    capture_output=True, text=True, timeout=120
                )
            return {"success": result.returncode == 0, "result": result.stdout or result.stderr}

        elif tool_name == "take_screenshot":
            path = tool_input.get("path", "~/Desktop/screenshot.png")
            subprocess.run(["screencapture", "-x", path], check=True)
            return {"success": True, "result": f"Screenshot saved to {path}"}

        elif tool_name == "run_shell_command":
            cmd = tool_input.get("command", "")
            # Safety: block dangerous commands
            blocked = ["rm -rf", "sudo rm", "format", "mkfs", "dd if="]
            if any(b in cmd for b in blocked):
                return {"success": False, "error": "Command blocked for safety"}
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            return {"success": True, "result": result.stdout or result.stderr}

        elif tool_name == "send_imessage":
            target = tool_input.get("phone_or_email", "")
            msg = tool_input.get("message", "")
            script = f'tell application "Messages" to send "{msg}" to buddy "{target}"'
            subprocess.run(["osascript", "-e", script], check=True)
            return {"success": True, "result": f"iMessage sent to {target}"}

        elif tool_name == "get_battery_status":
            result = subprocess.run(
                ["pmset", "-g", "batt"], capture_output=True, text=True
            )
            output = result.stdout.strip()
            import re
            pct_match = re.search(r"(\d+)%", output)
            status_match = re.search(r"(discharging|charging|charged)", output)
            
            pct = pct_match.group(1) if pct_match else "unknown"
            status = status_match.group(1) if status_match else "unknown"
            
            if status == "charged":
                status_str = "fully charged and plugged in"
            elif status == "charging":
                status_str = "charging"
            elif status == "discharging":
                status_str = "discharging (on battery power)"
            else:
                status_str = status
                
            clean_result = f"Battery is at {pct}% ({status_str})."
            return {"success": True, "result": clean_result}

        elif tool_name == "lock_screen":
            subprocess.run([
                "osascript", "-e",
                'tell application "System Events" to keystroke "q" using {command down, control down}'
            ])
            return {"success": True, "result": "Screen locked"}

        elif tool_name == "send_whatsapp_message":
            contact = tool_input.get("contact", "")
            msg = tool_input.get("message", "")
            script = f'''
            tell application "WhatsApp" to activate
            delay 1.5
            tell application "System Events"
                keystroke "f" using command down
                delay 0.5
                keystroke "{contact}"
                delay 2.5 -- wait for search results to load
                key code 48 -- Tab to move focus to list
                delay 0.5
                key code 125 -- Down arrow to select first result
                delay 0.5
                key code 36 -- Enter to open chat
                delay 1.0
                keystroke "{msg}"
                delay 0.5
                key code 36 -- Enter to send
            end tell
            '''
            try:
                subprocess.run(["osascript", "-e", script], check=True)
                return {"success": True, "result": f"Sent WhatsApp message to {contact}"}
            except Exception as e:
                import urllib.parse
                encoded = urllib.parse.quote(msg)
                subprocess.run(["open", f"whatsapp://send?text={encoded}"], check=True)
                return {"success": True, "result": f"Opened WhatsApp chat fallback"}

        elif tool_name == "compose_email":
            recipient = tool_input.get("recipient", "")
            subject = tool_input.get("subject", "Message from Robin")
            body = tool_input.get("body", "")
            import urllib.parse
            to_enc = urllib.parse.quote(recipient)
            subj_enc = urllib.parse.quote(subject)
            body_enc = urllib.parse.quote(body)
            subprocess.run(["open", f"mailto:{to_enc}?subject={subj_enc}&body={body_enc}"], check=True)
            return {"success": True, "result": f"Composed email draft to {recipient}"}

        elif tool_name == "close_browser_tab":
            keyword = tool_input.get("keyword", "").lower().strip()
            browser = tool_input.get("browser", "Google Chrome").strip()
            # Normalise browser name
            if browser.lower() in ["chrome", "google chrome"]:
                browser = "Google Chrome"
            elif browser.lower() == "firefox":
                browser = "Firefox"
            else:
                browser = "Safari"

            if keyword and browser == "Google Chrome":
                # Find and close matching tab across all windows
                script = f'''
                tell application "Google Chrome"
                    set tabClosed to false
                    repeat with w in windows
                        set tabList to tabs of w
                        repeat with t in tabList
                            set tabURL to URL of t
                            set tabTitle to title of t
                            if tabURL contains "{keyword}" or tabTitle contains "{keyword}" then
                                close t
                                set tabClosed to true
                                exit repeat
                            end if
                        end repeat
                        if tabClosed then exit repeat
                    end repeat
                    return tabClosed
                end tell
                '''
            elif keyword and browser == "Safari":
                script = f'''
                tell application "Safari"
                    set tabClosed to false
                    repeat with w in windows
                        repeat with t in tabs of w
                            if URL of t contains "{keyword}" or name of t contains "{keyword}" then
                                close t
                                set tabClosed to true
                                exit repeat
                            end if
                        end repeat
                        if tabClosed then exit repeat
                    end repeat
                    return tabClosed
                end tell
                '''
            else:
                # No keyword — just close the active/front tab
                if browser == "Google Chrome":
                    script = 'tell application "Google Chrome" to close active tab of front window'
                elif browser == "Firefox":
                    script = '''tell application "System Events"
                        tell process "Firefox"
                            keystroke "w" using command down
                        end tell
                    end tell'''
                else:
                    script = 'tell application "Safari" to close current tab of front window'

            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            if result.returncode == 0:
                label = f"'{keyword}' tab" if keyword else "active tab"
                return {"success": True, "result": f"Closed {label} in {browser}"}
            else:
                return {"success": False, "error": result.stderr.strip()}

        elif tool_name == "empty_trash":
            subprocess.run(["osascript", "-e", 'tell application "Finder" to empty trash'])
            return {"success": True, "result": "Trash emptied"}

        return {"success": False, "error": f"Unknown tool: {tool_name}"}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out"}
    except Exception as e:
        log.error("mac_tool_failed", tool=tool_name, error=str(e))
        return {"success": False, "error": str(e)}


MAC_TOOL_NAMES = {t["function"]["name"] for t in MAC_TOOLS}
