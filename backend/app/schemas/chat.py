from pydantic import BaseModel

from app.schemas.scheme import SchemeListItem


class ChatMessageRequest(BaseModel):
    message: str
    session_id: str
    language: str = "en"


class SuggestedQuestion(BaseModel):
    text: str


class ChatMessageResponse(BaseModel):
    reply: str
    schemes: list[SchemeListItem] = []
    suggestions: list[SuggestedQuestion] = []
    session_id: str
    fsm_state: str


class ChatVoiceRequest(BaseModel):
    language: str = "hi"
    session_id: str


class ChatVoiceResponse(BaseModel):
    transcript: str
    reply: str
    reply_audio_base64: str | None = None
    schemes: list[SchemeListItem] = []
    suggestions: list[SuggestedQuestion] = []
    session_id: str


class ChatHistoryMessage(BaseModel):
    role: str
    content: str
    content_original: str | None = None

    model_config = {"from_attributes": True}
