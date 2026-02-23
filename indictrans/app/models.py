"""Pydantic request/response schemas for the IndicTrans2 API."""

from pydantic import BaseModel, Field


class TranslateRequest(BaseModel):
    text: str = Field(..., description="Text to translate")
    source_lang: str = Field(default="en", description="Source language ISO 639-1 code")
    target_lang: str = Field(..., description="Target language ISO 639-1 code")


class TranslateResponse(BaseModel):
    translated_text: str
    source_lang: str
    target_lang: str


class BatchTranslateRequest(BaseModel):
    texts: list[str] = Field(..., description="List of texts to translate")
    source_lang: str = Field(default="en", description="Source language ISO 639-1 code")
    target_lang: str = Field(..., description="Target language ISO 639-1 code")


class BatchTranslateResponse(BaseModel):
    translated_texts: list[str]
    source_lang: str
    target_lang: str


class HealthResponse(BaseModel):
    status: str
    model: str
    device: str
    ready: bool
