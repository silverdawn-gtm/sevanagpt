"""Centralized configuration for IndicTrans2 Malayalam fine-tuning."""

import os
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = BASE_DIR / "output"
CHECKPOINT_DIR = OUTPUT_DIR / "checkpoints"
LOG_DIR = OUTPUT_DIR / "logs"
EVAL_DIR = OUTPUT_DIR / "eval_results"

# ── Model ────────────────────────────────────────────────────────────────
MODEL_NAME = "ai4bharat/indictrans2-en-indic-dist-200M"
MODEL_CACHE_DIR = os.getenv("INDICTRANS_CACHE_DIR", str(BASE_DIR.parent / "indictrans" / "models"))

# ── LoRA ─────────────────────────────────────────────────────────────────
LORA_RANK = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
LORA_TARGET_MODULES = ["q_proj", "v_proj", "k_proj", "out_proj", "fc1", "fc2"]

# ── Training ─────────────────────────────────────────────────────────────
BATCH_SIZE = 4
GRADIENT_ACCUMULATION_STEPS = 8
LEARNING_RATE = 2e-4
NUM_EPOCHS = 5
FP16 = True
GRADIENT_CHECKPOINTING = True
MAX_SEQ_LENGTH = 128
WARMUP_RATIO = 0.05
WEIGHT_DECAY = 0.01
EARLY_STOPPING_PATIENCE = 3

# ── Database (sync driver for local access, port 5433 maps to container 5432) ─
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://myscheme:myscheme_dev@localhost:5433/myscheme",
)

# ── Languages ────────────────────────────────────────────────────────────
SOURCE_LANG = "eng_Latn"  # IndicTrans2 code for English
TARGET_LANG = "mal_Mlym"  # IndicTrans2 code for Malayalam
TARGET_LANG_ISO = "ml"    # ISO code used in scheme_translations table

# ── IndicTrans service (for glossary baseline translations) ──────────────
INDICTRANS_URL = os.getenv("INDICTRANS_URL", "http://localhost:7860")

# ── Translation fields to extract ────────────────────────────────────────
SCHEME_FIELDS = ["name", "description", "benefits", "eligibility_criteria",
                 "application_process", "documents_required"]

# ── Dataset preparation ─────────────────────────────────────────────────
TRAIN_SPLIT = 0.9
MIN_TOKEN_LENGTH = 3
MAX_LENGTH_RATIO = 3.0
