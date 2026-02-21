from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Ministry, Scheme
from app.schemas.scheme import MinistryOut, SchemeListItem
from app.utils.scheme_translate import translate_scheme_list_items
from app.utils.translations import MINISTRY_TRANSLATIONS, translate_name

router = APIRouter(tags=["ministries"])


@router.get("/ministries", response_model=list[MinistryOut])
async def list_ministries(
    lang: str = Query("en"),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(
            Ministry,
            func.count(Scheme.id).label("scheme_count"),
        )
        .outerjoin(Scheme, (Scheme.ministry_id == Ministry.id) & (Scheme.status == "active"))
        .group_by(Ministry.id)
        .order_by(Ministry.name)
    )
    result = await db.execute(query)
    return [
        MinistryOut(
            id=m.id,
            name=translate_name(m.name, lang, MINISTRY_TRANSLATIONS),
            slug=m.slug,
            level=m.level,
            scheme_count=count,
        )
        for m, count in result.all()
    ]


@router.get("/ministries/{slug}")
async def get_ministry(
    slug: str,
    lang: str = Query("en"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    ministry = (await db.execute(select(Ministry).where(Ministry.slug == slug))).scalar_one_or_none()
    if not ministry:
        raise HTTPException(status_code=404, detail="Ministry not found")

    # Count total
    count_q = select(func.count(Scheme.id)).where(
        Scheme.ministry_id == ministry.id, Scheme.status == "active"
    )
    total = (await db.execute(count_q)).scalar() or 0

    schemes_q = (
        select(Scheme)
        .options(selectinload(Scheme.category), selectinload(Scheme.tags))
        .where(Scheme.ministry_id == ministry.id, Scheme.status == "active")
        .order_by(Scheme.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    schemes = (await db.execute(schemes_q)).unique().scalars().all()

    ministry_out = MinistryOut.model_validate(ministry)
    ministry_out.name = translate_name(ministry.name, lang, MINISTRY_TRANSLATIONS)

    items = [SchemeListItem.model_validate(s) for s in schemes]
    items = await translate_scheme_list_items(items, lang, db)

    return {
        "ministry": ministry_out,
        "schemes": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
