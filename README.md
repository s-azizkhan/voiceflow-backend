# VoiceFlow

Real-time voice transcription server using **Moonshine** (on-device, no API keys required).

## Components

| File | Description |
|------|-------------|
| `voiceflow-server.exe` | Transcription engine (FastAPI + WebSocket) |
| `voiceflow-manager.exe` | System tray + global hotkey controller |

Both executables live in the same installation folder.

## Quick Start

```bash
# Run the manager — it auto-starts the server and registers Ctrl+Alt+V
dist\VoiceFlow\manager\voiceflow-manager.exe
```

The tray icon appears. Press **Ctrl+Alt+V** anywhere to start/stop listening.

## Global Hotkey

| Hotkey | Action |
|--------|--------|
| `Ctrl+Alt+V` (first press) | Start listening — tray icon turns red |
| `Ctrl+Alt+V` (second press) | Stop — transcribed text shown in toast notification |

If no speech is detected, nothing is copied.

## System Tray Menu

Right-click the tray icon:

- **Server: Running/Stopped** — current status
- **Start Server / Stop Server / Restart Server**
- **Open Dashboard** → http://localhost:8765/__dashboard__
- **Open API Root** → http://localhost:8765/
- **Exit**

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Server status |
| `GET` | `/health` | Health check |
| `GET` | `/__dashboard__` | Web control panel |
| `POST` | `/vocal/start` | Start hotkey listening session |
| `POST` | `/vocal/stop` | Stop session, return transcribed text |
| `WS` | `/transcribe` | WebSocket live transcription |
| `POST` | `/__ctrl__/stop` | Stop all WS sessions |

## Build

```bash
# Install deps
uv sync

# Build server
.venv\Scripts\python.exe -m PyInstaller server.spec -y

# Build manager
.venv\Scripts\python.exe -m PyInstaller manager.spec -y

# Run installer (requires Inno Setup 6)
iscc installer\installer.iss
```

## Architecture

- `server.py` — FastAPI + WebSocket server; `MicTranscriber` per session
- `manager.py` — System tray app, hotkey listener, server subprocess manager
- `server.spec` — PyInstaller spec for `voiceflow-server.exe`
- `manager.spec` — PyInstaller spec for `voiceflow-manager.exe`
- `installer.iss` — Inno Setup installer script
- Moonshine model cached at `%LOCALAPPDATA%\moonshine_voice`
