import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Category, Ministry, Scheme, State, Tag, scheme_states, scheme_tags
from app.schemas.scheme import PaginatedSchemes, SchemeDetail, SchemeListItem
from app.utils.scheme_translate import translate_scheme_detail, translate_scheme_list_items

router = APIRouter(tags=["schemes"])


@router.get("/schemes", response_model=PaginatedSchemes)
async def list_schemes(
    category: str | None = None,
    state: str | None = None,
    ministry: str | None = None,
    level: str | None = None,
    tag: str | None = None,
    search: str | None = None,
    lang: str = Query("en"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Scheme).options(
        selectinload(Scheme.category),
        selectinload(Scheme.tags),
    ).where(Scheme.status == "active")

    if category:
        query = query.join(Scheme.category).where(Category.slug == category)
    if state:
        query = query.join(Scheme.states).where(State.slug == state)
    if ministry:
        query = query.join(Scheme.ministry).where(Ministry.slug == ministry)
    if level:
        query = query.where(Scheme.level == level)
    if tag:
        query = query.join(Scheme.tags).where(Tag.slug == tag)
    if search:
        query = query.where(
            Scheme.name.ilike(f"%{search}%") | Scheme.description.ilike(f"%{search}%")
        )

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    # Paginate
    query = query.order_by(Scheme.featured.desc(), Scheme.name).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    schemes = result.unique().scalars().all()

    items = [SchemeListItem.model_validate(s) for s in schemes]
    items = await translate_scheme_list_items(items, lang, db)

    return PaginatedSchemes(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/schemes/featured", response_model=list[SchemeListItem])
async def featured_schemes(
    lang: str = Query("en"),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Scheme)
        .options(selectinload(Scheme.category), selectinload(Scheme.tags))
        .where(Scheme.featured == True, Scheme.status == "active")
        .order_by(Scheme.name)
        .limit(12)
    )
    result = await db.execute(query)
    schemes = result.unique().scalars().all()

    items = [SchemeListItem.model_validate(s) for s in schemes]
    return await translate_scheme_list_items(items, lang, db)


@router.get("/schemes/{slug}", response_model=SchemeDetail)
async def get_scheme(
    slug: str,
    lang: str = Query("en"),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Scheme)
        .options(
            selectinload(Scheme.category),
            selectinload(Scheme.ministry),
            selectinload(Scheme.states),
            selectinload(Scheme.tags),
            selectinload(Scheme.faqs),
        )
        .where(Scheme.slug == slug)
    )
    result = await db.execute(query)
    scheme = result.unique().scalar_one_or_none()
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")

    detail = SchemeDetail.model_validate(scheme)
    return await translate_scheme_detail(detail, lang, db)
