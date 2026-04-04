"""
Live speaker diarization + transcription

Requires:
- pyannote/speaker-diarization-3.1 (already downloaded)
- openai/whisper-tiny for transcription
- Accepted terms at:
  - https://huggingface.co/pyannote/segmentation-3.0
  - https://huggingface.co/pyannote/speaker-diarization-3.1

Usage:
    python live_transcribe.py
"""

import os
import io
import queue
import threading
import wave
import numpy as np
import sounddevice as sd
import torch
import torchaudio
from pathlib import Path
from dotenv import load_dotenv

from pyannote.audio import Pipeline

# ── Config ────────────────────────────────────────────────────────────────────

SAMPLE_RATE = 16000
CHUNK_DURATION_SEC = 5        # seconds per inference chunk
WHISPER_MODEL = "tiny"        # tiny/small/medium/large — smaller = faster
VAD_chunk_duration = 0.5     # pyannote VAD chunk duration

# ── Logging ────────────────────────────────────────────────────────────────────

TRANSCRIPT_LOG = Path(__file__).parent / "transcripts.log"

def log_transcript(text: str, speaker: str = None, chunk_idx: int = None):
    """Append transcript to log file."""
    with open(TRANSCRIPT_LOG, "a", encoding="utf-8") as f:
        if speaker:
            f.write(f"[Chunk {chunk_idx}] {speaker}: {text}\n")
        else:
            f.write(f"[Chunk {chunk_idx}] {text}\n")

# ── Load env ───────────────────────────────────────────────────────────────────

env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

token = os.environ.get("HUGGINGFACE_ACCESS_TOKEN")
os.environ["HF_TOKEN"] = token

# ── Load pipelines ─────────────────────────────────────────────────────────────

print("Loading pipelines (first run downloads Whisper weights)...")

diarization_pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1"
)
if torch.cuda.is_available():
    diarization_pipeline.to(torch.device("cuda"))
    print("Diarization on GPU")
else:
    print("Diarization on CPU")

whisper_model = None  # Will be loaded on demand

print("Pipelines ready.\n")


# ── Audio queue ───────────────────────────────────────────────────────────────

audio_q: queue.Queue[np.ndarray] = queue.Queue()
stop_event = threading.Event()


def audio_callback(indata, frames, time, status):
    if status:
        print(f"[Audio callback] {status}", flush=True)
    audio_q.put(indata.copy()[:, 0])  # mono


def record_audio():
    """Continuously records from microphone and puts chunks into the queue."""
    print(f"Recording from microphone (SR={SAMPLE_RATE})... Press Ctrl+C to stop.\n")
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=int(SAMPLE_RATE * CHUNK_DURATION_SEC),
        callback=audio_callback,
    ):
        while not stop_event.is_set():
            sd.sleep(100)


def chunk_generator():
    """Yields audio chunks from the queue."""
    while not stop_event.is_set():
        try:
            chunk = audio_q.get(timeout=0.5)
            yield chunk
        except queue.Empty:
            continue


# ── Transcription ──────────────────────────────────────────────────────────────

def load_whisper():
    global whisper_model, whisper_processor
    if whisper_model is None:
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
        device = "cuda" if torch.cuda.is_available() else "cpu"
        torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

        whisper_model = AutoModelForSpeechSeq2Seq.from_pretrained(
            "openai/whisper-tiny",
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True,
        ).to(device)
        whisper_processor = AutoProcessor.from_pretrained("openai/whisper-tiny")
        print("Whisper loaded.")
    return whisper_model, whisper_processor


def transcribe_chunk(waveform_np: np.ndarray, sample_rate: int = SAMPLE_RATE) -> str:
    model, processor = load_whisper()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    inputs = processor(
        waveform_np,
        sampling_rate=sample_rate,
        return_tensors="pt"
    ).to(device)

    with torch.no_grad():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=256,
            do_sample=False,
        )
    text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    return text.strip()


# ── Diarization ───────────────────────────────────────────────────────────────

def diarize_chunk(waveform_np: np.ndarray, sample_rate: int = SAMPLE_RATE) -> list:
    """Returns list of (start, end, speaker) tuples for a chunk."""
    waveform_tensor = torch.from_numpy(waveform_np).unsqueeze(0)  # (1, samples)
    audio_dict = {"waveform": waveform_tensor, "sample_rate": sample_rate}

    try:
        dia = diarization_pipeline(audio_dict)
        segments = []
        for turn, _, speaker in dia.speaker_diarization.itertracks(yield_label=True):
            segments.append((float(turn.start), float(turn.end), str(speaker)))
        return segments
    except Exception as e:
        print(f"[Diarization error] {e}")
        return []


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("LIVE SPEAKER DIARIZATION + TRANSCRIPTION")
    print("=" * 60)
    print()

    record_thread = threading.Thread(target=record_audio, daemon=True)
    record_thread.start()

    for i, chunk in enumerate(chunk_generator()):
        if len(chunk) < SAMPLE_RATE * 0.5:  # skip very short chunks
            continue

        print(f"\n--- Chunk {i+1} ({len(chunk)/SAMPLE_RATE:.1f}s) ---")

        # 1. Diarize
        segments = diarize_chunk(chunk)

        # 2. Transcribe whole chunk
        text = transcribe_chunk(chunk)
        print(f"Transcript: {text or '(no speech)'}")

        # 3. Assign text to speaker segments (naive: split by silence / word timing)
        if segments and text:
            # Simple: assign full text to each active speaker segment
            for start, end, speaker in segments:
                print(f"  [{start:.2f}s - {end:.2f}s] {speaker}: {text}")
                log_transcript(text, speaker=speaker, chunk_idx=i+1)
        elif segments:
            for start, end, speaker in segments:
                print(f"  [{start:.2f}s - {end:.2f}s] {speaker}: (silence)")
                log_transcript("(silence)", speaker=speaker, chunk_idx=i+1)
        elif text:
            log_transcript(text, chunk_idx=i+1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopping...")
        stop_event.set()
