"""Hybrid search: keyword (full-text) + semantic (pgvector) + RRF merge."""

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Category, Ministry, Scheme, SchemeEmbedding, State, scheme_states
from app.models.scheme import SchemeTranslation
from app.services.mistral_service import embed_single


async def keyword_search(
    session: AsyncSession, query: str, limit: int = 20
) -> list[tuple[Scheme, float]]:
    """Full-text search using ILIKE with term splitting for better recall."""
    from sqlalchemy import or_

    # Split query into terms and search for each
    terms = [t.strip() for t in query.split() if len(t.strip()) >= 3]
    if not terms:
        terms = [query]

    conditions = []
    for term in terms:
        pattern = f"%{term}%"
        conditions.append(Scheme.name.ilike(pattern))
        conditions.append(Scheme.description.ilike(pattern))
        conditions.append(Scheme.benefits.ilike(pattern))
        conditions.append(Scheme.eligibility_criteria.ilike(pattern))

    q = (
        select(Scheme)
        .options(selectinload(Scheme.category), selectinload(Scheme.tags))
        .where(Scheme.status == "active", or_(*conditions))
        .limit(limit)
    )
    results = (await session.execute(q)).unique().scalars().all()

    # Score by number of matching terms
    scored = []
    for scheme in results:
        text_blob = f"{scheme.name} {scheme.description or ''} {scheme.benefits or ''} {scheme.eligibility_criteria or ''}".lower()
        score = sum(1 for term in terms if term.lower() in text_blob) / len(terms)
        scored.append((scheme, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


async def keyword_search_translated(
    session: AsyncSession, query: str, lang: str, limit: int = 20
) -> list[tuple[Scheme, float]]:
    """Search scheme_translations table for non-English keyword matches."""
    from sqlalchemy import or_

    terms = [t.strip() for t in query.split() if len(t.strip()) >= 2]
    if not terms:
        terms = [query]

    conditions = []
    for term in terms:
        pattern = f"%{term}%"
        conditions.append(SchemeTranslation.name.ilike(pattern))
        conditions.append(SchemeTranslation.description.ilike(pattern))

    q = (
        select(Scheme)
        .join(SchemeTranslation, SchemeTranslation.scheme_id == Scheme.id)
        .options(selectinload(Scheme.category), selectinload(Scheme.tags))
        .where(
            Scheme.status == "active",
            SchemeTranslation.lang == lang,
            or_(*conditions),
        )
        .limit(limit)
    )
    results = (await session.execute(q)).unique().scalars().all()

    # Fetch translations for scoring
    scheme_ids = [s.id for s in results]
    if scheme_ids:
        trans_q = select(SchemeTranslation).where(
            SchemeTranslation.scheme_id.in_(scheme_ids),
            SchemeTranslation.lang == lang,
        )
        trans_rows = (await session.execute(trans_q)).scalars().all()
        trans_map = {t.scheme_id: t for t in trans_rows}
    else:
        trans_map = {}

    scored = []
    for scheme in results:
        t = trans_map.get(scheme.id)
        text_blob = ""
        if t:
            text_blob = f"{t.name or ''} {t.description or ''}".lower()
        score = sum(1 for term in terms if term.lower() in text_blob) / len(terms) if text_blob else 0.5
        scored.append((scheme, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


async def semantic_search(
    session: AsyncSession, query: str, limit: int = 20
) -> list[tuple[Scheme, float]]:
    """Vector similarity search using pgvector cosine distance."""
    query_embedding = await embed_single(query)

    q = (
        select(
            Scheme,
            SchemeEmbedding.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .join(SchemeEmbedding, SchemeEmbedding.scheme_id == Scheme.id)
        .options(selectinload(Scheme.category), selectinload(Scheme.tags))
        .where(Scheme.status == "active")
        .order_by("distance")
        .limit(limit)
    )
    results = (await session.execute(q)).unique().all()
    return [(scheme, 1.0 - distance) for scheme, distance in results]


def reciprocal_rank_fusion(
    *result_lists: list[tuple[Scheme, float]], k: int = 60
) -> list[tuple[Scheme, float]]:
    """Merge multiple ranked lists using Reciprocal Rank Fusion."""
    scores: dict[str, float] = {}
    scheme_map: dict[str, Scheme] = {}

    for result_list in result_lists:
        for rank, (scheme, _) in enumerate(result_list):
            sid = str(scheme.id)
            scores[sid] = scores.get(sid, 0) + 1.0 / (k + rank + 1)
            scheme_map[sid] = scheme

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [(scheme_map[sid], scores[sid]) for sid in sorted_ids]


async def hybrid_search(
    session: AsyncSession,
    query: str,
    category_slug: str | None = None,
    state_slug: str | None = None,
    ministry_slug: str | None = None,
    level: str | None = None,
    limit: int = 10,
    use_semantic: bool = True,
) -> list[tuple[Scheme, float]]:
    """Combined keyword + semantic search with optional filters."""
    # Get keyword results
    keyword_results = await keyword_search(session, query, limit=20)

    # Get semantic results (if API key is configured)
    semantic_results = []
    if use_semantic:
        try:
            semantic_results = await semantic_search(session, query, limit=20)
        except Exception:
            pass  # Fall back to keyword-only if embeddings not available

    # Merge with RRF
    if semantic_results:
        merged = reciprocal_rank_fusion(keyword_results, semantic_results)
    else:
        merged = keyword_results

    # Apply post-filters
    filtered = []
    for scheme, score in merged:
        if category_slug and (not scheme.category or scheme.category.slug != category_slug):
            continue
        if level and scheme.level != level:
            continue
        filtered.append((scheme, score))

    # State and ministry filters require additional queries
    if state_slug:
        state = (
            await session.execute(select(State).where(State.slug == state_slug))
        ).scalar_one_or_none()
        if state:
            state_scheme_ids = set()
            rows = await session.execute(
                select(scheme_states.c.scheme_id).where(
                    scheme_states.c.state_id == state.id
                )
            )
            state_scheme_ids = {row[0] for row in rows.all()}
            filtered = [(s, sc) for s, sc in filtered if s.id in state_scheme_ids]

    if ministry_slug:
        ministry = (
            await session.execute(select(Ministry).where(Ministry.slug == ministry_slug))
        ).scalar_one_or_none()
        if ministry:
            filtered = [
                (s, sc) for s, sc in filtered if s.ministry_id == ministry.id
            ]

    return filtered[:limit]
