"""Robin — FastAPI Backend"""
import asyncio
import tempfile
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure Homebrew bin is in the system PATH for subprocesses (e.g. Whisper finding ffmpeg)
os.environ["PATH"] = "/opt/homebrew/bin:" + os.environ.get("PATH", "")


import structlog
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from agent.orchestrator import orchestrator
from memory.clickhouse import ch_client
from memory.profile import get_profile_data
from data.airbyte_sync import airbyte_client, background_sync_loop
from config import settings

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("robin_backend_starting")
    try:
        ch_client.ensure_schema()
    except Exception as e:
        log.warning("clickhouse_schema_warning", error=str(e))
    log.info("robin_backend_ready")
    asyncio.create_task(background_sync_loop(airbyte_client))
    yield


app = FastAPI(title="Robin AI Backend", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ChatRequest(BaseModel):
    user_id: str = "default"
    message: str
    smart_mode: bool = False


class ProfileUpdateRequest(BaseModel):
    user_id: str
    key: str
    value: str

UI_HTML_PATH = Path(__file__).parent / "index.html"

@app.get("/ui", response_class=HTMLResponse)
async def serve_ui():
    """Serve the Robin chat panel — open in any browser."""
    try:
        return HTMLResponse(content=UI_HTML_PATH.read_text())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>UI not found</h1><p>Expected: mac-app/ui/index.html</p>", status_code=404)


@app.get("/", response_class=HTMLResponse)
async def root():
    return """<!DOCTYPE html>
<html><head><title>Robin API</title>
<style>
body{font-family:-apple-system,sans-serif;background:#0d0d1a;color:#f0f0f8;margin:0;display:flex;align-items:center;justify-content:center;height:100vh;}
.card{background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);border-radius:20px;padding:40px 48px;text-align:center;max-width:460px;}
h1{font-size:32px;margin:0 0 8px;}
p{color:rgba(240,240,248,0.6);margin:0 0 28px;font-size:15px;}
.badge{display:inline-block;background:rgba(6,214,160,0.15);border:1px solid rgba(6,214,160,0.4);color:#06d6a0;padding:6px 16px;border-radius:20px;font-size:13px;margin-bottom:28px;}
.endpoints{text-align:left;background:rgba(0,0,0,0.3);border-radius:12px;padding:16px 20px;}
.ep{display:flex;gap:10px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.06);font-size:13px;font-family:monospace;}
.ep:last-child{border:none;}
.method{color:#7c6df0;font-weight:600;width:50px;flex-shrink:0;}
.path{color:#a0a0c0;}
</style></head>
<body><div class="card">
<h1>🤖 Robin</h1>
<p>Personal Voice AI Assistant — Backend API</p>
<div class="badge">● Live on Pioneer AI</div>
<div class="endpoints">
  <div class="ep"><span class="method">POST</span><span class="path">/chat — Send a message to Robin</span></div>
  <div class="ep"><span class="method">GET</span><span class="path">/health — System health check</span></div>
  <div class="ep"><span class="method">GET</span><span class="path">/profile/{user_id} — User profile + calendar</span></div>
  <div class="ep"><span class="method">GET</span><span class="path">/history/{user_id} — Conversation history</span></div>
  <div class="ep"><span class="method">GET</span><span class="path">/analytics/{user_id} — Usage stats</span></div>
  <div class="ep"><span class="method">POST</span><span class="path">/airbyte/sync — Trigger data sync</span></div>
  <div class="ep"><span class="method">GET</span><span class="path">/docs — Interactive API explorer</span></div>
</div>
</div></body></html>"""


@app.get("/health")
async def health():
    ollama_status = "offline"
    try:
        import httpx
        r = await asyncio.wait_for(
            asyncio.create_task(
                asyncio.to_thread(
                    lambda: __import__('httpx').get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=2)
                )
            ), timeout=3
        )
        ollama_status = "online" if r.status_code == 200 else "offline"
    except Exception:
        pass
    return {
        "status": "ok",
        "ollama": ollama_status,
        "pioneer": "configured" if settings.PIONEER_API_KEY else "not_configured",
        "composio": "configured" if settings.COMPOSIO_API_KEY else "not_configured",
    }


@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        result = await orchestrator.run(
            user_id=req.user_id,
            message=req.message,
            smart_mode=req.smart_mode,
        )
        # Ensure everything is JSON-serializable (handles enums, floats etc)
        return {
            "response": str(result.get("response", "")),
            "provider": str(result.get("provider", "pioneer")),
            "run_id": str(result.get("run_id", "")),
            "duration_ms": float(result.get("duration_ms", 0)),
            "tool_executed": result.get("tool_executed"),
        }
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log.error("chat_endpoint_error", error=str(e), traceback=tb)
        # Return proper JSON — never plain-text 500
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=200,  # 200 so JS can parse it
            content={
                "response": f"⚠️ Robin hit an internal error: {str(e)}\n\nCheck the backend terminal for details.",
                "provider": "error",
                "run_id": "",
                "duration_ms": 0,
                "tool_executed": None,
            }
        )


@app.get("/profile/{user_id}")
async def get_profile(user_id: str):
    return get_profile_data(user_id)


@app.put("/profile/update")
async def update_profile(req: ProfileUpdateRequest):
    ch_client.set_user_profile(req.user_id, req.key, req.value)
    return {"status": "ok"}


@app.get("/history/{user_id}")
async def get_history(user_id: str, limit: int = 50):
    conversations = ch_client.get_all_history(user_id, limit=limit)
    return {"conversations": conversations}


@app.get("/analytics/{user_id}")
async def get_analytics(user_id: str):
    count = ch_client.count_messages(user_id)
    return {"user_messages": count, "user_id": user_id}


@app.get("/composio/auth/{user_id}/{app}")
async def composio_auth(user_id: str, app: str):
    from agent.tools import RobinToolset
    toolset = RobinToolset(user_id=user_id)
    url = await toolset.get_auth_url(app)
    return {"auth_url": url}


@app.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Receive audio from browser MediaRecorder, transcribe with Whisper."""
    tmp_input  = tempfile.mktemp(suffix=".webm")
    tmp_wav    = tempfile.mktemp(suffix=".wav")
    FFMPEG     = "/opt/homebrew/bin/ffmpeg"

    try:
        # Save uploaded audio
        data = await audio.read()
        with open(tmp_input, "wb") as f:
            f.write(data)

        # Convert to WAV with ffmpeg
        import subprocess
        result = subprocess.run([
            FFMPEG, "-y", "-i", tmp_input,
            "-ar", "16000", "-ac", "1", "-f", "wav", tmp_wav
        ], capture_output=True, timeout=15)

        if result.returncode != 0:
            err_msg = result.stderr.decode()
            log.error("ffmpeg_failed", error=err_msg)
            lines = [line.strip() for line in err_msg.splitlines() if line.strip()]
            summary = lines[-1] if lines else "Unknown error"
            return JSONResponse({"text": "", "error": f"ffmpeg error: {summary}"})

        # Transcribe with Whisper
        import whisper
        model = whisper.load_model("tiny")
        res   = model.transcribe(tmp_wav, fp16=False)
        text  = res.get("text", "").strip()
        return {"text": text}

    except Exception as e:
        log.error("transcribe_error", error=str(e))
        return JSONResponse({"text": "", "error": str(e)})
    finally:
        for f in [tmp_input, tmp_wav]:
            try: os.remove(f)
            except: pass


@app.post("/speak")
async def speak_text(req: dict):
    """Trigger macOS TTS via 'say' command."""
    import subprocess
    text  = str(req.get("text", ""))[:300]
    clean = text.replace('"', '').replace("'", "")
    try:
        subprocess.Popen(["say", "-v", "Samantha", clean])
        return {"status": "speaking"}
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)})


@app.post("/airbyte/sync")
async def trigger_sync():
    result = await airbyte_client.sync_all()
    return result
