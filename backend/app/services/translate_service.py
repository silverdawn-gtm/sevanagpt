"""On-demand translation service with aggressive caching and batch optimization.

Uses deep-translator (Google Translate, free, no API key) as the primary engine.
Batches multiple texts into single API calls via newline concatenation (~13x faster).
Falls back to Bhashini if configured. Caches all results in translation_cache table.
"""

import asyncio
import hashlib
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TranslationCache
from app.services import indictrans_client

logger = logging.getLogger(__name__)

# All supported Indian languages (IndicTrans2 primary, Google Translate fallback)
SUPPORTED_LANGS = {
    "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "or", "ur",  # original 11
    "as", "ne", "sa", "sd", "mai", "doi", "kok", "sat", "mni", "bodo", "lus",  # IndicTrans2 additional
}

# Map our internal language codes to Google Translate codes.
# Missing keys = language not supported by Google Translate (IndicTrans2 only).
GOOGLE_LANG_MAP: dict[str, str] = {
    "hi": "hi", "bn": "bn", "ta": "ta", "te": "te", "mr": "mr",
    "gu": "gu", "kn": "kn", "ml": "ml", "pa": "pa", "or": "or",
    "ur": "ur", "as": "as", "ne": "ne", "sa": "sa", "sd": "sd",
    "doi": "doi", "mai": "mai", "lus": "lus",
    "mni": "mni-Mtei",  # Manipuri — Google uses BCP-47 script subtag
    "kok": "gom",        # Konkani — Google uses Goan Konkani code
    # "bodo" and "sat" are NOT supported by Google Translate
}

# Timeouts
SINGLE_TIMEOUT = 8.0   # seconds per individual translation
BATCH_TIMEOUT = 20.0   # seconds for entire batch operation
MAX_TEXT_LEN = 5000


def _cache_key(text: str, tgt_lang: str) -> str:
    return hashlib.sha256(f"{text}|en|{tgt_lang}".encode()).hexdigest()


def _google_translate_sync(text: str, tgt_lang: str) -> str | None:
    """Synchronous Google Translate via deep-translator.

    Returns None if the language is not supported by Google Translate.
    """
    google_code = GOOGLE_LANG_MAP.get(tgt_lang)
    if not google_code:
        return None

    from deep_translator import GoogleTranslator

    return GoogleTranslator(source="en", target=google_code).translate(text)


def _google_translate_batch_sync(texts: list[str], tgt_lang: str) -> list[str] | None:
    """Translate multiple texts in ONE API call via newline concatenation.

    ~13x faster than individual calls. Falls back to individual on split failure.
    Returns None if the language is not supported by Google Translate.
    """
    google_code = GOOGLE_LANG_MAP.get(tgt_lang)
    if not google_code:
        return None

    from deep_translator import GoogleTranslator

    if not texts:
        return []
    if len(texts) == 1:
        return [GoogleTranslator(source="en", target=google_code).translate(texts[0])]

    combined = "\n".join(texts)
    translated = GoogleTranslator(source="en", target=google_code).translate(combined)
    parts = translated.split("\n")

    # If newline split matches, we're good
    if len(parts) == len(texts):
        return [p.strip() for p in parts]

    # Fallback: translate individually
    logger.debug("Batch split mismatch (%d vs %d), falling back to individual", len(parts), len(texts))
    results = []
    translator = GoogleTranslator(source="en", target=google_code)
    for t in texts:
        try:
            results.append(translator.translate(t))
        except Exception:
            results.append(t)
    return results


async def translate_text(
    text: str,
    tgt_lang: str,
    db: AsyncSession | None = None,
) -> str:
    """Translate English text to target language with caching and timeout."""
    if not text or not text.strip() or tgt_lang == "en" or tgt_lang not in SUPPORTED_LANGS:
        return text

    source = text[:MAX_TEXT_LEN]
    key = _cache_key(source, tgt_lang)

    # Check cache
    if db:
        try:
            cached = (
                await db.execute(
                    select(TranslationCache.translated_text).where(
                        TranslationCache.hash_key == key
                    )
                )
            ).scalar_one_or_none()
            if cached:
                return cached
        except Exception:
            pass

    # Translate: try IndicTrans2 first, fall back to Google Translate
    translated = await indictrans_client.translate_single(source, tgt_lang)
    if translated is not None:
        logger.debug("IndicTrans2 translated text for lang=%s (len=%d)", tgt_lang, len(source))
    else:
        logger.debug("IndicTrans2 returned None for lang=%s, trying Google Translate", tgt_lang)
        if tgt_lang not in GOOGLE_LANG_MAP:
            logger.debug("Lang %s not supported by Google Translate and IndicTrans2 unavailable", tgt_lang)
            return text
        try:
            translated = await asyncio.wait_for(
                asyncio.to_thread(_google_translate_sync, source, tgt_lang),
                timeout=SINGLE_TIMEOUT,
            )
            if translated is None:
                return text
        except asyncio.TimeoutError:
            logger.warning("Translation timed out for lang=%s (text len=%d)", tgt_lang, len(source))
            return text
        except Exception as e:
            logger.warning("Google translation failed for lang=%s: %s", tgt_lang, e)
            return text

    # Cache the result
    if db and translated and translated != source:
        try:
            db.add(TranslationCache(
                id=uuid.uuid4(),
                hash_key=key,
                source_text=source,
                translated_text=translated,
                src_lang="en",
                tgt_lang=tgt_lang,
            ))
            await db.commit()
        except Exception:
            await db.rollback()

    return translated


async def _cache_lookup_batch(
    texts: list[str], tgt_lang: str, db: AsyncSession
) -> tuple[list[str | None], list[int]]:
    """Look up cached translations for a batch. Returns (results, uncached_indices)."""
    results: list[str | None] = [None] * len(texts)
    uncached_indices: list[int] = []
    keys = [_cache_key(t[:MAX_TEXT_LEN], tgt_lang) if t and t.strip() else "" for t in texts]

    try:
        non_empty_keys = [k for k in keys if k]
        if non_empty_keys:
            rows = (
                await db.execute(
                    select(TranslationCache.hash_key, TranslationCache.translated_text).where(
                        TranslationCache.hash_key.in_(non_empty_keys)
                    )
                )
            ).all()
            cache_map = {row[0]: row[1] for row in rows}

            for i, (text, key) in enumerate(zip(texts, keys)):
                if not text or not text.strip():
                    results[i] = text or ""
                elif key in cache_map:
                    results[i] = cache_map[key]
                else:
                    uncached_indices.append(i)
        else:
            uncached_indices = [i for i, t in enumerate(texts) if t and t.strip()]
    except Exception:
        uncached_indices = [i for i, t in enumerate(texts) if t and t.strip()]

    # Mark empty texts
    for i in range(len(texts)):
        if results[i] is None and i not in uncached_indices:
            results[i] = texts[i] or ""

    return results, uncached_indices


async def _cache_translations(
    texts: list[str], translated: list[str], tgt_lang: str, db: AsyncSession
) -> None:
    """Cache a batch of translations."""
    for src, trans in zip(texts, translated):
        if src and trans and trans != src:
            try:
                key = _cache_key(src[:MAX_TEXT_LEN], tgt_lang)
                db.add(TranslationCache(
                    id=uuid.uuid4(),
                    hash_key=key,
                    source_text=src[:MAX_TEXT_LEN],
                    translated_text=trans,
                    src_lang="en",
                    tgt_lang=tgt_lang,
                ))
            except Exception:
                pass
    try:
        await db.commit()
    except Exception:
        await db.rollback()


async def translate_texts_batch(
    texts: list[str],
    tgt_lang: str,
    db: AsyncSession | None = None,
) -> list[str]:
    """Translate multiple texts with batch optimization and caching.

    Uses newline concatenation to batch texts into fewer API calls (~13x faster).
    Chunks by character limit (4500 chars per batch) for reliability.
    Returns list of translated texts in the same order.
    """
    if tgt_lang == "en" or tgt_lang not in SUPPORTED_LANGS:
        return texts

    # Step 1: Check cache for all texts
    if db:
        results, uncached_indices = await _cache_lookup_batch(texts, tgt_lang, db)
    else:
        results = [None] * len(texts)
        uncached_indices = [i for i, t in enumerate(texts) if t and t.strip()]
        for i in range(len(texts)):
            if results[i] is None and i not in uncached_indices:
                results[i] = texts[i] or ""

    if not uncached_indices:
        return [r or "" for r in results]

    # Step 2: Group uncached texts into chunks for batch translation
    uncached_texts = [texts[i][:MAX_TEXT_LEN] for i in uncached_indices]
    chunks: list[tuple[list[int], list[str]]] = []
    current_indices: list[int] = []
    current_texts: list[str] = []
    current_len = 0
    CHUNK_LIMIT = 4500

    for ui, text in zip(uncached_indices, uncached_texts):
        text_len = len(text) + 1  # +1 for newline separator
        if current_len + text_len > CHUNK_LIMIT and current_texts:
            chunks.append((list(current_indices), list(current_texts)))
            current_indices = []
            current_texts = []
            current_len = 0
        current_indices.append(ui)
        current_texts.append(text)
        current_len += text_len

    if current_texts:
        chunks.append((current_indices, current_texts))

    # Step 3: Translate chunks with overall timeout
    async def _translate_chunk(indices: list[int], chunk_texts: list[str]) -> list[tuple[int, str]]:
        # Try IndicTrans2 first, fall back to Google Translate
        try:
            translated = await indictrans_client.translate_batch(chunk_texts, tgt_lang)
            if translated is None:
                translated = await asyncio.to_thread(
                    _google_translate_batch_sync, chunk_texts, tgt_lang
                )
            if translated is None:
                # Language not supported by Google Translate
                logger.debug("No translation engine available for lang=%s", tgt_lang)
                return list(zip(indices, chunk_texts))
            return list(zip(indices, translated))
        except Exception as e:
            logger.warning("Chunk translation failed for lang=%s: %s", tgt_lang, e)
            return list(zip(indices, chunk_texts))

    try:
        tasks = [_translate_chunk(idx, txt) for idx, txt in chunks]
        done = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=BATCH_TIMEOUT,
        )

        all_to_cache_src: list[str] = []
        all_to_cache_trans: list[str] = []

        for item in done:
            if isinstance(item, Exception):
                logger.warning("Batch chunk raised exception for lang=%s: %s", tgt_lang, item)
                continue
            if isinstance(item, list):
                for idx, translated in item:
                    results[idx] = translated
                    all_to_cache_src.append(texts[idx][:MAX_TEXT_LEN])
                    all_to_cache_trans.append(translated)

        # Cache all new translations
        if db and all_to_cache_src:
            await _cache_translations(all_to_cache_src, all_to_cache_trans, tgt_lang, db)

    except asyncio.TimeoutError:
        logger.warning("Batch translation timed out for lang=%s (%d texts)", tgt_lang, len(uncached_indices))
    except Exception as e:
        logger.warning("Batch translation error for lang=%s: %s", tgt_lang, e)

    # Fill any remaining None values with original text
    return [results[i] if results[i] is not None else (texts[i] or "") for i in range(len(texts))]
