"""
Demo script for pyannote/speaker-diarization-3.1

Requirements:
1. Install dependencies: uv sync
2. Accept user conditions at:
   - https://huggingface.co/pyannote/segmentation-3.0
   - https://huggingface.co/pyannote/speaker-diarization-3.1
3. Set HUGGINGFACE_ACCESS_TOKEN in .env file (loaded as HF_TOKEN)
"""

import os
from pathlib import Path
import torch
from dotenv import load_dotenv
from pyannote.audio import Pipeline

def main():
    # Load token from .env and set as HF_TOKEN (used by pyannote.audio)
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)

    token = os.environ.get("HUGGINGFACE_ACCESS_TOKEN")
    if not token:
        raise ValueError("Please set HUGGINGFACE_ACCESS_TOKEN in .env file")

    # pyannote.audio 4.x uses HF_TOKEN env var
    os.environ["HF_TOKEN"] = token

    # Load pipeline
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1"
    )

    # Move to GPU if available
    if torch.cuda.is_available():
        pipeline.to(torch.device("cuda"))
        print("Using GPU")
    else:
        print("Using CPU")

    # Run on audio file (replace with your audio file path)
    # Example: pipeline("path/to/your/audio.wav")
    print("Pipeline loaded successfully!")
    print(f"Pipeline: {pipeline}")

    # If you have an audio file, uncomment below:
    # diarization = pipeline("audio.wav")
    # with open("audio.rttm", "w") as rttm:
    #     diarization.write_rttm(rttm)

if __name__ == "__main__":
    main()
