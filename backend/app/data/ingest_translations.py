"""Pre-populate scheme_translations by re-fetching schemes from MyScheme API in each language.

The MyScheme API returns translated scheme names, descriptions, and tags when
called with lang=hi/ta/etc. This script fetches all schemes for each target
language and caches the translations in the scheme_translations table.

Usage:
    python -m app.data.ingest_translations          # all 11 languages
    python -m app.data.ingest_translations hi ta     # specific languages only
"""

import asyncio
import sys
import time
import uuid

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Scheme
from app.models.scheme import SchemeTranslation
from app.utils.slug import slugify

API_BASE = "https://api.myscheme.gov.in/search/v6"
API_KEY = "tYTy5eEhlu9rFjyxuCr7ra7ACp4dv1RH8gWuHTDc"
HEADERS = {
    "x-api-key": API_KEY,
    "Origin": "https://www.myscheme.gov.in",
    "Referer": "https://www.myscheme.gov.in/",
    "User-Agent": "Mozilla/5.0 (compatible; SevanaGPT/1.0)",
}
BATCH_SIZE = 50

TARGET_LANGUAGES = ["hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "or", "ur"]


async def fetch_schemes_in_lang(lang: str) -> list[dict]:
    """Fetch all schemes from MyScheme API in a specific language."""
    all_items = []
    offset = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        # First request to get total
        resp = await client.get(
            f"{API_BASE}/schemes",
            params={"lang": lang, "q": "", "keyword": "", "sort": "", "from": 0, "size": BATCH_SIZE},
            headers=HEADERS,
        )
        resp.raise_for_status()
        data = resp.json()
        total = data["data"]["summary"]["total"]
        items = data["data"]["hits"].get("items", [])
        all_items.extend(items)
        offset += BATCH_SIZE
        print(f"  [{lang}] Total available: {total}, fetched batch 1: {len(items)}")

        batch_num = 2
        while offset < total:
            await asyncio.sleep(0.3)
            try:
                resp = await client.get(
                    f"{API_BASE}/schemes",
                    params={"lang": lang, "q": "", "keyword": "", "sort": "", "from": offset, "size": BATCH_SIZE},
                    headers=HEADERS,
                )
                resp.raise_for_status()
                data = resp.json()
                items = data["data"]["hits"].get("items", [])
                if not items:
                    break
                all_items.extend(items)
                if batch_num % 20 == 0:
                    print(f"  [{lang}] Fetched batch {batch_num}: total so far {len(all_items)}")
            except Exception as e:
                print(f"  [{lang}] Error at offset {offset}: {e}, retrying...")
                await asyncio.sleep(2)
                try:
                    resp = await client.get(
                        f"{API_BASE}/schemes",
                        params={"lang": lang, "q": "", "keyword": "", "sort": "", "from": offset, "size": BATCH_SIZE},
                        headers=HEADERS,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    items = data["data"]["hits"].get("items", [])
                    all_items.extend(items)
                except Exception as e2:
                    print(f"  [{lang}] Retry failed at offset {offset}: {e2}, skipping")

            offset += BATCH_SIZE
            batch_num += 1

    print(f"  [{lang}] Fetch complete: {len(all_items)} schemes")
    return all_items


async def ingest_language(session: AsyncSession, lang: str, slug_to_scheme: dict[str, Scheme]):
    """Fetch translations for one language and insert into scheme_translations."""
    print(f"\n{'─' * 40}")
    print(f"Processing language: {lang}")
    print(f"{'─' * 40}")

    start = time.time()
    raw_schemes = await fetch_schemes_in_lang(lang)
    print(f"  Fetched in {time.time() - start:.1f}s")

    # Clear existing translations for this language
    await session.execute(
        delete(SchemeTranslation).where(SchemeTranslation.lang == lang)
    )
    await session.flush()

    matched = 0
    unmatched = 0
    batch = []

    for item in raw_schemes:
        fields = item.get("fields", {})
        slug = fields.get("slug", "")
        if not slug:
            name = fields.get("schemeName", "").strip()
            if name:
                slug = slugify(name)

        if not slug or slug not in slug_to_scheme:
            unmatched += 1
            continue

        scheme = slug_to_scheme[slug]
        translated_name = fields.get("schemeName", "").strip()
        translated_desc = fields.get("briefDescription", "").strip()
        translated_tags = fields.get("tags", [])

        # Skip if the translation is identical to English (no actual translation)
        if translated_name == scheme.name and translated_desc == (scheme.description or ""):
            unmatched += 1
            continue

        batch.append(SchemeTranslation(
            id=uuid.uuid4(),
            scheme_id=scheme.id,
            lang=lang,
            name=translated_name or None,
            description=translated_desc or None,
            tags_json=translated_tags if translated_tags else None,
        ))
        matched += 1

        if len(batch) >= 500:
            session.add_all(batch)
            await session.flush()
            batch.clear()

    if batch:
        session.add_all(batch)
        await session.flush()

    await session.commit()
    print(f"  [{lang}] Done: {matched} translations saved, {unmatched} unmatched/skipped")


async def ingest(languages: list[str] | None = None):
    """Main entry point for translation ingestion."""
    langs = languages or TARGET_LANGUAGES

    print("=" * 60)
    print("Scheme Translation Ingestion")
    print(f"Languages: {', '.join(langs)}")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Load all schemes for slug matching
        all_schemes = (await session.execute(select(Scheme))).scalars().all()
        slug_to_scheme = {s.slug: s for s in all_schemes}
        print(f"Loaded {len(slug_to_scheme)} schemes for matching")

        start = time.time()
        for lang in langs:
            await ingest_language(session, lang, slug_to_scheme)

        elapsed = time.time() - start
        print(f"\n{'=' * 60}")
        print(f"All done! Processed {len(langs)} languages in {elapsed:.1f}s")
        print(f"{'=' * 60}")

    await engine.dispose()


if __name__ == "__main__":
    # Accept optional language codes as CLI args
    args = sys.argv[1:]
    valid_langs = [a for a in args if a in TARGET_LANGUAGES]
    asyncio.run(ingest(valid_langs if valid_langs else None))
