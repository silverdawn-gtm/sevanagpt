"""LoRA fine-tuning of IndicTrans2 for Malayalam government scheme translation.

Loads the base model, applies LoRA adapters to attention + FFN layers,
and trains on the prepared parallel dataset using Seq2SeqTrainer.

VRAM estimate: ~2.4GB on RTX 3050 6GB with fp16 + gradient checkpointing.
Training time: ~30-60 min on RTX 3050.
"""

import json
import os

import torch
from datasets import Dataset
from peft import LoraConfig, TaskType, get_peft_model
from transformers import (
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
    EarlyStoppingCallback,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
)

os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["TRUST_REMOTE_CODE"] = "1"

import config

# Try to import IndicProcessor — needed for preprocessing
try:
    from IndicTransToolkit import IndicProcessor
except ImportError:
    print("WARNING: IndicTransToolkit not installed. Install it for proper preprocessing.")
    IndicProcessor = None


def load_jsonl(path):
    """Load JSONL file into list of dicts."""
    data = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def build_dataset(pairs, tokenizer, processor):
    """Build HuggingFace Dataset with tokenized inputs and labels.

    Source text: preprocessed by IndicProcessor (adds "eng_Latn mal_Mlym" prefix)
                 then tokenized via _src_tokenize (default mode).
    Target text: preprocessed by IndicProcessor with is_target=True (no prefix,
                 just normalization + transliteration) then tokenized via
                 _tgt_tokenize (target tokenizer context).
    """
    en_texts = [p["en"] for p in pairs]
    ml_texts = [p["ml"] for p in pairs]

    if processor is not None:
        en_processed = processor.preprocess_batch(
            en_texts, src_lang=config.SOURCE_LANG, tgt_lang=config.TARGET_LANG,
            is_target=False,
        )
        ml_processed = processor.preprocess_batch(
            ml_texts, src_lang=config.TARGET_LANG, tgt_lang=config.TARGET_LANG,
            is_target=True,
        )
    else:
        en_processed = en_texts
        ml_processed = ml_texts

    # Tokenize source (uses _src_tokenize — parses "src_lang tgt_lang text")
    model_inputs = tokenizer(
        en_processed,
        max_length=config.MAX_SEQ_LENGTH,
        truncation=True,
        padding="max_length",
    )

    # Tokenize targets using the target tokenizer (uses _tgt_tokenize)
    with tokenizer.as_target_tokenizer():
        labels = tokenizer(
            ml_processed,
            max_length=config.MAX_SEQ_LENGTH,
            truncation=True,
            padding="max_length",
        )

    # Replace padding token id with -100 so it's ignored in loss
    label_ids = []
    for label in labels["input_ids"]:
        label_ids.append([
            tok if tok != tokenizer.pad_token_id else -100
            for tok in label
        ])

    model_inputs["labels"] = label_ids
    return Dataset.from_dict(model_inputs)


def main():
    print(f"Model: {config.MODEL_NAME}")
    print(f"LoRA rank: {config.LORA_RANK}, alpha: {config.LORA_ALPHA}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    if device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

    # ── Load tokenizer and model ─────────────────────────────────────────
    print("\nLoading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        config.MODEL_NAME,
        trust_remote_code=True,
        cache_dir=config.MODEL_CACHE_DIR,
    )

    print("Loading base model...")
    # Load in float32 — Trainer's fp16 flag handles mixed precision via GradScaler.
    # Loading directly in float16 causes "Attempting to unscale FP16 gradients" errors.
    model = AutoModelForSeq2SeqLM.from_pretrained(
        config.MODEL_NAME,
        trust_remote_code=True,
        cache_dir=config.MODEL_CACHE_DIR,
        torch_dtype=torch.float32,
    )

    # Enable gradient checkpointing to save VRAM
    if config.GRADIENT_CHECKPOINTING:
        model.gradient_checkpointing_enable()

    # ── Apply LoRA ───────────────────────────────────────────────────────
    print("Applying LoRA adapters...")
    lora_config = LoraConfig(
        task_type=TaskType.SEQ_2_SEQ_LM,
        r=config.LORA_RANK,
        lora_alpha=config.LORA_ALPHA,
        lora_dropout=config.LORA_DROPOUT,
        target_modules=config.LORA_TARGET_MODULES,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # ── Initialize IndicProcessor ────────────────────────────────────────
    # Must use inference=True — this mode adds the required "src_lang tgt_lang"
    # prefix to source text and handles placeholder wrapping. The model expects
    # these tags even during training.
    processor = None
    if IndicProcessor is not None:
        print("Initializing IndicProcessor (inference=True)...")
        processor = IndicProcessor(inference=True)

    # ── Load data ────────────────────────────────────────────────────────
    print("\nLoading training data...")
    train_pairs = load_jsonl(config.PROCESSED_DIR / "train.jsonl")
    val_pairs = load_jsonl(config.PROCESSED_DIR / "val.jsonl")
    print(f"  Train: {len(train_pairs)} pairs")
    print(f"  Val: {len(val_pairs)} pairs")

    train_dataset = build_dataset(train_pairs, tokenizer, processor)
    val_dataset = build_dataset(val_pairs, tokenizer, processor)

    # ── Training arguments ───────────────────────────────────────────────
    config.CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)

    training_args = Seq2SeqTrainingArguments(
        output_dir=str(config.CHECKPOINT_DIR),
        num_train_epochs=config.NUM_EPOCHS,
        per_device_train_batch_size=config.BATCH_SIZE,
        per_device_eval_batch_size=config.BATCH_SIZE,
        gradient_accumulation_steps=config.GRADIENT_ACCUMULATION_STEPS,
        learning_rate=config.LEARNING_RATE,
        fp16=config.FP16 and device == "cuda",
        warmup_ratio=config.WARMUP_RATIO,
        weight_decay=config.WEIGHT_DECAY,
        logging_dir=str(config.LOG_DIR),
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        predict_with_generate=True,
        generation_max_length=config.MAX_SEQ_LENGTH,
        save_total_limit=3,
        report_to="tensorboard",
        dataloader_num_workers=0,  # Windows compatibility
        remove_unused_columns=False,
    )

    # ── Trainer ──────────────────────────────────────────────────────────
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        callbacks=[
            EarlyStoppingCallback(early_stopping_patience=config.EARLY_STOPPING_PATIENCE),
        ],
    )

    # ── Train ────────────────────────────────────────────────────────────
    print("\nStarting training...")
    train_result = trainer.train()

    # ── Save final adapter ───────────────────────────────────────────────
    final_dir = config.CHECKPOINT_DIR / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))

    # Save training metrics
    metrics = train_result.metrics
    metrics_path = config.EVAL_DIR / "train_metrics.json"
    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\nTraining complete!")
    print(f"  Final adapter saved to: {final_dir}")
    print(f"  Training metrics: {metrics_path}")
    print(f"  Loss: {metrics.get('train_loss', 'N/A')}")
    print(f"  Runtime: {metrics.get('train_runtime', 0):.0f}s")

    # Report parameter efficiency for paper
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\n  Total parameters: {total_params:,}")
    print(f"  Trainable parameters: {trainable_params:,}")
    print(f"  Trainable %: {100 * trainable_params / total_params:.2f}%")


if __name__ == "__main__":
    main()
