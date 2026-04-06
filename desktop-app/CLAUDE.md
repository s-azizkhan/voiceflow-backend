# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VoiceFlow is a Tauri desktop app that wraps a Python transcription server (`server.py`). The app provides voice recording and file upload for real-time transcription via a minimal UI. The Python server (which runs separately) handles all transcription using **Moonshine** (on-device, no API keys required).

**Key distinction**: The `desktop-app/` directory contains the Tauri shell (Rust + web frontend). The Python transcription server lives at the repository root as `server.py`.

## Commands

```bash
# Frontend (Vite dev server)
cd desktop-app
npm run dev

# Build Tauri app
npm run tauri build

# Run built Tauri app
open VoiceFlow_0.1.0_aarch64.dmg   # or the generated .app
```

The Tauri app auto-spawns `server.py` from the repository root when launched. In development, the Python server must be started separately:

```bash
# Repository root
cd ..
uv run python server.py        # starts FastAPI on port 8765
```

The Rust backend (`src-tauri/`) manages the Python server lifecycle via `start_server` command.

## Architecture

```
desktop-app/
├── src/                  # Web frontend (vanilla JS + Vite)
│   ├── main.js           # All UI logic, WebSocket/HTTP calls to Python server
│   ├── index.html        # Single-page layout
│   └── styles.css        # Dark theme UI
├── src-tauri/
│   ├── src/
│   │   ├── lib.rs        # Tauri app entry, registers commands
│   │   └── commands/
│   │       ├── mod.rs    # Command module exports
│   │       └── server.rs # start_server + check_server_health commands
│   ├── tauri.conf.json   # Window config, bundle resources, tray icon
│   ├── capabilities/default.json  # Tauri permissions (fs, dialog, global-shortcut, shell)
│   └── Cargo.toml
└── package.json
```

**Server communication** (`src/main.js`):
- `check_server_health` → GET `http://localhost:8765/health`
- `start_server` → spawns `python server.py` from the bundled Resources or adjacent to the binary
- REST: `POST /transcribe/file` for file uploads (MediaRecorder blob)
- WebSocket: `/transcribe` (live streaming), `/vocal` (push-to-talk)

The Tauri app does not embed the Python server — it manages it as a child process and communicates via HTTP/WS on port 8765.

**Bundled resources** (`tauri.conf.json`): `server.py` is copied into the app bundle at `Contents/Resources/server.py` so the Tauri app can spawn it regardless of install location.