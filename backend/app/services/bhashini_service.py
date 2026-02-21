"""Bhashini API wrapper for translation (NMT), speech-to-text (ASR), and text-to-speech (TTS)."""

import hashlib
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import TranslationCache


def is_configured() -> bool:
    return bool(settings.BHASHINI_USER_ID and settings.BHASHINI_API_KEY)


async def _call_bhashini(task_type: str, payload: dict) -> dict:
    """Make a call to Bhashini inference API."""
    if not is_configured():
        raise RuntimeError("Bhashini credentials not configured")

    headers = {
        "userID": settings.BHASHINI_USER_ID,
        "ulcaApiKey": settings.BHASHINI_API_KEY,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            settings.BHASHINI_PIPELINE_URL,
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()


async def translate_text(
    text: str, src_lang: str, tgt_lang: str, session: AsyncSession | None = None
) -> str:
    """Translate text between languages using Bhashini NMT."""
    if src_lang == tgt_lang:
        return text

    # Check cache
    if session:
        cache_key = hashlib.sha256(f"{text}|{src_lang}|{tgt_lang}".encode()).hexdigest()
        cached = (
            await session.execute(
                select(TranslationCache).where(TranslationCache.hash_key == cache_key)
            )
        ).scalar_one_or_none()
        if cached:
            return cached.translated_text

    if not is_configured():
        return text  # Return original if not configured

    payload = {
        "pipelineTasks": [
            {
                "taskType": "translation",
                "config": {
                    "language": {
                        "sourceLanguage": src_lang,
                        "targetLanguage": tgt_lang,
                    }
                },
            }
        ],
        "inputData": {
            "input": [{"source": text}]
        },
    }

    result = await _call_bhashini("translation", payload)
    translated = result["pipelineResponse"][0]["output"][0]["target"]

    # Cache result
    if session:
        session.add(TranslationCache(
            id=uuid.uuid4(),
            hash_key=cache_key,
            source_text=text,
            translated_text=translated,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
        ))
        await session.commit()

    return translated


async def speech_to_text(audio_bytes: bytes, language: str) -> str:
    """Convert speech to text using Bhashini ASR."""
    import base64

    payload = {
        "pipelineTasks": [
            {
                "taskType": "asr",
                "config": {
                    "language": {"sourceLanguage": language},
                    "audioFormat": "wav",
                    "samplingRate": 16000,
                },
            }
        ],
        "inputData": {
            "audio": [{"audioContent": base64.b64encode(audio_bytes).decode()}]
        },
    }

    result = await _call_bhashini("asr", payload)
    return result["pipelineResponse"][0]["output"][0]["source"]


async def text_to_speech(text: str, language: str) -> bytes:
    """Convert text to speech using Bhashini TTS."""
    import base64

    payload = {
        "pipelineTasks": [
            {
                "taskType": "tts",
                "config": {
                    "language": {"sourceLanguage": language},
                    "gender": "female",
                },
            }
        ],
        "inputData": {
            "input": [{"source": text}]
        },
    }

    result = await _call_bhashini("tts", payload)
    audio_b64 = result["pipelineResponse"][0]["audio"][0]["audioContent"]
    return base64.b64decode(audio_b64)
