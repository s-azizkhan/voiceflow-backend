# voiceflow-backend

Real-time voice transcription backend using **Moonshine** (on-device, no API keys required).

## Portable Executable (recommended)

```bash
# Build
.venv\Scripts\python.exe -m PyInstaller server.spec -y

# Run
dist\voiceflow-server\voiceflow-server.exe
```

The `.exe` auto-starts on `http://0.0.0.0:8765`.

## Web Dashboard

Open **http://localhost:8765/__dashboard__** in your browser to:
- View server status
- Stop active transcription sessions
- Restart sessions

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Server status + model info |
| `GET` | `/__dashboard__` | Web control panel |
| `GET` | `/health` | Health check |
| `GET` | `/__ctrl__/status` | Control API status |
| `POST` | `/__ctrl__/stop` | Stop active sessions |
| `POST` | `/__ctrl__/restart` | Restart sessions |
| `WS` | `/transcribe` | WebSocket live transcription |

**WebSocket** — connect to `ws://localhost:8765/transcribe`, receive events:

```json
{ "type": "partial", "text": "hello wor" }
{ "type": "final",   "text": "hello world" }
```

## Development

```bash
# Install dependencies
uv sync

# Run directly
.venv\Scripts\python.exe server.py
```

## Architecture

- `server.py` — FastAPI + WebSocket server with built-in web dashboard
- `server.spec` — PyInstaller spec for portable `.exe`
- `transcripts.log` — Appended by both entry points
- Moonshine model downloaded on first run (~300 MB, cached in `%LOCALAPPDATA%\moonshine_voice`)
