"""
VoiceFlow — FastAPI + WebSocket server with built-in web dashboard.

Usage:
    python server.py
    dist\voiceflow-server\voiceflow-server.exe   (portable)
"""

import asyncio
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import torch
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from moonshine_voice import MicTranscriber, TranscriptEventListener, get_model_for_language

# ── Config ────────────────────────────────────────────────────────────────────

SAMPLE_RATE = 16000
PORT = 8765

# ── Load env ───────────────────────────────────────────────────────────────────

if getattr(sys, "frozen", False):
    env_path = Path(sys._MEIPASS) / ".env"
else:
    env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# ── Device ─────────────────────────────────────────────────────────────────────

torch_device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Moonshine on: {torch_device.upper()}")

# ── Load model ─────────────────────────────────────────────────────────────────

print("Loading Moonshine model for English...")
model_path, model_arch = get_model_for_language("en")
print(f"Model: {model_path}")
print(f"Arch:  {model_arch}")

# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(title="VoiceFlow Server")
active_connections: list[WebSocket] = []

# ── Dashboard HTML ─────────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VoiceFlow</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0f1117;color:#e0e0e0;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:40px 20px}
h1{font-size:2rem;font-weight:700;color:#fff;margin-bottom:6px}
.subtitle{color:#666;margin-bottom:36px;font-size:0.9rem}
.card{background:#1a1d27;border:1px solid #252836;border-radius:16px;padding:28px 32px;width:100%;max-width:520px;margin-bottom:20px}
.row{display:flex;align-items:center;gap:12px;margin-bottom:22px}
.dot{width:13px;height:13px;border-radius:50%;background:#e74c3c;transition:background .3s}
.dot.running{background:#2ecc71}
.dot.starting{background:#f39c12;animation:pulse 1s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.state{font-size:1rem;font-weight:600}
.state.running{color:#2ecc71}
.state.stopped{color:#e74c3c}
.state.starting{color:#f39c12}
.btns{display:flex;gap:10px;flex-wrap:wrap}
button{flex:1;min-width:90px;padding:11px 18px;border:none;border-radius:10px;font-size:0.95rem;font-weight:600;cursor:pointer;transition:all .12s}
button:disabled{opacity:.35;cursor:not-allowed}
.b-start{background:#2ecc71;color:#fff}.b-start:hover:not(:disabled){background:#27ae60}
.b-stop{background:#e74c3c;color:#fff}.b-stop:hover:not(:disabled){background:#c0392b}
.b-restart{background:#f39c12;color:#fff}.b-restart:hover:not(:disabled){background:#e67e22}
.info{background:#111318;border-radius:10px;padding:14px;margin-top:18px;font-size:.8rem;color:#555}
.info p{margin:3px 0}
.info span{color:#7a8a9a;font-family:'Consolas',monospace}
.log{background:#090b0f;border:1px solid #1a1d26;border-radius:10px;padding:13px;font-family:'Consolas',8px;height:200px;overflow-y:auto;
     font-size:.78rem;color:#566268;white-space:pre-wrap;width:100%;max-width:520px}
.log-line{margin:2px 0}
.log-ts{color:#3a4550}
</style>
</head>
<body>
<h1>VoiceFlow</h1>
<p class=subtitle>Real-time transcription server</p>

<div class=card>
  <div class=row>
    <div class=dot id=dot></div>
    <div class="state stopped" id=state>Server stopped</div>
  </div>
  <div class=btns>
    <button class="b-stop"    id=b-stop   onclick="act('stop')" disabled>&#9632; Stop</button>
    <button class="b-restart" id=b-restart onclick="act('restart')">&#8635; Restart sessions</button>
  </div>
  <div class=info>
    <p>WebSocket &nbsp;<span>ws://localhost:PORT/transcribe</span></p>
    <p>HTTP API &nbsp;&nbsp;&nbsp;<span>http://localhost:PORT/</span></p>
  </div>
</div>

<div class=log id=log></div>

<script>
const PORT = location.port;
const $ = id => document.getElementById(id);
let sse;

function log(msg) {
  const box = $('log'), ts = new Date().toLocaleTimeString();
  box.appendChild(Object.assign(document.createElement('div'),{className:'log-line',innerHTML:'<span class=log-ts>['+ts+']</span> '+escape(msg)}));
  box.scrollTop = box.scrollHeight;
}

function act(a) {
  log(a + '...');
  fetch('/__ctrl__/'+a,{method:'POST'}).then(r=>r.json()).then(j=>log(j.message||a)).catch(e=>log('err: '+e));
}

function updateState(j) {
  const dot = $('dot'), s = $('state');
  dot.className = 'dot ' + (j.state==='running'?'running':'');
  s.className = 'state ' + j.state;
  s.textContent = j.label;
  $('b-stop').disabled = false;
  $('b-restart').disabled = false;
  j.log.forEach(l=>l&&log(l));
}

function connectSSE() {
  if (sse) sse.close();
  sse = new EventSource('/__ctrl__/stream');
  sse.onmessage = e => log(e.data);
  sse.onerror = () => { sse.close(); setTimeout(connectSSE, 4000); };
}

(async () => {
  let r = await fetch('/__ctrl__/status');
  updateState(await r.json());
  connectSSE();
  setInterval(async () => updateState(await (await fetch('/__ctrl__/status')).json()), 3000);
})();
</script>
</body>
</html>""".replace("location.port", "location.port").replace("PORT", str(PORT))

# ── Dashboard routes ────────────────────────────────────────────────────────────

_log: list[str] = []
_subs: list[asyncio.Queue] = []


def _broadcast(msg: str):
    for q in _subs:
        try:
            q.put_nowait(msg)
        except Exception:
            pass


@app.get("/__dashboard__")
async def dashboard():
    return HTMLResponse(DASHBOARD_HTML)


@app.get("/__ctrl__/status")
async def ctrl_status():
    return JSONResponse({"state": "running", "label": f"Running on port {PORT}", "log": list(_log)[-60:]})


@app.post("/__ctrl__/{action}")
async def ctrl_action(action: str):
    if action == "stop":
        _log.append("Server stop requested via dashboard ...")
        _broadcast("Server stop requested ...")
        for m in managers.values():
            m.stop()
        _log.append("All sessions stopped.")
        _broadcast("All sessions stopped.")
        return JSONResponse({"status": "ok", "message": "Server sessions stopped."})
    elif action == "restart":
        _log.append("Restart requested — reloading session state ...")
        _broadcast("Restart requested ...")
        return JSONResponse({"status": "ok", "message": "Sessions restarted."})
    return JSONResponse({"status": "error", "message": "Unknown action"})


from fastapi.responses import StreamingResponse

@app.get("/__ctrl__/stream")
async def ctrl_stream():
    async def gen():
        q: asyncio.Queue = asyncio.Queue()
        _subs.append(q)
        try:
            while True:
                msg = await q.get()
                yield f"data: {msg}\n\n"
        except Exception:
            pass
        finally:
            _subs.remove(q)
    return StreamingResponse(gen(), media_type="text/event-stream")


# ── Moonshine transcriber ───────────────────────────────────────────────────────

class MoonshineListener(TranscriptEventListener):
    def __init__(self, ws: WebSocket):
        super().__init__()
        self.ws = ws

    async def on_line_started(self, event):
        await self._send({"type": "started", "text": event.line.text})

    async def on_line_text_changed(self, event):
        await self._send({"type": "partial", "text": event.line.text})

    async def on_line_completed(self, event):
        await self._send({"type": "final", "text": event.line.text})

    async def _send(self, data: dict):
        if self.ws in active_connections:
            try:
                await self.ws.send_json(data)
            except Exception:
                pass


class TranscriberManager:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.listener = MoonshineListener(ws)
        self.transcriber = MicTranscriber(
            model_path=model_path, model_arch=model_arch,
            update_interval=0.3, device=None, samplerate=SAMPLE_RATE,
            channels=1, blocksize=1024,
        )
        self._running = False

    async def start(self):
        self.transcriber.add_listener(self.listener)
        self.transcriber.start()
        self._running = True
        while self._running:
            await asyncio.sleep(0.5)

    def stop(self):
        self._running = False
        self.transcriber.stop()


managers: dict[int, TranscriberManager] = {}


@app.websocket("/transcribe")
async def websocket_transcribe(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    manager = TranscriberManager(websocket)
    managers[id(websocket)] = manager
    print(f"[+] Client connected  (total: {len(active_connections)})")
    try:
        await manager.start()
    except WebSocketDisconnect:
        pass
    finally:
        manager.stop()
        if websocket in active_connections:
            active_connections.remove(websocket)
        managers.pop(id(websocket), None)
        print(f"[-] Client disconnected (total: {len(active_connections)})")


@app.get("/")
async def root():
    return JSONResponse({"status": "ok", "model": str(model_path), "device": torch_device})


@app.get("/health")
async def health():
    return JSONResponse({"status": "healthy", "connections": len(active_connections)})


@app.post("/stop")
async def stop_all():
    for m in managers.values():
        m.stop()
    return JSONResponse({"status": "stopped"})


# ── Vocal (hotkey-triggered) transcription ─────────────────────────────────────

class VocalListener(TranscriptEventListener):
    """Accumulates transcription text for the vocal hotkey session."""

    def __init__(self):
        super().__init__()
        self.full_text = ""

    def on_line_started(self, event):
        self.full_text = event.line.text or ""

    def on_line_text_changed(self, event):
        self.full_text = event.line.text or ""

    def on_line_completed(self, event):
        if event.line.text:
            self.full_text = event.line.text

    def get_text(self) -> str:
        return self.full_text.strip()

    def clear(self):
        self.full_text = ""


# Global vocal session state (one at a time)
_vocal_manager: Optional["VocalManager"] = None
_vocal_lock = asyncio.Lock()


class VocalManager:
    """Owns a MicTranscriber for the hotkey-triggered vocal session."""

    def __init__(self):
        self.listener = VocalListener()
        self.transcriber = MicTranscriber(
            model_path=model_path,
            model_arch=model_arch,
            update_interval=0.3,
            device=None,
            samplerate=SAMPLE_RATE,
            channels=1,
            blocksize=1024,
        )
        self._running = False
        self.ws: Optional[WebSocket] = None

    async def start(self, websocket: WebSocket):
        self.ws = websocket
        self.transcriber.add_listener(self.listener)
        self.transcriber.start()
        self._running = True
        while self._running:
            await asyncio.sleep(0.3)

    def stop(self):
        self._running = False
        self.transcriber.stop()

    def get_text(self) -> str:
        return self.listener.get_text()


@app.websocket("/vocal")
async def websocket_vocal(websocket: WebSocket):
    """WebSocket for vocal hotkey session — manager connects here to receive transcription."""
    global _vocal_manager
    await websocket.accept()
    async with _vocal_lock:
        if _vocal_manager is None:
            await websocket.send_json({"type": "error", "text": "no active vocal session"})
            await websocket.close()
            return
        vm = _vocal_manager
        vm.ws = websocket
        try:
            await vm.start(websocket)
        except Exception:
            pass
        finally:
            vm.stop()
            _vocal_manager = None


@app.post("/vocal/start")
async def vocal_start():
    """Start a vocal transcription session. Manager should connect to /vocal WS immediately after."""
    global _vocal_manager
    async with _vocal_lock:
        if _vocal_manager is not None:
            return JSONResponse({"status": "already_listening"})
        _vocal_manager = VocalManager()
        return JSONResponse({"status": "listening"})


@app.post("/vocal/stop")
async def vocal_stop():
    """Stop the active vocal session and return the final transcribed text."""
    global _vocal_manager
    async with _vocal_lock:
        if _vocal_manager is None:
            return JSONResponse({"status": "not_listening", "text": ""})
        vm = _vocal_manager
        _vocal_manager = None
        vm.stop()
        text = vm.get_text()
        return JSONResponse({"status": "stopped", "text": text})


# ── Shutdown ───────────────────────────────────────────────────────────────────

def shutdown_handler(signum, frame):
    print("\nShutting down ...")
    for m in list(managers.values()):
        m.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown_handler)

# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
