"""Pre-populate translation cache for all scheme names and descriptions.

Usage:
    python -m app.data.pre_translate hi          # Hindi only
    python -m app.data.pre_translate hi ta bn     # Multiple languages
    python -m app.data.pre_translate --all        # All 11 languages

This makes all subsequent page loads instant for cached languages.
Typically takes ~2-5 minutes per language for ~4600 schemes.
"""

import asyncio
import hashlib
import logging
import sys
import time
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

ALL_LANGS = [
    "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "or", "ur",  # original 11
    "as", "ne", "sa", "sd", "mai", "doi", "kok", "sat", "mni", "bodo", "lus",  # IndicTrans2 additional
]
BATCH_SIZE = 8  # Number of texts per translation chunk (small for IndicTrans GPU)
CHUNK_CHAR_LIMIT = 4500
CONCURRENT_WORKERS = 2  # Parallel translation requests (low to avoid OOM)


def _cache_key(text: str, tgt_lang: str) -> str:
    return hashlib.sha256(f"{text}|en|{tgt_lang}".encode()).hexdigest()


def _google_translate_batch_sync(texts: list[str], tgt_lang: str) -> list[str]:
    """Translate a batch of texts using Google Translate newline concatenation."""
    from deep_translator import GoogleTranslator

    if not texts:
        return []

    combined = "\n".join(texts)
    translator = GoogleTranslator(source="en", target=tgt_lang)

    if len(combined) <= CHUNK_CHAR_LIMIT:
        translated = translator.translate(combined)
        parts = translated.split("\n")
        if len(parts) == len(texts):
            return [p.strip() for p in parts]

    # Fallback or oversized: translate individually
    results = []
    for t in texts:
        try:
            results.append(translator.translate(t))
        except Exception:
            results.append(t)
    return results


async def _translate_batch(texts: list[str], tgt_lang: str) -> list[str]:
    """Translate via IndicTrans2 first, fall back to Google Translate."""
    from app.services import indictrans_client

    result = await indictrans_client.translate_batch(texts, tgt_lang)
    if result is not None:
        return result

    return await asyncio.to_thread(_google_translate_batch_sync, texts, tgt_lang)


async def pre_translate_language(lang: str) -> None:
    """Pre-translate all scheme names and short descriptions for one language."""
    from app.database import async_session
    from app.models import TranslationCache, Scheme

    logger.info("Starting pre-translation for language: %s", lang)
    start = time.time()

    async with async_session() as db:
        # Get all active schemes
        schemes = (
            await db.execute(
                select(Scheme.id, Scheme.name, Scheme.description)
                .where(Scheme.status == "active")
                .order_by(Scheme.name)
            )
        ).all()
        logger.info("Found %d active schemes", len(schemes))

        # Check which are already cached
        all_texts = []
        for s in schemes:
            all_texts.append((s.name or "", "name", s.id))
            desc = (s.description or "")[:300]
            all_texts.append((desc, "field", s.id))

        keys = [_cache_key(t[0], lang) for t in all_texts]
        existing = set()
        try:
            for batch_start in range(0, len(keys), 500):
                batch_keys = keys[batch_start:batch_start + 500]
                rows = (
                    await db.execute(
                        select(TranslationCache.hash_key).where(
                            TranslationCache.hash_key.in_(batch_keys)
                        )
                    )
                ).scalars().all()
                existing.update(rows)
        except Exception:
            pass

        # Filter to uncached texts, deduplicate by hash_key
        seen_keys = set()
        uncached = []
        for i, (text, field_type, sid) in enumerate(all_texts):
            k = keys[i]
            if text and text.strip() and k not in existing and k not in seen_keys:
                uncached.append((i, text, field_type))
                seen_keys.add(k)
        logger.info("Need to translate %d texts (%d already cached)", len(uncached), len(all_texts) - len(uncached))

        if not uncached:
            logger.info("All translations already cached for %s!", lang)
            return

        # Split uncached into batches
        batches = []
        for batch_start in range(0, len(uncached), BATCH_SIZE):
            batches.append(uncached[batch_start:batch_start + BATCH_SIZE])

        # Process batches with concurrent workers and periodic commits
        sem = asyncio.Semaphore(CONCURRENT_WORKERS)
        translated_count = 0
        queue = asyncio.Queue()

        async def _worker(batch_idx, batch):
            batch_texts = [t[1] for t in batch]
            async with sem:
                try:
                    translated = await _translate_batch(batch_texts, lang)
                    await queue.put((batch_idx, batch, translated))
                except Exception as e:
                    logger.error("Batch %d error: %s", batch_idx, e)
                    await queue.put((batch_idx, batch, None))

        # Launch all workers
        tasks = [asyncio.create_task(_worker(i, b)) for i, b in enumerate(batches)]

        # Collect results and commit periodically
        COMMIT_EVERY = CONCURRENT_WORKERS * 2
        pending_count = 0
        completed_batches = 0

        for _ in range(len(batches)):
            batch_idx, batch, translated = await queue.get()
            completed_batches += 1

            if translated:
                for (orig_idx, orig_text, _), trans in zip(batch, translated):
                    if trans and trans != orig_text:
                        key = keys[orig_idx]
                        try:
                            db.add(TranslationCache(
                                id=uuid.uuid4(),
                                hash_key=key,
                                source_text=orig_text[:5000],
                                translated_text=trans,
                                src_lang="en",
                                tgt_lang=lang,
                            ))
                            translated_count += 1
                            pending_count += 1
                        except Exception:
                            pass

            # Commit periodically
            if pending_count >= COMMIT_EVERY * BATCH_SIZE or completed_batches == len(batches):
                try:
                    await db.commit()
                    pending_count = 0
                except Exception:
                    await db.rollback()

            # Log progress
            elapsed = time.time() - start
            rate = translated_count / elapsed if elapsed > 0 else 0
            logger.info(
                "[%s] %d/%d translated (%.0f texts/sec, %.0fs elapsed, batch %d/%d)",
                lang, translated_count, len(uncached), rate, elapsed,
                completed_batches, len(batches),
            )

        # Wait for all workers to finish
        await asyncio.gather(*tasks)

        # Final commit
        try:
            await db.commit()
        except Exception:
            await db.rollback()

        elapsed = time.time() - start
        logger.info("Completed %s: %d translations in %.1fs", lang, translated_count, elapsed)


async def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    if "--all" in args:
        langs = ALL_LANGS
    else:
        langs = [a for a in args if a in ALL_LANGS]
        if not langs:
            print(f"Invalid languages. Supported: {', '.join(ALL_LANGS)}")
            sys.exit(1)

    for lang in langs:
        await pre_translate_language(lang)

    print("\nDone! All subsequent page loads will be instant for cached languages.")


if __name__ == "__main__":
    asyncio.run(main())
