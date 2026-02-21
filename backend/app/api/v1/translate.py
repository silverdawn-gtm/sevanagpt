from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.bhashini_service import translate_text
from app.utils.languages import LANGUAGE_MAP

router = APIRouter(tags=["translate"])


class TranslateRequest(BaseModel):
    text: str
    src_lang: str = "en"
    tgt_lang: str = "hi"


class TranslateResponse(BaseModel):
    translated_text: str
    src_lang: str
    tgt_lang: str


@router.post("/translate", response_model=TranslateResponse)
async def translate(body: TranslateRequest, db: AsyncSession = Depends(get_db)):
    translated = await translate_text(body.text, body.src_lang, body.tgt_lang, session=db)
    return TranslateResponse(
        translated_text=translated,
        src_lang=body.src_lang,
        tgt_lang=body.tgt_lang,
    )


@router.get("/languages")
async def list_languages():
    return list(LANGUAGE_MAP.values())
