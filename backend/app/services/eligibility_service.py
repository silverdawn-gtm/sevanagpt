"""Eligibility matching engine — SQL filtering on structured fields."""

from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Scheme, State, scheme_states
from app.schemas.eligibility import EligibilityCheckRequest
from app.schemas.scheme import SchemeListItem


async def check_eligibility(
    session: AsyncSession, profile: EligibilityCheckRequest
) -> list[dict]:
    """Match user profile against scheme eligibility criteria.

    Returns schemes sorted by match score (number of matching criteria / total criteria).
    """
    query = (
        select(Scheme)
        .options(selectinload(Scheme.category), selectinload(Scheme.tags))
        .where(Scheme.status == "active")
    )

    # If state is specified, filter to central schemes + schemes for that state
    if profile.state_code:
        state_subq = (
            select(scheme_states.c.scheme_id)
            .join(State, State.id == scheme_states.c.state_id)
            .where(State.code == profile.state_code)
        )
        query = query.where(
            or_(
                Scheme.level == "central",
                Scheme.id.in_(state_subq),
            )
        )

    result = await session.execute(query)
    schemes = result.unique().scalars().all()

    scored_results = []
    for scheme in schemes:
        score, matched = _compute_match(scheme, profile)
        if score > 0:
            scored_results.append({
                "scheme": SchemeListItem.model_validate(scheme),
                "match_score": score,
                "matched_criteria": matched,
            })

    # Sort by match score descending
    scored_results.sort(key=lambda x: x["match_score"], reverse=True)
    return scored_results


def _compute_match(scheme: Scheme, profile: EligibilityCheckRequest) -> tuple[float, list[str]]:
    """Compute match score between a scheme and user profile.

    Returns (score 0-1, list of matched criteria).
    """
    total_criteria = 0
    matched_criteria = []

    # Gender check
    if scheme.target_gender:
        total_criteria += 1
        if profile.gender and profile.gender.lower() in [g.lower() for g in scheme.target_gender]:
            matched_criteria.append(f"Gender: {profile.gender}")
        elif profile.gender and "all" in [g.lower() for g in scheme.target_gender]:
            matched_criteria.append("Gender: open to all")

    # Age check
    if scheme.min_age is not None or scheme.max_age is not None:
        total_criteria += 1
        if profile.age is not None:
            age_ok = True
            if scheme.min_age is not None and profile.age < scheme.min_age:
                age_ok = False
            if scheme.max_age is not None and profile.age > scheme.max_age:
                age_ok = False
            if age_ok:
                matched_criteria.append(f"Age: {profile.age} within range")

    # Social category
    if scheme.target_social_category:
        total_criteria += 1
        if profile.social_category:
            sc_upper = profile.social_category.upper()
            targets = [c.upper() for c in scheme.target_social_category]
            if sc_upper in targets or "ALL" in targets or "GENERAL" in targets:
                matched_criteria.append(f"Category: {profile.social_category}")

    # Income
    if scheme.target_income_max is not None:
        total_criteria += 1
        if profile.income is not None and profile.income <= scheme.target_income_max:
            matched_criteria.append(f"Income: within limit")

    # Disability
    if scheme.is_disability is True:
        total_criteria += 1
        if profile.is_disability is True:
            matched_criteria.append("Disability: eligible")

    # Student
    if scheme.is_student is True:
        total_criteria += 1
        if profile.is_student is True:
            matched_criteria.append("Student: eligible")

    # BPL
    if scheme.is_bpl is True:
        total_criteria += 1
        if profile.is_bpl is True:
            matched_criteria.append("BPL: eligible")

    # If scheme has no structured criteria, give a baseline score for universal schemes
    if total_criteria == 0:
        return 0.1, ["Open to all"]

    score = len(matched_criteria) / total_criteria if total_criteria > 0 else 0
    return score, matched_criteria


async def get_eligibility_options(session: AsyncSession) -> dict:
    """Get valid options for the eligibility wizard dropdowns."""
    states = (await session.execute(
        select(State).order_by(State.name)
    )).scalars().all()

    return {
        "genders": ["Male", "Female", "Transgender"],
        "social_categories": ["General", "SC", "ST", "OBC", "EWS"],
        "states": [
            {"code": s.code, "name": s.name, "is_ut": s.is_ut}
            for s in states
        ],
    }
