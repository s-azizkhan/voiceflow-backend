# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Real-time voice transcription backend using **Moonshine** (on-device, no API keys required). Two entry points:

- `live_transcribe.py` — Standalone microphone transcription with local logging to `transcripts.log`
- `server.py` — FastAPI + WebSocket server for remote clients (Bun/Node/etc.)

**Note:** `demo.py` is stale (references pyannote which is no longer used).

## Commands

```bash
# Install dependencies
uv sync

# Standalone live transcription (mic → console + transcripts.log)
.venv\Scripts\python.exe live_transcribe.py

# Start WebSocket API server
.venv\Scripts\python.exe server.py
# Runs on http://0.0.0.0:8765

# WebSocket endpoint: ws://localhost:8765/transcribe
# Events: {"type": "partial"|"final", "text": "..."}
```

**Python interpreter:** Use `.venv\Scripts\python.exe` — system Python lacks `torch` and `moonshine-voice`.

## Architecture

- `server.py` — `TranscriberManager` owns a `MicTranscriber` per WebSocket session. `MoonshineListener` bridges moonshine's sync event callbacks to async WebSocket sends.
- `live_transcribe.py` — Same `MicTranscriber` pattern, blocking loop for local use.
- `transcripts.log` — Appended by both entry points; contains all transcribed text including fillers (um, ah, etc.).

## Dependencies

- `moonshine-voice` — transcription + speaker ID (auto-downloads model on first run)
- `fastapi` + `uvicorn` — HTTP/WS server
- `sounddevice` — audio input
- `torch` — tensor runtime

## Environment

- `.env` — contains `HUGGINGFACE_ACCESS_TOKEN` (used by moonshine for model downloads)
- `.venv/` — Python virtual environment (managed by uv)
- `.python-version` — `3.12`
