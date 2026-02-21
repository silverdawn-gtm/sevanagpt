from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Category, Scheme
from app.schemas.scheme import CategoryOut, SchemeListItem
from app.utils.scheme_translate import translate_scheme_list_items
from app.utils.translations import CATEGORY_TRANSLATIONS, translate_name

router = APIRouter(tags=["categories"])


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    lang: str = Query("en"),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(
            Category,
            func.count(Scheme.id).label("scheme_count"),
        )
        .outerjoin(Scheme, (Scheme.category_id == Category.id) & (Scheme.status == "active"))
        .group_by(Category.id)
        .order_by(Category.display_order, Category.name)
    )
    result = await db.execute(query)
    rows = result.all()
    return [
        CategoryOut(
            id=cat.id,
            name=translate_name(cat.name, lang, CATEGORY_TRANSLATIONS),
            slug=cat.slug,
            icon=cat.icon,
            display_order=cat.display_order,
            scheme_count=count,
        )
        for cat, count in rows
    ]


@router.get("/categories/{slug}")
async def get_category(
    slug: str,
    lang: str = Query("en"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    cat = (await db.execute(select(Category).where(Category.slug == slug))).scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    # Count total
    count_q = select(func.count(Scheme.id)).where(
        Scheme.category_id == cat.id, Scheme.status == "active"
    )
    total = (await db.execute(count_q)).scalar() or 0

    schemes_q = (
        select(Scheme)
        .options(selectinload(Scheme.category), selectinload(Scheme.tags))
        .where(Scheme.category_id == cat.id, Scheme.status == "active")
        .order_by(Scheme.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    schemes = (await db.execute(schemes_q)).unique().scalars().all()

    cat_out = CategoryOut.model_validate(cat)
    cat_out.name = translate_name(cat.name, lang, CATEGORY_TRANSLATIONS)

    items = [SchemeListItem.model_validate(s) for s in schemes]
    items = await translate_scheme_list_items(items, lang, db)

    return {
        "category": cat_out,
        "schemes": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
