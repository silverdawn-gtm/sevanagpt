"""Lightweight async HTTP client for the IndicTrans2 microservice.

Returns None on any failure so callers can fall back to Google Translate.
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient | None:
    global _client
    if not settings.INDICTRANS_URL or not settings.INDICTRANS_ENABLED:
        return None
    if _client is None:
        _client = httpx.AsyncClient(base_url=settings.INDICTRANS_URL)
    return _client


async def is_available() -> bool:
    """Check if the IndicTrans2 service is up and model is loaded."""
    client = _get_client()
    if not client:
        return False
    try:
        resp = await client.get("/health", timeout=5.0)
        return resp.status_code == 200 and resp.json().get("ready", False)
    except Exception:
        return False


async def translate_single(text: str, target_lang: str) -> str | None:
    """Translate a single text. Returns None on failure (signals fallback)."""
    client = _get_client()
    if not client:
        return None
    try:
        resp = await client.post(
            "/translate",
            json={"text": text, "source_lang": "en", "target_lang": target_lang},
            timeout=settings.INDICTRANS_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json()["translated_text"]
        logger.debug("IndicTrans2 returned %d for single translate", resp.status_code)
        return None
    except Exception as e:
        logger.debug("IndicTrans2 single translate failed: %s", e)
        return None


async def translate_batch(texts: list[str], target_lang: str) -> list[str] | None:
    """Translate a batch of texts. Returns None on failure (signals fallback)."""
    client = _get_client()
    if not client:
        return None
    try:
        resp = await client.post(
            "/translate/batch",
            json={"texts": texts, "source_lang": "en", "target_lang": target_lang},
            timeout=settings.INDICTRANS_BATCH_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json()["translated_texts"]
        logger.debug("IndicTrans2 returned %d for batch translate", resp.status_code)
        return None
    except Exception as e:
        logger.debug("IndicTrans2 batch translate failed: %s", e)
        return None
