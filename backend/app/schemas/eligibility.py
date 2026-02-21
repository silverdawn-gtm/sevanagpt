from pydantic import BaseModel

from app.schemas.scheme import SchemeListItem


class EligibilityCheckRequest(BaseModel):
    gender: str | None = None  # male / female / transgender
    age: int | None = None
    state_code: str | None = None
    social_category: str | None = None  # SC / ST / OBC / General
    income: float | None = None
    is_disability: bool | None = None
    is_student: bool | None = None
    is_bpl: bool | None = None


class EligibilityResult(BaseModel):
    scheme: SchemeListItem
    match_score: float  # 0-1 how many criteria matched
    matched_criteria: list[str]


class EligibilityResponse(BaseModel):
    results: list[EligibilityResult]
    total: int
    profile: EligibilityCheckRequest


class EligibilityOptions(BaseModel):
    genders: list[str]
    social_categories: list[str]
    states: list[dict]
