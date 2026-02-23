"""Pre-download the IndicTrans2 model to the local cache.

Usage:
    python -m download_model        (from the indictrans/ directory)
    make download-model             (from the project root)
"""

from app import config
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

def main() -> None:
    print(f"Model:     {config.MODEL_NAME}")
    print(f"Cache dir: {config.MODEL_CACHE_DIR}")
    print()

    print("Downloading tokenizer...")
    AutoTokenizer.from_pretrained(
        config.MODEL_NAME,
        trust_remote_code=True,
        cache_dir=config.MODEL_CACHE_DIR,
    )
    print("Tokenizer ready.\n")

    print("Downloading model weights (this may take a few minutes)...")
    AutoModelForSeq2SeqLM.from_pretrained(
        config.MODEL_NAME,
        trust_remote_code=True,
        cache_dir=config.MODEL_CACHE_DIR,
    )
    print("Model weights ready.\n")

    print("Done! The model is cached locally and will load without downloading next time.")


if __name__ == "__main__":
    main()
