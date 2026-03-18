"""Pre-cache category, ministry, state, gender, and social category translations.

Calls the backend's translate endpoint to warm the translation_cache table
for all short UI-facing strings across all 22 languages.
"""

import requests
import time

BACKEND_URL = "http://localhost:8000/api/v1"

ALL_LANGS = [
    "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "or", "ur",
    "as", "ne", "sa", "sd", "mai", "doi", "kok", "sat", "mni", "bodo", "lus",
]

CATEGORIES = [
    "Agriculture, Rural & Environment",
    "Banking, Financial Services and Insurance",
    "Business & Entrepreneurship",
    "Education & Learning",
    "Health & Wellness",
    "Housing & Shelter",
    "Public Safety, Law & Justice",
    "Science, IT & Communications",
    "Skills & Employment",
    "Social Welfare & Empowerment",
    "Sports & Culture",
    "Transport & Infrastructure",
    "Travel & Tourism",
    "Utility & Sanitation",
    "Women and Child",
    "Youth Affairs",
    "Disability & Accessibility",
    "Minority Affairs",
]

GENDERS = ["male", "female", "transgender"]

SOCIAL_CATEGORIES = ["SC", "ST", "OBC", "General", "EWS"]

LEVELS = ["central", "state"]


def translate_batch(texts, lang):
    """Call the IndicTrans batch API to translate and cache."""
    url = "http://localhost:7860/translate/batch"
    try:
        resp = requests.post(url, json={
            "texts": texts,
            "target_lang": lang,
            "source_lang": "en",
        }, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("translated_texts", [])
    except Exception as e:
        print(f"  Error for {lang}: {e}")
    return None


def cache_via_backend(texts, lang):
    """Translate via backend /translate endpoint which auto-caches."""
    url = f"{BACKEND_URL}/translate"
    results = []
    for text in texts:
        try:
            resp = requests.post(url, json={
                "text": text,
                "target_lang": lang,
            }, timeout=10)
            if resp.status_code == 200:
                results.append(resp.json().get("translated_text", text))
            else:
                results.append(text)
        except Exception:
            results.append(text)
    return results


def main():
    # Collect all strings to pre-cache
    all_strings = CATEGORIES + GENDERS + SOCIAL_CATEGORIES + LEVELS
    print(f"Pre-caching {len(all_strings)} strings across {len(ALL_LANGS)} languages")
    print(f"Total translations: {len(all_strings) * len(ALL_LANGS)}")

    # We don't need states/ministries here - they're fetched via the
    # /categories, /states, /ministries endpoints which already go through
    # translate_name. We just need to ensure the IndicTrans translations
    # are in the translation_cache table.

    for lang in ALL_LANGS:
        print(f"\n[{lang}] Translating {len(all_strings)} strings...")
        result = translate_batch(all_strings, lang)
        if result:
            for src, tgt in zip(all_strings, result):
                if tgt != src:
                    print(f"  {src} -> {tgt}")
        else:
            print(f"  Failed, trying one-by-one...")
            for text in all_strings:
                result = translate_batch([text], lang)
                if result:
                    print(f"  {text} -> {result[0]}")

        # Small delay to avoid overloading GPU
        time.sleep(0.5)

    # Now trigger the backend to cache them by making scheme detail requests
    # with each language. This ensures they go through translate_texts_batch
    # which stores in translation_cache.
    print("\n\nWarming backend cache via scheme detail requests...")
    # Use a scheme that has gender data
    test_slug = "anna-bhagya-yojana-karnataka"
    for lang in ALL_LANGS:
        try:
            resp = requests.get(f"{BACKEND_URL}/schemes/{test_slug}?lang={lang}", timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                gender = data.get("target_gender", [])
                cat = data.get("category", {}).get("name", "")
                print(f"  [{lang}] gender={gender}, category={cat[:30]}")
            else:
                print(f"  [{lang}] HTTP {resp.status_code}")
        except Exception as e:
            print(f"  [{lang}] Error: {e}")
        time.sleep(0.3)

    print("\nDone! All UI strings are now cached.")


if __name__ == "__main__":
    main()
