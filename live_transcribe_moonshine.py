"""
Live speaker diarization + transcription using Moonshine

Requires:
- pip install moonshine-voice
- Model downloaded automatically on first run

Usage:
    python live_transcribe_moonshine.py
"""

import threading
import numpy as np
import sounddevice as sd
import torch
from pathlib import Path
from dotenv import load_dotenv

import moonshine_voice
from moonshine_voice import MicTranscriber, TranscriptEventListener, get_model_for_language

# ── Config ────────────────────────────────────────────────────────────────────

SAMPLE_RATE = 16000

# ── Logging ────────────────────────────────────────────────────────────────────

TRANSCRIPT_LOG = Path(__file__).parent / "transcripts.log"

def log_transcript(text: str, speaker: str = None, line_idx: int = None):
    """Append transcript to log file."""
    with open(TRANSCRIPT_LOG, "a", encoding="utf-8") as f:
        if speaker:
            f.write(f"[{speaker}] {text}\n")
        else:
            f.write(f"{text}\n")

# ── Load env ───────────────────────────────────────────────────────────────────

env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# ── Device ─────────────────────────────────────────────────────────────────────

torch_device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"PyTorch running on: {torch_device.upper()}")

# ── Download / load model ─────────────────────────────────────────────────────

print("Getting Moonshine model for English...")
model_path, model_arch = get_model_for_language("en")
print(f"Model: {model_path}")
print(f"Arch:  {model_arch}")

# ── Moonshine Listener ────────────────────────────────────────────────────────

class LiveTranscriptListener(TranscriptEventListener):
    def __init__(self):
        super().__init__()

    def on_line_started(self, event):
        pass

    def on_line_text_changed(self, event):
        text = event.line.text
        if text:
            print(f"  [transcribing] {text}", flush=True)

    def on_line_completed(self, event):
        text = event.line.text
        if text:
            print(f"  [final] {text}")
            log_transcript(text)

# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("LIVE TRANSCRIPTION (Moonshine)")
    print("=" * 60)
    print()
    print("Press Ctrl+C to stop.\n")

    listener = LiveTranscriptListener()

    transcriber = MicTranscriber(
        model_path=model_path,
        model_arch=model_arch,
        update_interval=0.3,
        device=None,  # None = default microphone
        samplerate=SAMPLE_RATE,
        channels=1,
        blocksize=1024,
    )
    transcriber.add_listener(listener)
    transcriber.start()

    print("Listening... (all output also logged to transcripts.log)\n")

    try:
        while True:
            sd.sleep(500)
    except KeyboardInterrupt:
        print("\nStopping...")
        transcriber.stop()

if __name__ == "__main__":
    main()
