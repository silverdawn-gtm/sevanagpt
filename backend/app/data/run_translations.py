"""Batch translation launcher for scheme data.

Runs pre-translation for selected languages (default: hi, ta, te, kn).
Checks IndicTrans2 health first, falls back to Google Translate automatically.

Usage:
    python -m app.data.run_translations              # default 4 languages
    python -m app.data.run_translations hi ta         # specific languages
    python -m app.data.run_translations --all         # all 23 languages
"""

import asyncio
import logging
import sys
import time

import httpx

from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_LANGS = ["hi", "ta", "te", "kn"]


async def check_indictrans_health() -> bool:
    """Check if IndicTrans2 microservice is reachable."""
    url = settings.INDICTRANS_URL
    if not url:
        logger.info("INDICTRANS_URL not configured — will use Google Translate fallback")
        return False

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{url}/health")
            if resp.status_code == 200:
                logger.info("IndicTrans2 is healthy at %s", url)
                return True
            logger.warning("IndicTrans2 returned %d — will use Google Translate fallback", resp.status_code)
            return False
    except Exception as e:
        logger.warning("IndicTrans2 unreachable (%s) — will use Google Translate fallback", e)
        return False


async def run(langs: list[str]):
    """Run pre-translation for given languages sequentially."""
    from app.data.pre_translate import pre_translate_language

    indictrans_ok = await check_indictrans_health()
    backend = "IndicTrans2" if indictrans_ok else "Google Translate"

    logger.info("=" * 60)
    logger.info("Batch Translation Launcher")
    logger.info("Languages: %s", ", ".join(langs))
    logger.info("Backend:   %s", backend)
    logger.info("=" * 60)

    overall_start = time.time()
    completed = []
    failed = []

    for i, lang in enumerate(langs, 1):
        logger.info("\n[%d/%d] Starting language: %s", i, len(langs), lang)
        lang_start = time.time()

        try:
            await pre_translate_language(lang)
            elapsed = time.time() - lang_start
            completed.append(lang)
            logger.info("[%d/%d] Finished %s in %.1fs", i, len(langs), lang, elapsed)
        except Exception as e:
            elapsed = time.time() - lang_start
            failed.append(lang)
            logger.error("[%d/%d] Failed %s after %.1fs: %s", i, len(langs), lang, elapsed, e)

        # Estimate remaining time
        total_elapsed = time.time() - overall_start
        avg_per_lang = total_elapsed / i
        remaining = avg_per_lang * (len(langs) - i)
        if i < len(langs):
            logger.info("Estimated time remaining: %.0fs (%.1f min)", remaining, remaining / 60)

    total_elapsed = time.time() - overall_start
    logger.info("\n" + "=" * 60)
    logger.info("Translation Complete!")
    logger.info("Total time: %.1fs (%.1f min)", total_elapsed, total_elapsed / 60)
    logger.info("Completed:  %s", ", ".join(completed) if completed else "(none)")
    if failed:
        logger.info("Failed:     %s", ", ".join(failed))
    logger.info("=" * 60)


def main():
    args = sys.argv[1:]

    if "--all" in args:
        from app.data.pre_translate import ALL_LANGS
        langs = ALL_LANGS
    elif args:
        from app.data.pre_translate import ALL_LANGS
        langs = [a for a in args if a in ALL_LANGS]
        if not langs:
            print(f"Invalid languages. Supported: {', '.join(ALL_LANGS)}")
            sys.exit(1)
    else:
        langs = DEFAULT_LANGS

    asyncio.run(run(langs))


if __name__ == "__main__":
    main()
