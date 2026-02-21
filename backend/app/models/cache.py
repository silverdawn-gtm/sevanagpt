import uuid

from sqlalchemy import Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class TranslationCache(Base):
    __tablename__ = "translation_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hash_key = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256(source_text + src_lang + tgt_lang)
    source_text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=False)
    src_lang = Column(String(10), nullable=False)
    tgt_lang = Column(String(10), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
