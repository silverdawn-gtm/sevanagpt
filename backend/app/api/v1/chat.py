from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.chat import ChatHistoryMessage, ChatMessageRequest, ChatMessageResponse
from app.services.chat_service import get_chat_history, process_message, reset_conversation
from app.utils.rate_limit import chat_limiter, get_client_ip

router = APIRouter(tags=["chat"])


@router.post("/chat/message", response_model=ChatMessageResponse)
async def chat_message(request: Request, body: ChatMessageRequest, db: AsyncSession = Depends(get_db)):
    chat_limiter.check(get_client_ip(request))
    result = await process_message(
        session=db,
        session_id=body.session_id,
        user_message=body.message,
        language=body.language,
    )
    return ChatMessageResponse(**result)


@router.get("/chat/history/{session_id}", response_model=list[ChatHistoryMessage])
async def chat_history(session_id: str, db: AsyncSession = Depends(get_db)):
    history = await get_chat_history(db, session_id)
    return history


@router.post("/chat/reset/{session_id}")
async def chat_reset(session_id: str, db: AsyncSession = Depends(get_db)):
    success = await reset_conversation(db, session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "ok", "message": "Conversation reset"}
