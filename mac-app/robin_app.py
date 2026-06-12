"""
Robin Mac App — Simplified & Reliable
- Serves UI from FastAPI backend (localhost:8000/ui)  
- Menubar click just opens the browser — no pywebview threading issues
- Voice handled by browser Web Speech API
"""
import os
import subprocess
import threading
import time
from pathlib import Path

import rumps
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "backend" / ".env")

BACKEND_URL = os.getenv("ROBIN_BACKEND_URL", "http://localhost:8000")
USER_ID     = os.getenv("ROBIN_USER_ID", os.getenv("USER", "default"))


def open_panel():
    """Open the Robin chat panel in the default browser."""
    url = f"{BACKEND_URL}/ui?user={USER_ID}"
    subprocess.Popen(["open", url])


def check_backend() -> dict:
    try:
        resp = requests.get(f"{BACKEND_URL}/health", timeout=3)
        return resp.json()
    except Exception:
        return {"status": "offline"}


class RobinMenubarApp(rumps.App):

    def __init__(self):
        super().__init__(
            name="Robin", title="🤖",
            menu=[
                rumps.MenuItem("Open Robin", callback=self.open_panel),
                None,
                rumps.MenuItem("Check Backend", callback=self.check_backend_status),
                None,
                rumps.MenuItem("Quit Robin", callback=self.quit_robin),
            ],
            quit_button=None,
        )
        # Check backend health on start, auto-start if needed
        threading.Thread(target=self._startup_check, daemon=True).start()
        print(f"✅ Robin menubar ready — {BACKEND_URL}/ui")

    def _startup_check(self):
        time.sleep(2)
        status = check_backend()
        if status.get("status") == "ok":
            rumps.notification("Robin", "Ready", "Click 🤖 → Open Robin to start chatting", sound=False)
        else:
            rumps.notification("Robin", "Backend offline",
                "Start it: cd ~/Desktop/robin/backend && python3 -m uvicorn main:app --port 8000",
                sound=False)

    @rumps.clicked("Open Robin")
    def open_panel(self, _=None):
        status = check_backend()
        if status.get("status") != "ok":
            rumps.notification("Robin", "Backend offline ❌",
                "Run in Terminal: cd ~/Desktop/robin/backend && python3 -m uvicorn main:app --port 8000",
                sound=False)
            return
        url = f"{BACKEND_URL}/ui?user={USER_ID}"
        subprocess.Popen(["open", url])

    @rumps.clicked("Check Backend")
    def check_backend_status(self, _):
        status = check_backend()
        if status.get("status") == "ok":
            pioneer = status.get("pioneer", "?")
            composio = status.get("composio", "?")
            rumps.notification("Robin Backend", "Online ✅",
                f"Pioneer: {pioneer} | Composio: {composio}", sound=False)
        else:
            rumps.notification("Robin Backend", "Offline ❌",
                "cd ~/Desktop/robin/backend && python3 -m uvicorn main:app --port 8000",
                sound=False)

    @rumps.clicked("Quit Robin")
    def quit_robin(self, _):
        rumps.quit_application()


def main():
    print("🤖 Robin starting…")
    print(f"   Panel URL: {BACKEND_URL}/ui")
    print(f"   User ID  : {USER_ID}")
    RobinMenubarApp().run()


if __name__ == "__main__":
    main()
