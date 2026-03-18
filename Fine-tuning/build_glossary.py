"""Build English-Malayalam government scheme terminology glossary.

Phase 1 (default): Auto-generates glossary from multiple sources and
outputs data/auto_glossary.csv for manual review.

Phase 2 (--finalize): Reads the reviewed CSV and outputs
data/raw/glossary.jsonl for training.

Sources:
  - frontend/public/locales/ml/common.json (UI terms)
  - backend/app/data/seed.py (categories, states, ministries, tags)
  - Frequent government terms from scheme descriptions
"""

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

import requests
from sqlalchemy import create_engine, text
from tqdm import tqdm

import config

# ── Government terminology patterns ─────────────────────────────────────
# Common Indian government terms that should have standard Malayalam translations
GOV_TERMS = [
    "Below Poverty Line", "BPL", "Above Poverty Line", "APL",
    "Scheduled Caste", "Scheduled Tribe", "Other Backward Class",
    "Economically Weaker Section", "EWS",
    "Direct Benefit Transfer", "DBT",
    "Aadhaar", "ration card", "income certificate",
    "domicile certificate", "caste certificate",
    "Public Distribution System", "PDS",
    "Self Help Group", "SHG",
    "Gram Panchayat", "Block Development Officer",
    "District Collector", "Sub-Divisional Magistrate",
    "Anganwadi", "ASHA worker",
    "Jan Dhan", "Mudra loan",
    "Pradhan Mantri", "Chief Minister",
    "scholarship", "pension", "stipend", "subsidy",
    "beneficiary", "applicant", "eligible",
    "annual income", "family income",
    "bank account", "savings account",
    "disability certificate", "medical certificate",
    "birth certificate", "death certificate",
    "voter ID", "PAN card", "driving license",
    "Central Government", "State Government",
    "Union Territory",
    "Ministry", "Department", "Directorate",
    "empowerment", "welfare", "development",
    "rural", "urban", "tribal",
    "agriculture", "farmer", "fisherman",
    "artisan", "handicraft", "handloom",
    "micro enterprise", "small enterprise",
    "MSME", "startup",
    "health insurance", "life insurance",
    "maternity benefit", "child welfare",
    "old age pension", "widow pension",
    "housing scheme", "financial assistance",
    "skill development", "vocational training",
    "education loan", "tuition fee",
    "drinking water", "sanitation", "toilet",
    "electricity connection", "LPG connection",
    "employment guarantee", "MGNREGA",
]


def _flatten_json(obj, prefix=""):
    """Flatten nested JSON into key-value pairs."""
    pairs = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, str):
                pairs.append((new_key, v))
            elif isinstance(v, dict):
                pairs.extend(_flatten_json(v, new_key))
    return pairs


def extract_ui_terms():
    """Extract EN-ML pairs from locale JSON files."""
    ml_path = config.BASE_DIR.parent / "frontend" / "public" / "locales" / "ml" / "common.json"
    en_path = config.BASE_DIR.parent / "frontend" / "public" / "locales" / "en" / "common.json"

    pairs = []
    if ml_path.exists() and en_path.exists():
        with open(en_path, encoding="utf-8") as f:
            en_data = json.load(f)
        with open(ml_path, encoding="utf-8") as f:
            ml_data = json.load(f)

        en_flat = dict(_flatten_json(en_data))
        ml_flat = dict(_flatten_json(ml_data))

        for key in en_flat:
            if key in ml_flat:
                en_val = en_flat[key].strip()
                ml_val = ml_flat[key].strip()
                # Skip template strings and very short values
                if en_val and ml_val and "{" not in en_val and len(en_val) > 1:
                    pairs.append((en_val, ml_val, "ui_locale"))

    print(f"  UI locale terms: {len(pairs)}")
    return pairs


def extract_seed_terms():
    """Extract category, state, ministry names from seed data."""
    pairs = []
    # We'll just extract the English terms — auto-translate will provide baseline ML
    seed_path = config.BASE_DIR.parent / "backend" / "app" / "data" / "seed.py"
    if not seed_path.exists():
        print("  seed.py not found, skipping")
        return pairs

    content = seed_path.read_text(encoding="utf-8")

    # Extract CATEGORIES
    cat_match = re.findall(r'\("([^"]+)",\s*"[^"]+"\)', content)
    for name in cat_match:
        pairs.append((name, "", "seed_category"))

    # Extract STATES
    state_match = re.findall(r'\("([^"]+)",\s*"[A-Z]{2}",\s*(?:True|False)\)', content)
    for name in state_match:
        pairs.append((name, "", "seed_state"))

    # Extract MINISTRIES (quoted strings in list)
    ministry_section = content.split("MINISTRIES")[1].split("]")[0] if "MINISTRIES" in content else ""
    ministry_match = re.findall(r'"([^"]+)"', ministry_section)
    for name in ministry_match:
        pairs.append((name, "", "seed_ministry"))

    # Extract TAGS
    tag_section = content.split("TAGS")[1].split("]")[0] if "TAGS" in content else ""
    tag_match = re.findall(r'"([^"]+)"', tag_section)
    for name in tag_match:
        pairs.append((name, "", "seed_tag"))

    print(f"  Seed terms: {len(pairs)}")
    return pairs


def extract_frequent_terms():
    """Mine frequent government terms from scheme descriptions."""
    engine = create_engine(config.DATABASE_URL)
    pairs = []

    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT name, description, eligibility_criteria FROM schemes "
            "WHERE description IS NOT NULL LIMIT 2000"
        ))
        rows = result.fetchall()

    # Count occurrences of known government terms
    term_counts = Counter()
    all_text = " ".join(
        " ".join(str(v) for v in row if v) for row in rows
    ).lower()

    for term in GOV_TERMS:
        count = all_text.count(term.lower())
        if count > 0:
            term_counts[term] = count

    for term, count in term_counts.most_common():
        pairs.append((term, "", "freq_mining", count))

    print(f"  Frequent government terms: {len(pairs)}")
    return pairs


def auto_translate_batch(terms, batch_size=8):
    """Translate terms via running IndicTrans2 service."""
    translations = {}
    url = f"{config.INDICTRANS_URL}/translate/batch"

    for i in range(0, len(terms), batch_size):
        batch = terms[i:i + batch_size]
        try:
            resp = requests.post(url, json={
                "texts": batch,
                "target_lang": "ml",
                "source_lang": "en",
            }, timeout=60)
            if resp.status_code == 200:
                results = resp.json().get("translated_texts", [])
                for term, trans in zip(batch, results):
                    translations[term] = trans
            else:
                print(f"  Translation API returned {resp.status_code}: {resp.text[:200]}")
                for term in batch:
                    translations[term] = ""
        except requests.RequestException as e:
            print(f"  Translation API error: {e}")
            for term in batch:
                translations[term] = ""

    return translations


def generate_glossary():
    """Phase 1: Auto-generate glossary CSV for review."""
    print("Extracting terms from sources...")
    all_entries = []

    # Source 1: UI locale pairs (already have ML translations)
    ui_pairs = extract_ui_terms()
    for en, ml, source in ui_pairs:
        all_entries.append({"english": en, "auto_malayalam": ml, "source": source, "frequency": 1})

    # Source 2: Seed data terms (need auto-translation)
    seed_pairs = extract_seed_terms()
    seed_en_terms = [en for en, _, _ in seed_pairs]

    # Source 3: Frequent government terms (need auto-translation)
    freq_pairs = extract_frequent_terms()
    freq_en_terms = [en for en, _, _, _ in freq_pairs]
    freq_counts = {en: count for en, _, _, count in freq_pairs}

    # Auto-translate terms that don't have Malayalam yet
    terms_to_translate = list(set(seed_en_terms + freq_en_terms))
    if terms_to_translate:
        print(f"\nAuto-translating {len(terms_to_translate)} terms via IndicTrans2...")
        translations = auto_translate_batch(terms_to_translate)

        for en, _, source in seed_pairs:
            all_entries.append({
                "english": en,
                "auto_malayalam": translations.get(en, ""),
                "source": source,
                "frequency": 1,
            })

        for en, _, _, count in freq_pairs:
            all_entries.append({
                "english": en,
                "auto_malayalam": translations.get(en, ""),
                "source": "freq_mining",
                "frequency": count,
            })

    # Deduplicate by English term (keep highest frequency)
    seen = {}
    for entry in all_entries:
        key = entry["english"].lower()
        if key not in seen or entry["frequency"] > seen[key]["frequency"]:
            seen[key] = entry
    deduped = sorted(seen.values(), key=lambda x: (-x["frequency"], x["english"]))

    # Write CSV
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = config.DATA_DIR / "auto_glossary.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["english", "auto_malayalam", "source", "frequency"])
        writer.writeheader()
        writer.writerows(deduped)

    print(f"\nGenerated glossary with {len(deduped)} terms: {csv_path}")
    print("Review the CSV, correct Malayalam translations, then run:")
    print("  python build_glossary.py --finalize")


def finalize_glossary():
    """Phase 2: Read reviewed CSV and output glossary.jsonl."""
    csv_path = config.DATA_DIR / "auto_glossary.csv"
    if not csv_path.exists():
        print(f"Error: {csv_path} not found. Run without --finalize first.")
        return

    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.RAW_DIR / "glossary.jsonl"

    count = 0
    with open(csv_path, encoding="utf-8") as f_in, \
         open(out_path, "w", encoding="utf-8") as f_out:
        reader = csv.DictReader(f_in)
        for row in reader:
            en = row["english"].strip()
            ml = row["auto_malayalam"].strip()
            if en and ml:
                record = {"en": en, "ml": ml, "field": "glossary"}
                f_out.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1

    print(f"Finalized glossary: {count} pairs written to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build EN-ML terminology glossary")
    parser.add_argument("--finalize", action="store_true",
                        help="Read reviewed CSV and output glossary.jsonl")
    args = parser.parse_args()

    if args.finalize:
        finalize_glossary()
    else:
        generate_glossary()
