from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Scheme
from app.schemas.scheme import SchemeListItem
from app.schemas.search import SearchRequest, SearchResponse, SearchResult, SuggestResponse
from app.services.search_service import hybrid_search
from app.utils.scheme_translate import translate_scheme_list_items

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search_schemes(body: SearchRequest, db: AsyncSession = Depends(get_db)):
    results = await hybrid_search(
        session=db,
        query=body.query,
        category_slug=body.category_slug,
        state_slug=body.state_slug,
        ministry_slug=body.ministry_slug,
        level=body.level,
        limit=body.page_size,
    )

    items = [SchemeListItem.model_validate(scheme) for scheme, score in results]
    scores = [round(score, 4) for scheme, score in results]

    items = await translate_scheme_list_items(items, body.language, db)

    return SearchResponse(
        results=[
            SearchResult(scheme=item, score=score)
            for item, score in zip(items, scores)
        ],
        total=len(items),
        query=body.query,
    )


@router.get("/search/suggest", response_model=SuggestResponse)
async def suggest(q: str = Query(..., min_length=2), db: AsyncSession = Depends(get_db)):
    pattern = f"%{q}%"
    query = (
        select(Scheme.name)
        .where(Scheme.status == "active", Scheme.name.ilike(pattern))
        .limit(8)
    )
    results = (await db.execute(query)).scalars().all()
    return SuggestResponse(suggestions=list(results))
