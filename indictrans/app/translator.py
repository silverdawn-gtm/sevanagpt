"""IndicTrans2 model loading (singleton) and inference."""

import logging
import os
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from IndicTransToolkit import IndicProcessor

from . import config
from .lang_codes import ENGLISH_CODE, to_indictrans_code

# Allow trust_remote_code without interactive prompt
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["TRUST_REMOTE_CODE"] = "1"

logger = logging.getLogger(__name__)

# Singleton state
_model = None
_tokenizer = None
_processor = None
_ready = False


def is_ready() -> bool:
    return _ready


def load_model() -> None:
    """Load model, tokenizer, and processor into GPU/CPU memory."""
    global _model, _tokenizer, _processor, _ready

    if _ready:
        return

    print(f"[IndicTrans2] Loading model: {config.MODEL_NAME} on {config.DEVICE}")
    print("[IndicTrans2] This may take a few minutes on first run (downloading model)...")

    print(f"[IndicTrans2] Cache directory: {config.MODEL_CACHE_DIR}")

    print("[IndicTrans2] Loading tokenizer...")
    _tokenizer = AutoTokenizer.from_pretrained(
        config.MODEL_NAME,
        trust_remote_code=True,
        cache_dir=config.MODEL_CACHE_DIR,
    )

    print("[IndicTrans2] Loading model weights...")
    _model = AutoModelForSeq2SeqLM.from_pretrained(
        config.MODEL_NAME,
        trust_remote_code=True,
        cache_dir=config.MODEL_CACHE_DIR,
        dtype=torch.float16 if config.DEVICE == "cuda" else torch.float32,
    ).to(config.DEVICE)
    _model.eval()

    print("[IndicTrans2] Initializing IndicProcessor...")
    _processor = IndicProcessor(inference=True)

    _ready = True
    print("[IndicTrans2] Model loaded successfully! Server is ready.")


def translate_batch(
    texts: list[str],
    target_lang: str,
    source_lang: str = "en",
) -> list[str]:
    """Translate a batch of texts from source to target language.

    Args:
        texts: List of texts to translate.
        target_lang: ISO 639-1 target language code.
        source_lang: ISO 639-1 source language code (default: "en").

    Returns:
        List of translated texts, same length as input.
    """
    if not _ready:
        raise RuntimeError("Model not loaded. Call load_model() first.")

    if not texts:
        return []

    # Convert ISO codes to IndicTrans2 codes
    src_code = ENGLISH_CODE if source_lang == "en" else to_indictrans_code(source_lang)
    tgt_code = to_indictrans_code(target_lang)
    if not src_code or not tgt_code:
        raise ValueError(f"Unsupported language pair: {source_lang} -> {target_lang}")

    # Preprocess
    preprocessed = _processor.preprocess_batch(
        texts,
        src_lang=src_code,
        tgt_lang=tgt_code,
    )

    # Tokenize
    inputs = _tokenizer(
        preprocessed,
        truncation=True,
        padding="longest",
        max_length=config.MAX_LENGTH,
        return_tensors="pt",
    ).to(config.DEVICE)

    # Generate (use_cache=False works around a past_key_values bug in the
    # custom IndicTrans2 model code with newer transformers versions)
    with torch.no_grad():
        generated = _model.generate(
            **inputs,
            num_beams=config.NUM_BEAMS,
            num_return_sequences=1,
            max_length=config.MAX_LENGTH,
            use_cache=False,
        )

    # Decode
    decoded = _tokenizer.batch_decode(
        generated,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=True,
    )

    # Postprocess
    result = _processor.postprocess_batch(decoded, lang=tgt_code)

    return result
