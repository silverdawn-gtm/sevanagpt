"""LLM service — supports Mistral (primary) and Groq (free fallback) for chat.

Embeddings remain Mistral-only (Groq doesn't support embeddings).
Chat uses whichever provider has a configured API key (prefers Mistral).
"""

import asyncio
import functools
import json

import httpx

from app.config import settings

_mistral_client = None


# ── Provider detection ──────────────────────────────────────────────

def mistral_configured() -> bool:
    return bool(settings.MISTRAL_API_KEY)


def groq_configured() -> bool:
    return bool(settings.GROQ_API_KEY)


def chat_configured() -> bool:
    """True if any chat LLM provider is configured."""
    return mistral_configured() or groq_configured()


def is_configured() -> bool:
    """Backward-compat: True if Mistral is configured (needed for embeddings)."""
    return mistral_configured()


# ── Mistral client (for embeddings + chat) ──────────────────────────

def get_mistral_client():
    global _mistral_client
    if _mistral_client is None:
        if not mistral_configured():
            raise RuntimeError("MISTRAL_API_KEY not configured")
        from mistralai import Mistral
        _mistral_client = Mistral(api_key=settings.MISTRAL_API_KEY)
    return _mistral_client


async def _run_sync(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))


# ── Embeddings (Mistral only) ──────────────────────────────────────

async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not mistral_configured():
        raise RuntimeError("MISTRAL_API_KEY not configured — needed for embeddings")
    client = get_mistral_client()
    response = await _run_sync(
        client.embeddings.create,
        model=settings.MISTRAL_EMBED_MODEL,
        inputs=texts,
    )
    return [item.embedding for item in response.data]


async def embed_single(text: str) -> list[float]:
    results = await embed_texts([text])
    return results[0]


# ── Chat completion (Mistral or Groq) ──────────────────────────────

async def _groq_chat(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """Call Groq API (OpenAI-compatible) via httpx."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.GROQ_MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _mistral_chat(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """Call Mistral API."""
    client = get_mistral_client()
    response = await _run_sync(
        client.chat.complete,
        model=settings.MISTRAL_CHAT_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


async def chat_complete(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """Chat completion — tries Mistral first, then Groq."""
    if mistral_configured():
        return await _mistral_chat(messages, temperature, max_tokens)
    if groq_configured():
        return await _groq_chat(messages, temperature, max_tokens)
    raise RuntimeError("No LLM API key configured (set MISTRAL_API_KEY or GROQ_API_KEY)")


async def classify_intent(user_message: str, context: str = "") -> dict:
    """Use LLM to classify user intent for FSM transitions."""
    if not chat_configured():
        raise RuntimeError("No LLM API key configured")

    prompt = f"""Classify the user's intent. Return ONLY a JSON object with these fields:
- "intent": one of ["greeting", "search_scheme", "ask_detail", "check_eligibility", "clarify", "goodbye", "other"]
- "entities": extracted entities like {{"category": "", "state": "", "age": null, "gender": "", "occupation": ""}}

Context from conversation: {context}
User message: {user_message}

Return ONLY valid JSON, no other text."""

    response = await chat_complete(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=256,
    )
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError:
        # Try to extract JSON from response
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(response[start:end])
            except json.JSONDecodeError:
                pass
        return {"intent": "other", "entities": {}}
