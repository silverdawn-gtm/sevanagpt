"""Extract English-Malayalam parallel pairs from the database.

Connects to PostgreSQL (localhost:5433) and JOINs schemes with
scheme_translations WHERE lang='ml'. Outputs one JSONL line per
field pair to data/raw/scheme_pairs.jsonl.
"""

import json
from sqlalchemy import create_engine, text
from tqdm import tqdm

import config

def extract():
    engine = create_engine(config.DATABASE_URL)

    query = text("""
        SELECT
            s.id,
            s.name         AS en_name,
            s.description  AS en_description,
            s.benefits     AS en_benefits,
            s.eligibility_criteria  AS en_eligibility_criteria,
            s.application_process   AS en_application_process,
            s.documents_required    AS en_documents_required,
            t.name         AS ml_name,
            t.description  AS ml_description,
            t.benefits     AS ml_benefits,
            t.eligibility_criteria  AS ml_eligibility_criteria,
            t.application_process   AS ml_application_process,
            t.documents_required    AS ml_documents_required
        FROM schemes s
        JOIN scheme_translations t ON s.id = t.scheme_id
        WHERE t.lang = :lang
    """)

    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.RAW_DIR / "scheme_pairs.jsonl"

    total_pairs = 0
    field_counts = {f: 0 for f in config.SCHEME_FIELDS}

    with engine.connect() as conn:
        rows = conn.execute(query, {"lang": config.TARGET_LANG_ISO}).fetchall()

    print(f"Found {len(rows)} schemes with Malayalam translations")

    with open(out_path, "w", encoding="utf-8") as f:
        for row in tqdm(rows, desc="Extracting pairs"):
            row_dict = row._mapping
            for field in config.SCHEME_FIELDS:
                en_val = row_dict.get(f"en_{field}")
                ml_val = row_dict.get(f"ml_{field}")

                # Skip if either side is empty
                if not en_val or not ml_val:
                    continue
                en_val = en_val.strip()
                ml_val = ml_val.strip()
                if not en_val or not ml_val:
                    continue

                record = {
                    "en": en_val,
                    "ml": ml_val,
                    "field": field,
                    "scheme_id": str(row_dict["id"]),
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_pairs += 1
                field_counts[field] += 1

    print(f"\nExtracted {total_pairs} parallel pairs to {out_path}")
    print("Pairs per field:")
    for field, count in field_counts.items():
        print(f"  {field}: {count}")


if __name__ == "__main__":
    extract()
