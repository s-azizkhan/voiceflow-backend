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
import os
try:
    import psutil
    HAS_PSUTIL = True
    process = psutil.Process(os.getpid())
    process.cpu_percent(interval=None) # Initialize CPU tracking
except ImportError:
    HAS_PSUTIL = False
from pathlib import Path
from dotenv import load_dotenv

import moonshine_voice
from moonshine_voice import MicTranscriber, TranscriptEventListener, get_model_for_language

# ── Config ────────────────────────────────────────────────────────────────────

SAMPLE_RATE = 16000

# ── Logging ────────────────────────────────────────────────────────────────────

TRANSCRIPT_LOG = Path(__file__).parent / "transcripts.log"

def print_usage_stats():
    """Print CPU, RAM, and GPU memory usage statistics."""
    stats = []
    if HAS_PSUTIL:
        mem_info = process.memory_info()
        mem_mb = mem_info.rss / (1024 * 1024)
        cpu_percent = process.cpu_percent(interval=None)
        stats.append(f"CPU: {cpu_percent:.1f}%")
        stats.append(f"RAM: {mem_mb:.1f} MB")
    else:
        stats.append("RAM/CPU tracking needs `pip install psutil`")

    if torch.cuda.is_available():
        gpu_allocated = torch.cuda.memory_allocated() / (1024 * 1024)
        gpu_reserved = torch.cuda.memory_reserved() / (1024 * 1024)
        stats.append(f"GPU Mem: {gpu_allocated:.1f}MB alloc, {gpu_reserved:.1f}MB res")
    
    if stats:
        print(f"  [Usage Stats] {' | '.join(stats)}")

def log_transcript(text: str, speaker: str = None, line_idx: int = None):
    """Append transcript to log file."""
    with open(TRANSCRIPT_LOG, "a", encoding="utf-8") as f:
        if speaker:
            f.write(f"[{speaker}] {text}")
        else:
            f.write(f"{text}")

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
            print_usage_stats()

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
        print_usage_stats()

if __name__ == "__main__":
    main()
