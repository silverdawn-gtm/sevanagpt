import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base

# Many-to-many: schemes <-> states
scheme_states = Table(
    "scheme_states",
    Base.metadata,
    Column("scheme_id", UUID(as_uuid=True), ForeignKey("schemes.id", ondelete="CASCADE"), primary_key=True),
    Column("state_id", UUID(as_uuid=True), ForeignKey("states.id", ondelete="CASCADE"), primary_key=True),
)

# Many-to-many: schemes <-> tags
scheme_tags = Table(
    "scheme_tags",
    Base.metadata,
    Column("scheme_id", UUID(as_uuid=True), ForeignKey("schemes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Category(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False, unique=True)
    slug = Column(String(200), nullable=False, unique=True, index=True)
    icon = Column(String(100), nullable=True)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())

    schemes = relationship("Scheme", back_populates="category")


class State(Base):
    __tablename__ = "states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False, unique=True)
    slug = Column(String(200), nullable=False, unique=True, index=True)
    code = Column(String(10), nullable=False, unique=True)
    is_ut = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    schemes = relationship("Scheme", secondary=scheme_states, back_populates="states")
    ministries = relationship("Ministry", back_populates="state")


class Ministry(Base):
    __tablename__ = "ministries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False, unique=True)
    slug = Column(String(500), nullable=False, unique=True, index=True)
    level = Column(String(20), nullable=False, default="central")  # central / state
    state_id = Column(UUID(as_uuid=True), ForeignKey("states.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    state = relationship("State", back_populates="ministries")
    schemes = relationship("Scheme", back_populates="ministry")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    slug = Column(String(100), nullable=False, unique=True, index=True)

    schemes = relationship("Scheme", secondary=scheme_tags, back_populates="tags")


class Scheme(Base):
    __tablename__ = "schemes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False)
    slug = Column(String(500), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    benefits = Column(Text, nullable=True)
    eligibility_criteria = Column(Text, nullable=True)
    application_process = Column(Text, nullable=True)
    documents_required = Column(Text, nullable=True)
    official_link = Column(String(1000), nullable=True)

    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    ministry_id = Column(UUID(as_uuid=True), ForeignKey("ministries.id"), nullable=True)
    level = Column(String(20), nullable=False, default="central")  # central / state

    # Structured eligibility fields
    target_gender = Column(ARRAY(String), nullable=True)  # ['male', 'female', 'transgender']
    min_age = Column(Integer, nullable=True)
    max_age = Column(Integer, nullable=True)
    target_social_category = Column(ARRAY(String), nullable=True)  # ['SC', 'ST', 'OBC', 'General']
    target_income_max = Column(Float, nullable=True)
    is_disability = Column(Boolean, nullable=True)
    is_student = Column(Boolean, nullable=True)
    is_bpl = Column(Boolean, nullable=True)

    status = Column(String(20), default="active")
    featured = Column(Boolean, default=False)
    source = Column(String(50), default="manual")  # manual, kaggle, datagov, huggingface
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Full-text search vector
    search_vector = Column(
        Text, nullable=True
    )  # We'll use a generated tsvector column via migration

    category = relationship("Category", back_populates="schemes")
    ministry = relationship("Ministry", back_populates="schemes")
    states = relationship("State", secondary=scheme_states, back_populates="schemes")
    tags = relationship("Tag", secondary=scheme_tags, back_populates="schemes")
    faqs = relationship("SchemeFAQ", back_populates="scheme", cascade="all, delete-orphan")
    embedding = relationship("SchemeEmbedding", back_populates="scheme", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_schemes_level", "level"),
        Index("ix_schemes_status", "status"),
    )


class SchemeFAQ(Base):
    __tablename__ = "scheme_faqs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scheme_id = Column(UUID(as_uuid=True), ForeignKey("schemes.id", ondelete="CASCADE"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    display_order = Column(Integer, default=0)

    scheme = relationship("Scheme", back_populates="faqs")


class SchemeEmbedding(Base):
    __tablename__ = "scheme_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scheme_id = Column(UUID(as_uuid=True), ForeignKey("schemes.id", ondelete="CASCADE"), nullable=False, unique=True)
    embedding = Column(Vector(1024), nullable=False)
    text_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    scheme = relationship("Scheme", back_populates="embedding")


class SchemeTranslation(Base):
    __tablename__ = "scheme_translations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scheme_id = Column(UUID(as_uuid=True), ForeignKey("schemes.id", ondelete="CASCADE"), nullable=False)
    lang = Column(String(10), nullable=False)
    name = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    benefits = Column(Text, nullable=True)
    eligibility_criteria = Column(Text, nullable=True)
    application_process = Column(Text, nullable=True)
    documents_required = Column(Text, nullable=True)
    tags_json = Column(JSONB, nullable=True)  # translated tag names as list
    created_at = Column(DateTime, server_default=func.now())

    scheme = relationship("Scheme", backref="translations")

    __table_args__ = (
        Index("ix_scheme_translations_scheme_lang", "scheme_id", "lang", unique=True),
    )
