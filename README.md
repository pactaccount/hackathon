# 🤖 Robin — Personal AI Assistant for Mac

Robin is a voice-powered, on-device AI assistant that lives in your Mac menubar. It understands natural language and can control your Mac, manage apps, send messages, search the web, and much more — all without leaving your desktop.

---

## ✨ Features

| Category | Capabilities |
|----------|-------------|
| 🖥️ **Mac Control** | Set volume, open apps, take screenshots, lock screen, empty trash |
| 🌐 **Web** | Open websites, Google Search, close browser tabs (Chrome/Safari/Firefox) |
| 💬 **Messaging** | Send WhatsApp messages, compose emails via mailto |
| 🔋 **System Info** | Real-time battery status, charging state |
| 📅 **Productivity** | Google Calendar sync via Airbyte, Gmail integration via Composio |
| 🎙️ **Voice** | Browser-based voice input (Web Speech API) + Whisper transcription |
| 🧠 **Memory** | Persistent conversation history + user profile via ClickHouse |

---

## 🏗️ Architecture

```
┌─────────────────┐     HTTP      ┌──────────────────────────────────┐
│  Mac Menubar    │ ───────────▶  │  FastAPI Backend (port 8000)     │
│  robin_app.py   │               │                                  │
└─────────────────┘               │  ┌─────────────┐                 │
                                  │  │ Orchestrator │                 │
┌─────────────────┐               │  │ (Pre-LLM     │                 │
│  Browser UI     │ ───────────▶  │  │  Tool Exec)  │                 │
│  /ui endpoint   │               │  └──────┬──────┘                 │
└─────────────────┘               │         │                         │
                                  │  ┌──────▼──────┐  ┌───────────┐  │
                                  │  │  AI Gateway  │  │ Mac Tools │  │
                                  │  │  (Pioneer /  │  │AppleScript│  │
                                  │  │  Ollama /    │  │ subprocess│  │
                                  │  │  Groq)       │  └───────────┘  │
                                  │  └─────────────┘                  │
                                  │  ┌────────────────────────────┐   │
                                  │  │ ClickHouse (Memory/Profile) │  │
                                  │  └────────────────────────────┘   │
                                  └──────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Clone & install backend dependencies

```bash
git clone https://github.com/YOUR_USERNAME/robin.git
cd robin/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Set up environment

```bash
cp .env.example .env
# Fill in your API keys in .env
```

### 3. Start the backend

```bash
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Open the UI

Visit [http://localhost:8000/ui](http://localhost:8000/ui) in your browser, or run the Mac menubar app:

```bash
cd mac-app
pip install -r requirements.txt
python3 robin_app.py
```

---

## 📦 Project Structure

```
robin/
├── backend/
│   ├── main.py              # FastAPI app — all HTTP endpoints
│   ├── config.py            # Pydantic settings (loads .env)
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example         # ← copy to .env and fill in keys
│   ├── agent/
│   │   ├── gateway.py       # LLM router: Pioneer / Groq / Ollama
│   │   ├── orchestrator.py  # Intent detection + tool execution
│   │   ├── mac_tools.py     # AppleScript / subprocess Mac actions
│   │   └── tools.py         # Composio cloud tools (Calendar, Gmail…)
│   ├── memory/
│   │   ├── clickhouse.py    # Conversation history + user profile
│   │   └── profile.py       # System prompt builder
│   └── data/
│       └── airbyte_sync.py  # Airbyte background sync loop
├── mac-app/
│   ├── robin_app.py         # macOS menubar app (rumps)
│   ├── requirements.txt
│   └── ui/
│       └── index.html       # Chat UI served by backend
├── render.yaml              # Render.com deployment config
└── README.md
```

---

## 🔑 Required API Keys

| Key | Where to get it |
|-----|----------------|
| `PIONEER_API_KEY` | [pioneer.ai](https://pioneer.ai) — LLM provider |
| `COMPOSIO_API_KEY` | [composio.dev](https://composio.dev) — Google Calendar, Gmail |
| `CLICKHOUSE_*` | [clickhouse.cloud](https://clickhouse.cloud) — Memory storage |
| `AIRBYTE_*` | [airbyte.com](https://airbyte.com) — Data sync (optional) |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) — Optional fast LLM |

---

## 🛠️ Mac Permissions Required

Robin uses AppleScript to control macOS apps. You may need to grant:

- **Accessibility** — System Settings → Privacy & Security → Accessibility → add Terminal/Python
- **Automation** — grant access to WhatsApp, Google Chrome, Safari etc. when prompted

---

## 🌐 Deployment (Render)

```bash
# Deploy backend to Render using render.yaml
# Set all environment variables in Render dashboard
```

---

## 🤝 Built With

- **[Pioneer AI](https://pioneer.ai)** — LLM provider (Llama 3.1 + Claude Sonnet)
- **[Composio](https://composio.dev)** — Google Calendar & Gmail integrations
- **[ClickHouse Cloud](https://clickhouse.cloud)** — Real-time memory storage
- **[Airbyte](https://airbyte.com)** — Data pipeline for calendar sync
- **FastAPI + Uvicorn** — Backend API
- **rumps** — macOS menubar framework

---

*Built at a hackathon by Abhinav 🚀*
