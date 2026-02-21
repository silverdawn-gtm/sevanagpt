from pydantic import BaseModel

from app.schemas.scheme import SchemeListItem


class SearchRequest(BaseModel):
    query: str
    language: str = "en"
    category_slug: str | None = None
    state_slug: str | None = None
    ministry_slug: str | None = None
    level: str | None = None
    tags: list[str] = []
    page: int = 1
    page_size: int = 10


class SearchResult(BaseModel):
    scheme: SchemeListItem
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    query: str


class SuggestResponse(BaseModel):
    suggestions: list[str]
