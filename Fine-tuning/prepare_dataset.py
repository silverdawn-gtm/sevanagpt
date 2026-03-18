"""Clean, deduplicate, and split parallel data into train/val sets.

Reads:
  - data/raw/scheme_pairs.jsonl (from extract_parallel_data.py)
  - data/raw/glossary.jsonl (from build_glossary.py --finalize, optional)

Outputs:
  - data/processed/train.jsonl
  - data/processed/val.jsonl
  - data/processed/glossary_test.jsonl (held-out glossary for terminology eval)
  - data/stats.json
"""

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import config


def clean_text(text: str) -> str:
    """Strip HTML, normalize Unicode, collapse whitespace."""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove HTML entities
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    # Normalize Unicode to NFC
    text = unicodedata.normalize("NFC", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def sentence_split(text: str) -> list[str]:
    """Split text on sentence boundaries (period, Devanagari danda)."""
    # Split on . or । followed by space or end
    parts = re.split(r"(?<=[.।])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def rough_token_count(text: str) -> int:
    """Approximate token count by splitting on whitespace."""
    return len(text.split())


def load_pairs(path: Path) -> list[dict]:
    """Load JSONL file into list of dicts."""
    pairs = []
    if not path.exists():
        print(f"  {path} not found, skipping")
        return pairs
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                pairs.append(json.loads(line))
    return pairs


def prepare():
    scheme_pairs = load_pairs(config.RAW_DIR / "scheme_pairs.jsonl")
    glossary_pairs = load_pairs(config.RAW_DIR / "glossary.jsonl")

    print(f"Loaded {len(scheme_pairs)} scheme pairs, {len(glossary_pairs)} glossary pairs")

    # ── Step 1: Sentence-split longer descriptions ───────────────────────
    expanded = []
    for pair in scheme_pairs:
        en_text = pair["en"]
        ml_text = pair["ml"]

        # Only split long texts (>200 chars) from description-like fields
        if pair["field"] in ("description", "benefits", "eligibility_criteria",
                              "application_process") and len(en_text) > 200:
            en_sents = sentence_split(en_text)
            ml_sents = sentence_split(ml_text)
            # Only use split if sentence counts match (alignment heuristic)
            if len(en_sents) == len(ml_sents) and len(en_sents) > 1:
                for en_s, ml_s in zip(en_sents, ml_sents):
                    expanded.append({"en": en_s, "ml": ml_s, "field": pair["field"]})
                continue
        expanded.append({"en": en_text, "ml": ml_text, "field": pair["field"]})

    print(f"After sentence splitting: {len(expanded)} pairs")

    # ── Step 2: Clean text ───────────────────────────────────────────────
    cleaned = []
    for pair in expanded:
        en = clean_text(pair["en"])
        ml = clean_text(pair["ml"])
        if en and ml:
            cleaned.append({"en": en, "ml": ml, "field": pair["field"]})

    print(f"After cleaning: {len(cleaned)} pairs")

    # ── Step 3: Filter ───────────────────────────────────────────────────
    filtered = []
    removed_reasons = Counter()
    for pair in cleaned:
        en_tokens = rough_token_count(pair["en"])
        ml_tokens = rough_token_count(pair["ml"])

        # Remove too-short pairs
        if en_tokens < config.MIN_TOKEN_LENGTH or ml_tokens < config.MIN_TOKEN_LENGTH:
            removed_reasons["too_short"] += 1
            continue

        # Remove identical pairs (not actually translated)
        if pair["en"] == pair["ml"]:
            removed_reasons["identical"] += 1
            continue

        # Remove extreme length ratio
        ratio = max(en_tokens, ml_tokens) / max(min(en_tokens, ml_tokens), 1)
        if ratio > config.MAX_LENGTH_RATIO:
            removed_reasons["length_ratio"] += 1
            continue

        filtered.append(pair)

    print(f"After filtering: {len(filtered)} pairs")
    if removed_reasons:
        print(f"  Removed: {dict(removed_reasons)}")

    # ── Step 4: Deduplicate ──────────────────────────────────────────────
    seen = set()
    deduped = []
    for pair in filtered:
        key = (pair["en"].lower(), pair["ml"].lower())
        if key not in seen:
            seen.add(key)
            deduped.append(pair)

    print(f"After deduplication: {len(deduped)} pairs")

    # ── Step 5: Stratified train/val split ───────────────────────────────
    import random
    random.seed(42)

    # Group by field type
    by_field = {}
    for pair in deduped:
        by_field.setdefault(pair["field"], []).append(pair)

    train_set = []
    val_set = []
    for field, pairs in by_field.items():
        random.shuffle(pairs)
        split_idx = int(len(pairs) * config.TRAIN_SPLIT)
        train_set.extend(pairs[:split_idx])
        val_set.extend(pairs[split_idx:])

    random.shuffle(train_set)
    random.shuffle(val_set)

    # ── Step 6: Hold out glossary as separate test set ───────────────────
    glossary_test = []
    for pair in glossary_pairs:
        en = clean_text(pair["en"])
        ml = clean_text(pair["ml"])
        if en and ml:
            glossary_test.append({"en": en, "ml": ml, "field": "glossary"})

    # ── Step 7: Save ─────────────────────────────────────────────────────
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    for name, data in [("train", train_set), ("val", val_set), ("glossary_test", glossary_test)]:
        path = config.PROCESSED_DIR / f"{name}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"  {name}: {len(data)} pairs -> {path}")

    # ── Stats ────────────────────────────────────────────────────────────
    stats = {
        "raw_scheme_pairs": len(scheme_pairs),
        "raw_glossary_pairs": len(glossary_pairs),
        "after_sentence_split": len(expanded),
        "after_cleaning": len(cleaned),
        "after_filtering": len(filtered),
        "after_dedup": len(deduped),
        "train": len(train_set),
        "val": len(val_set),
        "glossary_test": len(glossary_test),
        "removed_reasons": dict(removed_reasons),
        "field_distribution": {
            field: len(pairs) for field, pairs in by_field.items()
        },
    }
    stats_path = config.DATA_DIR / "stats.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"\nStats saved to {stats_path}")


if __name__ == "__main__":
    prepare()
