from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class CategoryOut(BaseModel):
    id: UUID
    name: str
    slug: str
    icon: str | None = None
    display_order: int = 0
    scheme_count: int = 0

    model_config = {"from_attributes": True}


class StateOut(BaseModel):
    id: UUID
    name: str
    slug: str
    code: str
    is_ut: bool = False
    scheme_count: int = 0

    model_config = {"from_attributes": True}


class MinistryOut(BaseModel):
    id: UUID
    name: str
    slug: str
    level: str = "central"
    scheme_count: int = 0

    model_config = {"from_attributes": True}


class TagOut(BaseModel):
    id: UUID
    name: str
    slug: str

    model_config = {"from_attributes": True}


class FAQOut(BaseModel):
    question: str
    answer: str

    model_config = {"from_attributes": True}


class SchemeListItem(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None = None
    level: str = "central"
    category: CategoryOut | None = None
    tags: list[TagOut] = []
    featured: bool = False

    model_config = {"from_attributes": True}


class SchemeDetail(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None = None
    benefits: str | None = None
    eligibility_criteria: str | None = None
    application_process: str | None = None
    documents_required: str | None = None
    official_link: str | None = None
    level: str = "central"
    target_gender: list[str] | None = None
    min_age: int | None = None
    max_age: int | None = None
    target_social_category: list[str] | None = None
    target_income_max: float | None = None
    is_disability: bool | None = None
    is_student: bool | None = None
    is_bpl: bool | None = None
    # Link enrichment fields
    extra_details: dict[str, Any] | None = None
    link_status: str | None = None
    link_checked_at: datetime | None = None
    launch_date: date | None = None
    application_deadline: date | None = None
    helpline: str | None = None
    benefit_type: str | None = None

    source: str = "manual"
    status: str = "active"
    featured: bool = False
    category: CategoryOut | None = None
    ministry: MinistryOut | None = None
    states: list[StateOut] = []
    tags: list[TagOut] = []
    faqs: list[FAQOut] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PaginatedSchemes(BaseModel):
    items: list[SchemeListItem]
    total: int
    page: int
    page_size: int
    total_pages: int
