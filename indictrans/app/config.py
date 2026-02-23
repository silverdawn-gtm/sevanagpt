"""Configuration for IndicTrans2 microservice."""

import os
from pathlib import Path

import torch

def _default_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    print("[IndicTrans2] CUDA not available, falling back to CPU")
    return "cpu"

# Model — 200M distilled variant fits on GTX 1650 (4GB VRAM) in float16
MODEL_NAME: str = os.getenv("INDICTRANS_MODEL", "ai4bharat/indictrans2-en-indic-dist-200M")

# Local model cache — defaults to indictrans/models/ in the project
_PROJECT_DIR = Path(__file__).resolve().parent.parent  # indictrans/
MODEL_CACHE_DIR: str = os.getenv("INDICTRANS_CACHE_DIR", str(_PROJECT_DIR / "models"))
DEVICE: str = os.getenv("INDICTRANS_DEVICE", _default_device())

# Inference
MAX_LENGTH: int = int(os.getenv("INDICTRANS_MAX_LENGTH", "256"))
NUM_BEAMS: int = int(os.getenv("INDICTRANS_NUM_BEAMS", "5"))

# Server
HOST: str = os.getenv("INDICTRANS_HOST", "0.0.0.0")
PORT: int = int(os.getenv("INDICTRANS_PORT", "7860"))
