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
        torch_dtype=torch.float16 if config.DEVICE == "cuda" else torch.float32,
    ).to(config.DEVICE)

    # Load LoRA adapter if configured
    if config.LORA_ADAPTER_PATH and os.path.isdir(config.LORA_ADAPTER_PATH):
        print(f"[IndicTrans2] Loading LoRA adapter from {config.LORA_ADAPTER_PATH}")
        from peft import PeftModel
        _model = PeftModel.from_pretrained(_model, config.LORA_ADAPTER_PATH)
        print("[IndicTrans2] LoRA adapter loaded successfully")

    _model.eval()

    print("[IndicTrans2] Initializing IndicProcessor...")
    _processor = IndicProcessor(inference=True)

    _ready = True
    print("[IndicTrans2] Model loaded successfully! Server is ready.")


def _translate_chunk(
    texts: list[str],
    src_code: str,
    tgt_code: str,
) -> list[str]:
    """Translate a small chunk that fits in GPU memory."""
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
    return _processor.postprocess_batch(decoded, lang=tgt_code)


def translate_batch(
    texts: list[str],
    target_lang: str,
    source_lang: str = "en",
) -> list[str]:
    """Translate a batch of texts from source to target language.

    Automatically chunks large batches to avoid GPU OOM.
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

    # Truncate long texts to avoid OOM
    texts = [t[:500] for t in texts]

    # Process in GPU-friendly chunks
    results = []
    for i in range(0, len(texts), config.MAX_BATCH_SIZE):
        chunk = texts[i : i + config.MAX_BATCH_SIZE]
        try:
            results.extend(_translate_chunk(chunk, src_code, tgt_code))
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                torch.cuda.empty_cache()
                logger.warning("OOM on chunk of %d, falling back to one-by-one", len(chunk))
                for text in chunk:
                    try:
                        results.extend(_translate_chunk([text], src_code, tgt_code))
                    except RuntimeError:
                        torch.cuda.empty_cache()
                        results.append(text)  # Return original on failure
            else:
                raise

    return results
