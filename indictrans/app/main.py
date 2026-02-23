"""FastAPI app for IndicTrans2 translation microservice."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from . import config
from .translator import load_model, is_ready, translate_batch
from .lang_codes import to_indictrans_code
from .models import (
    TranslateRequest,
    TranslateResponse,
    BatchTranslateRequest,
    BatchTranslateResponse,
    HealthResponse,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup in a thread so it doesn't block the event loop."""
    print("[IndicTrans2] Starting model loading...")
    await asyncio.to_thread(load_model)
    yield


app = FastAPI(
    title="IndicTrans2 Translation Service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok" if is_ready() else "loading",
        model=config.MODEL_NAME,
        device=config.DEVICE,
        ready=is_ready(),
    )


@app.post("/translate", response_model=TranslateResponse)
async def translate_single(req: TranslateRequest):
    if not is_ready():
        raise HTTPException(status_code=503, detail="Model not ready")

    if not to_indictrans_code(req.target_lang):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported target language: {req.target_lang}",
        )

    try:
        results = translate_batch(
            [req.text],
            target_lang=req.target_lang,
            source_lang=req.source_lang,
        )
        return TranslateResponse(
            translated_text=results[0],
            source_lang=req.source_lang,
            target_lang=req.target_lang,
        )
    except Exception as e:
        logger.error("Translation error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/translate/batch", response_model=BatchTranslateResponse)
async def translate_batch_endpoint(req: BatchTranslateRequest):
    if not is_ready():
        raise HTTPException(status_code=503, detail="Model not ready")

    if not req.texts:
        return BatchTranslateResponse(
            translated_texts=[],
            source_lang=req.source_lang,
            target_lang=req.target_lang,
        )

    if not to_indictrans_code(req.target_lang):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported target language: {req.target_lang}",
        )

    try:
        results = translate_batch(
            req.texts,
            target_lang=req.target_lang,
            source_lang=req.source_lang,
        )
        return BatchTranslateResponse(
            translated_texts=results,
            source_lang=req.source_lang,
            target_lang=req.target_lang,
        )
    except Exception as e:
        logger.error("Batch translation error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)
