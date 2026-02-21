from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Scheme, State, scheme_states
from app.schemas.scheme import SchemeListItem, StateOut
from app.utils.scheme_translate import translate_scheme_list_items
from app.utils.translations import STATE_TRANSLATIONS, translate_name

router = APIRouter(tags=["states"])


@router.get("/states", response_model=list[StateOut])
async def list_states(
    lang: str = Query("en"),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(
            State,
            func.count(scheme_states.c.scheme_id).label("scheme_count"),
        )
        .outerjoin(scheme_states, scheme_states.c.state_id == State.id)
        .group_by(State.id)
        .order_by(State.name)
    )
    result = await db.execute(query)
    return [
        StateOut(
            id=s.id,
            name=translate_name(s.name, lang, STATE_TRANSLATIONS),
            slug=s.slug,
            code=s.code,
            is_ut=s.is_ut,
            scheme_count=count,
        )
        for s, count in result.all()
    ]


@router.get("/states/{slug}")
async def get_state(
    slug: str,
    lang: str = Query("en"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    state = (await db.execute(select(State).where(State.slug == slug))).scalar_one_or_none()
    if not state:
        raise HTTPException(status_code=404, detail="State not found")

    # Count total
    count_q = (
        select(func.count(Scheme.id))
        .join(scheme_states, scheme_states.c.scheme_id == Scheme.id)
        .where(scheme_states.c.state_id == state.id, Scheme.status == "active")
    )
    total = (await db.execute(count_q)).scalar() or 0

    schemes_q = (
        select(Scheme)
        .options(selectinload(Scheme.category), selectinload(Scheme.tags))
        .join(scheme_states, scheme_states.c.scheme_id == Scheme.id)
        .where(scheme_states.c.state_id == state.id, Scheme.status == "active")
        .order_by(Scheme.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    schemes = (await db.execute(schemes_q)).unique().scalars().all()

    state_out = StateOut.model_validate(state)
    state_out.name = translate_name(state.name, lang, STATE_TRANSLATIONS)

    items = [SchemeListItem.model_validate(s) for s in schemes]
    items = await translate_scheme_list_items(items, lang, db)

    return {
        "state": state_out,
        "schemes": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
