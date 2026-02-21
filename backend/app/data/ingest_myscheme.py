"""Ingest schemes from the official MyScheme.gov.in search API.

Fetches all ~4,600 schemes via the public search API in batches of 50,
maps categories/states/ministries/tags to our DB, and inserts with source='myscheme'.
"""

import asyncio
import time
import uuid

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import (
    Category,
    Ministry,
    Scheme,
    SchemeEmbedding,
    SchemeFAQ,
    State,
    Tag,
    scheme_states,
    scheme_tags,
)
from app.utils.slug import slugify

API_BASE = "https://api.myscheme.gov.in/search/v6"
API_KEY = "tYTy5eEhlu9rFjyxuCr7ra7ACp4dv1RH8gWuHTDc"
HEADERS = {
    "x-api-key": API_KEY,
    "Origin": "https://www.myscheme.gov.in",
    "Referer": "https://www.myscheme.gov.in/",
    "User-Agent": "Mozilla/5.0 (compatible; SevanaGPT/1.0)",
}
BATCH_SIZE = 50

# Map MyScheme category names (lowered, normalized) to our seed category names
CATEGORY_MAP = {
    "social welfare & empowerment": "Social Welfare & Empowerment",
    "education & learning": "Education & Learning",
    "agriculture,rural & environment": "Agriculture, Rural & Environment",
    "agriculture, rural & environment": "Agriculture, Rural & Environment",
    "business & entrepreneurship": "Business & Entrepreneurship",
    "skills & employment": "Skills & Employment",
    "banking,financial services and insurance": "Banking, Financial Services and Insurance",
    "banking, financial services and insurance": "Banking, Financial Services and Insurance",
    "health & wellness": "Health & Wellness",
    "housing & shelter": "Housing & Shelter",
    "science, it & communications": "Science, IT & Communications",
    "science,it & communications": "Science, IT & Communications",
    "sports & culture": "Sports & Culture",
    "transport & infrastructure": "Transport & Infrastructure",
    "travel & tourism": "Travel & Tourism",
    "utility & sanitation": "Utility & Sanitation",
    "women and child": "Women and Child",
    "public safety, law & justice": "Public Safety, Law & Justice",
    "public safety,law & justice": "Public Safety, Law & Justice",
}

# Map some MyScheme state names that differ from our seed
STATE_NAME_MAP = {
    "dadra & nagar haveli and daman & diu": "Dadra and Nagar Haveli and Daman and Diu",
    "andaman & nicobar islands": "Andaman and Nicobar Islands",
}


def normalize_cat(name: str) -> str:
    """Normalize a MyScheme category name to match our DB."""
    low = name.lower().strip()
    mapped = CATEGORY_MAP.get(low)
    if mapped:
        return mapped
    # Try fuzzy: strip commas and compare
    stripped = low.replace(",", " ").replace("  ", " ")
    for key, val in CATEGORY_MAP.items():
        if stripped == key.replace(",", " ").replace("  ", " "):
            return val
    return name  # return as-is if no match


def normalize_state_name(name: str) -> str:
    """Normalize a MyScheme state name to match our DB."""
    low = name.lower().strip()
    return STATE_NAME_MAP.get(low, name)


async def fetch_all_schemes() -> list[dict]:
    """Fetch all schemes from the MyScheme search API."""
    all_items = []
    offset = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        # First request to get the total count
        resp = await client.get(
            f"{API_BASE}/schemes",
            params={"lang": "en", "q": "", "keyword": "", "sort": "", "from": 0, "size": BATCH_SIZE},
            headers=HEADERS,
        )
        resp.raise_for_status()
        data = resp.json()
        total = data["data"]["summary"]["total"]
        items = data["data"]["hits"].get("items", [])
        all_items.extend(items)
        offset += BATCH_SIZE
        print(f"Total schemes available: {total}")
        print(f"Fetched batch 1: {len(items)} items (total so far: {len(all_items)})")

        # Fetch remaining batches
        batch_num = 2
        while offset < total:
            await asyncio.sleep(0.3)  # Be respectful to the API
            try:
                resp = await client.get(
                    f"{API_BASE}/schemes",
                    params={"lang": "en", "q": "", "keyword": "", "sort": "", "from": offset, "size": BATCH_SIZE},
                    headers=HEADERS,
                )
                resp.raise_for_status()
                data = resp.json()
                items = data["data"]["hits"].get("items", [])
                if not items:
                    print(f"Batch {batch_num}: no more items at offset {offset}, stopping")
                    break
                all_items.extend(items)
                print(f"Fetched batch {batch_num}: {len(items)} items (total so far: {len(all_items)})")
            except Exception as e:
                print(f"Error at offset {offset}: {e}, retrying in 2s...")
                await asyncio.sleep(2)
                try:
                    resp = await client.get(
                        f"{API_BASE}/schemes",
                        params={"lang": "en", "q": "", "keyword": "", "sort": "", "from": offset, "size": BATCH_SIZE},
                        headers=HEADERS,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    items = data["data"]["hits"].get("items", [])
                    all_items.extend(items)
                    print(f"Retry batch {batch_num}: {len(items)} items")
                except Exception as e2:
                    print(f"Retry also failed at offset {offset}: {e2}, skipping batch")

            offset += BATCH_SIZE
            batch_num += 1

    print(f"\nFetch complete: {len(all_items)} total schemes fetched")
    return all_items


async def clear_old_data(session: AsyncSession):
    """Remove all existing non-manual schemes and their relations."""
    # Get IDs of schemes to delete
    old_ids = (
        await session.execute(
            select(Scheme.id).where(Scheme.source.in_(["kaggle", "myscheme", "huggingface"]))
        )
    ).scalars().all()

    if not old_ids:
        print("No old ingested schemes to clear")
        return

    print(f"Clearing {len(old_ids)} old ingested schemes...")

    # Delete related data first
    await session.execute(
        delete(scheme_states).where(scheme_states.c.scheme_id.in_(old_ids))
    )
    await session.execute(
        delete(scheme_tags).where(scheme_tags.c.scheme_id.in_(old_ids))
    )
    await session.execute(
        delete(SchemeFAQ).where(SchemeFAQ.scheme_id.in_(old_ids))
    )
    await session.execute(
        delete(SchemeEmbedding).where(SchemeEmbedding.scheme_id.in_(old_ids))
    )
    await session.execute(
        delete(Scheme).where(Scheme.id.in_(old_ids))
    )
    await session.flush()
    print(f"Cleared {len(old_ids)} old schemes and their relations")


async def ingest():
    """Main ingestion entry point for MyScheme API data."""
    print("=" * 60)
    print("MyScheme.gov.in Data Ingestion")
    print("=" * 60)

    # Step 1: Fetch all schemes from API
    print("\nStep 1: Fetching schemes from MyScheme API...")
    start = time.time()
    raw_schemes = await fetch_all_schemes()
    print(f"Fetched in {time.time() - start:.1f}s")

    if not raw_schemes:
        print("No schemes fetched, aborting!")
        return

    # Step 2: Connect to DB and prepare lookups
    print("\nStep 2: Preparing database...")
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Clear old data
        await clear_old_data(session)
        await session.commit()

        # Load lookups
        categories = {
            c.name.lower(): c
            for c in (await session.execute(select(Category))).scalars().all()
        }
        states_lookup = {
            s.name.lower(): s
            for s in (await session.execute(select(State))).scalars().all()
        }
        all_ministries = (await session.execute(select(Ministry))).scalars().all()
        ministries_lookup = {m.name.lower(): m for m in all_ministries}
        ministries_slug_set = {m.slug for m in all_ministries}
        all_tags = (await session.execute(select(Tag))).scalars().all()
        tags_lookup = {t.name.lower(): t for t in all_tags}
        tags_slug_set = {t.slug for t in all_tags}  # track slugs to avoid duplicates
        existing_slugs = set(
            (await session.execute(select(Scheme.slug))).scalars().all()
        )

        print(f"Loaded {len(categories)} categories, {len(states_lookup)} states, "
              f"{len(ministries_lookup)} ministries, {len(tags_lookup)} tags")
        print(f"Existing scheme slugs: {len(existing_slugs)}")

        # Step 3: Process and insert schemes
        print("\nStep 3: Processing and inserting schemes...")
        added = 0
        skipped = 0
        new_ministries = 0
        new_tags = 0
        pending_relations = []  # (scheme_id, state_ids, tag_ids)

        for item in raw_schemes:
            fields = item.get("fields", {})
            name = fields.get("schemeName", "").strip()
            if not name:
                skipped += 1
                continue

            slug = fields.get("slug", "") or slugify(name)
            if slug in existing_slugs:
                skipped += 1
                continue

            # Map category (take the first one)
            cat_names = fields.get("schemeCategory", [])
            category_obj = None
            for cat_name in cat_names:
                normalized = normalize_cat(cat_name)
                category_obj = categories.get(normalized.lower())
                if category_obj:
                    break

            # Map ministry (create if new)
            ministry_name = fields.get("nodalMinistryName", "")
            ministry_obj = None
            if ministry_name:
                ministry_obj = ministries_lookup.get(ministry_name.lower().strip())
                if not ministry_obj:
                    m_slug = slugify(ministry_name)
                    if m_slug and m_slug not in ministries_slug_set:
                        ministry_obj = Ministry(
                            id=uuid.uuid4(),
                            name=ministry_name.strip(),
                            slug=m_slug,
                            level="central",
                        )
                        session.add(ministry_obj)
                        ministries_lookup[ministry_name.lower().strip()] = ministry_obj
                        ministries_slug_set.add(m_slug)
                        new_ministries += 1

            # Determine level
            level_raw = (fields.get("level", "") or "central").strip().lower()
            level = "central" if level_raw == "central" else "state"

            # Create scheme
            scheme = Scheme(
                id=uuid.uuid4(),
                name=name,
                slug=slug,
                description=fields.get("briefDescription", ""),
                official_link=f"https://www.myscheme.gov.in/schemes/{slug}",
                category_id=category_obj.id if category_obj else None,
                ministry_id=ministry_obj.id if ministry_obj else None,
                level=level,
                status="active",
                source="myscheme",
            )
            session.add(scheme)
            existing_slugs.add(slug)

            # Collect state and tag IDs for batch insert after flush
            state_ids = set()
            state_names = fields.get("beneficiaryState", [])
            for state_name in state_names:
                if state_name == "All":
                    continue
                normalized_name = normalize_state_name(state_name)
                state_obj = states_lookup.get(normalized_name.lower().strip())
                if state_obj:
                    state_ids.add(state_obj.id)

            tag_ids = set()
            tag_names = fields.get("tags", [])
            for tag_name in tag_names:
                tag_name_clean = tag_name.strip()
                if not tag_name_clean:
                    continue
                tag_obj = tags_lookup.get(tag_name_clean.lower())
                if not tag_obj:
                    tag_slug = slugify(tag_name_clean)
                    if not tag_slug or tag_slug in tags_slug_set:
                        # Skip tags with empty or duplicate slugs
                        continue
                    tag_obj = Tag(
                        id=uuid.uuid4(),
                        name=tag_name_clean,
                        slug=tag_slug,
                    )
                    session.add(tag_obj)
                    tags_lookup[tag_name_clean.lower()] = tag_obj
                    tags_slug_set.add(tag_slug)
                    new_tags += 1
                tag_ids.add(tag_obj.id)

            # Store pending relations
            pending_relations.append((scheme.id, state_ids, tag_ids))
            added += 1

            if added % 500 == 0:
                # Flush schemes and tags, then insert junction rows
                await session.flush()
                for s_id, s_states, s_tags in pending_relations:
                    for st_id in s_states:
                        await session.execute(
                            scheme_states.insert().values(scheme_id=s_id, state_id=st_id)
                        )
                    for t_id in s_tags:
                        await session.execute(
                            scheme_tags.insert().values(scheme_id=s_id, tag_id=t_id)
                        )
                pending_relations.clear()
                await session.flush()
                print(f"  ... processed {added} schemes")

        # Flush remaining schemes and insert their relations
        if pending_relations:
            await session.flush()
            for s_id, s_states, s_tags in pending_relations:
                for st_id in s_states:
                    await session.execute(
                        scheme_states.insert().values(scheme_id=s_id, state_id=st_id)
                    )
                for t_id in s_tags:
                    await session.execute(
                        scheme_tags.insert().values(scheme_id=s_id, tag_id=t_id)
                    )
            pending_relations.clear()

        await session.commit()
        print(f"\n{'=' * 60}")
        print(f"Ingestion complete!")
        print(f"  Added: {added} schemes")
        print(f"  Skipped: {skipped} (empty/duplicate)")
        print(f"  New ministries created: {new_ministries}")
        print(f"  New tags created: {new_tags}")

        # Print category distribution
        from sqlalchemy import func as sqlfunc
        cat_counts = (
            await session.execute(
                select(Category.name, sqlfunc.count(Scheme.id))
                .join(Scheme, Scheme.category_id == Category.id)
                .group_by(Category.name)
                .order_by(sqlfunc.count(Scheme.id).desc())
            )
        ).all()
        print(f"\nCategory distribution:")
        for cat_name, count in cat_counts:
            print(f"  {cat_name}: {count}")

        # Count schemes with states
        state_scheme_count = (
            await session.execute(
                select(sqlfunc.count(sqlfunc.distinct(scheme_states.c.scheme_id)))
            )
        ).scalar()
        print(f"\nSchemes with state mapping: {state_scheme_count}")

        total = (await session.execute(select(sqlfunc.count(Scheme.id)))).scalar()
        print(f"Total schemes in DB: {total}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(ingest())
