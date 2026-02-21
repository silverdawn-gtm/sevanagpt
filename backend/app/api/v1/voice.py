"""Voice endpoints — ASR, TTS, and voice chat."""

import base64

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.chat import ChatVoiceResponse
from app.services import bhashini_service
from app.services.chat_service import process_message
from app.utils.rate_limit import voice_limiter, get_client_ip

router = APIRouter(tags=["voice"])


@router.post("/chat/voice", response_model=ChatVoiceResponse)
async def chat_voice(
    request: Request,
    audio: UploadFile = File(...),
    language: str = Form("hi"),
    session_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Full voice chat: audio → ASR → translate → chat → translate → TTS."""
    voice_limiter.check(get_client_ip(request))
    audio_bytes = await audio.read()

    # Step 1: Speech-to-text (ASR)
    try:
        transcript = await bhashini_service.speech_to_text(audio_bytes, language)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Speech recognition failed: {e}")

    if not transcript.strip():
        raise HTTPException(status_code=400, detail="Could not recognize speech")

    # Step 2: Translate to English if needed
    english_text = transcript
    if language != "en":
        try:
            english_text = await bhashini_service.translate_text(
                transcript, language, "en", session=db
            )
        except Exception:
            english_text = transcript  # fallback: use original

    # Step 3: Process through chat pipeline (in English)
    result = await process_message(
        session=db,
        session_id=session_id,
        user_message=english_text,
        language=language,
    )

    # Step 4: Translate reply back to user's language
    reply_text = result["reply"]
    if language != "en":
        try:
            reply_text = await bhashini_service.translate_text(
                result["reply"], "en", language, session=db
            )
        except Exception:
            pass  # keep English reply

    # Step 5: TTS — convert reply to audio
    reply_audio_b64 = None
    try:
        audio_data = await bhashini_service.text_to_speech(reply_text, language)
        reply_audio_b64 = base64.b64encode(audio_data).decode()
    except Exception:
        pass  # no audio reply

    return ChatVoiceResponse(
        transcript=transcript,
        reply=reply_text,
        reply_audio_base64=reply_audio_b64,
        schemes=result["schemes"],
        suggestions=result["suggestions"],
        session_id=session_id,
    )


@router.post("/voice/transcribe")
async def voice_transcribe(
    audio: UploadFile = File(...),
    language: str = Form("hi"),
):
    """Standalone ASR: audio → text."""
    audio_bytes = await audio.read()
    try:
        transcript = await bhashini_service.speech_to_text(audio_bytes, language)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Speech recognition failed: {e}")

    return {"transcript": transcript, "language": language}


@router.post("/voice/synthesize")
async def voice_synthesize(
    text: str = Form(...),
    language: str = Form("hi"),
):
    """Standalone TTS: text → audio (base64)."""
    try:
        audio_data = await bhashini_service.text_to_speech(text, language)
        audio_b64 = base64.b64encode(audio_data).decode()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Speech synthesis failed: {e}")

    return {"audio_base64": audio_b64, "language": language}
