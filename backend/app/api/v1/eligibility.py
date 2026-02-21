from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.eligibility import (
    EligibilityCheckRequest,
    EligibilityOptions,
    EligibilityResponse,
    EligibilityResult,
)
from app.services.eligibility_service import check_eligibility, get_eligibility_options
from app.utils.scheme_translate import translate_scheme_list_items
from app.utils.translations import STATE_TRANSLATIONS, translate_name

router = APIRouter(tags=["eligibility"])


@router.post("/eligibility/check", response_model=EligibilityResponse)
async def eligibility_check(
    body: EligibilityCheckRequest,
    lang: str = Query("en"),
    db: AsyncSession = Depends(get_db),
):
    results = await check_eligibility(db, body)

    if lang != "en" and results:
        items = [r["scheme"] for r in results]
        items = await translate_scheme_list_items(items, lang, db)
        for r, translated_item in zip(results, items):
            r["scheme"] = translated_item

    return EligibilityResponse(
        results=[EligibilityResult(**r) for r in results],
        total=len(results),
        profile=body,
    )


@router.get("/eligibility/options", response_model=EligibilityOptions)
async def eligibility_options(
    lang: str = Query("en"),
    db: AsyncSession = Depends(get_db),
):
    options = await get_eligibility_options(db)

    if lang != "en":
        options["states"] = [
            {**s, "name": translate_name(s["name"], lang, STATE_TRANSLATIONS)}
            for s in options["states"]
        ]

    return EligibilityOptions(**options)
