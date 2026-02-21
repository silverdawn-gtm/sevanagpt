"""Ingest scheme data from data.gov.in open API.

Uses httpx to call the data.gov.in resource API, parses the JSON response,
normalises fields, deduplicates against existing schemes by slug,
and inserts new records with source='datagov'.
"""

import asyncio
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Category, Ministry, Scheme, Tag
from app.utils.slug import slugify


# data.gov.in resource IDs known to contain government scheme information
DATAGOV_RESOURCE_IDS = [
    "2a16e8a9-86df-4221-8a7e-eaborb62def1",  # placeholder -- replace with real IDs
]

DATAGOV_BASE_URL = "https://api.data.gov.in/resource"


def match_name(name: str, lookup: dict):
    """Fuzzy-match a name against a lookup dict (lowered keys)."""
    if not name:
        return None
    name_lower = name.lower().strip()
    for key, obj in lookup.items():
        if key in name_lower or name_lower in key:
            return obj
    return None


def normalize_record(record: dict) -> dict | None:
    """Map a data.gov.in JSON record to Scheme-compatible field dict.

    The exact field names depend on the resource; we try common patterns.
    """

    def _str(val) -> str | None:
        if val is None:
            return None
        s = str(val).strip()
        return s if s else None

    name = (
        _str(record.get("scheme_name"))
        or _str(record.get("name_of_the_scheme"))
        or _str(record.get("scheme"))
        or _str(record.get("name"))
        or _str(record.get("title"))
        or _str(record.get("schemename"))
    )
    if not name:
        return None

    return {
        "name": name,
        "description": (
            _str(record.get("description"))
            or _str(record.get("objective"))
            or _str(record.get("details"))
            or _str(record.get("scheme_description"))
        ),
        "benefits": (
            _str(record.get("benefits"))
            or _str(record.get("benefit"))
        ),
        "eligibility_criteria": (
            _str(record.get("eligibility"))
            or _str(record.get("eligibility_criteria"))
        ),
        "application_process": _str(record.get("application_process")),
        "documents_required": _str(record.get("documents_required")),
        "official_link": (
            _str(record.get("url"))
            or _str(record.get("link"))
            or _str(record.get("website"))
        ),
        "category": (
            _str(record.get("category"))
            or _str(record.get("sector"))
        ),
        "ministry": (
            _str(record.get("ministry"))
            or _str(record.get("department"))
            or _str(record.get("ministry_department"))
        ),
        "level": "central",
    }


async def fetch_resource(
    client: httpx.AsyncClient,
    resource_id: str,
    api_key: str,
    offset: int = 0,
    limit: int = 100,
) -> list[dict]:
    """Fetch a page of records from a data.gov.in resource."""
    params = {
        "api-key": api_key,
        "format": "json",
        "offset": offset,
        "limit": limit,
    }
    url = f"{DATAGOV_BASE_URL}/{resource_id}"
    try:
        resp = await client.get(url, params=params, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        records = data.get("records", [])
        return records
    except Exception as e:
        print(f"  Error fetching resource {resource_id} (offset={offset}): {e}")
        return []


async def fetch_all_records(
    client: httpx.AsyncClient,
    resource_id: str,
    api_key: str,
    max_records: int = 500,
) -> list[dict]:
    """Paginate through a data.gov.in resource, collecting up to max_records."""
    all_records: list[dict] = []
    offset = 0
    page_size = 100

    while offset < max_records:
        records = await fetch_resource(client, resource_id, api_key, offset=offset, limit=page_size)
        if not records:
            break
        all_records.extend(records)
        if len(records) < page_size:
            break
        offset += page_size

    return all_records


async def ingest():
    """Main ingestion entry point for data.gov.in schemes."""
    if not settings.DATAGOV_API_KEY:
        print("DATAGOV_API_KEY not set -- skipping data.gov.in ingestion")
        return

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Load lookups
        categories = {
            c.name.lower(): c
            for c in (await session.execute(select(Category))).scalars().all()
        }
        ministries = {
            m.name.lower(): m
            for m in (await session.execute(select(Ministry))).scalars().all()
        }

        # Collect existing slugs for deduplication
        existing_slugs = set(
            (await session.execute(select(Scheme.slug))).scalars().all()
        )

        added = 0
        skipped = 0

        async with httpx.AsyncClient() as client:
            for resource_id in DATAGOV_RESOURCE_IDS:
                print(f"Fetching data.gov.in resource: {resource_id}")
                records = await fetch_all_records(
                    client, resource_id, settings.DATAGOV_API_KEY
                )
                print(f"  Got {len(records)} records")

                for record in records:
                    data = normalize_record(record)
                    if not data:
                        skipped += 1
                        continue

                    slug = slugify(data["name"])
                    if slug in existing_slugs:
                        skipped += 1
                        continue

                    cat = match_name(data.get("category", ""), categories)
                    ministry = match_name(data.get("ministry", ""), ministries)

                    scheme = Scheme(
                        id=uuid.uuid4(),
                        name=data["name"],
                        slug=slug,
                        description=data.get("description"),
                        benefits=data.get("benefits"),
                        eligibility_criteria=data.get("eligibility_criteria"),
                        application_process=data.get("application_process"),
                        documents_required=data.get("documents_required"),
                        official_link=data.get("official_link"),
                        category_id=cat.id if cat else None,
                        ministry_id=ministry.id if ministry else None,
                        level=data.get("level", "central"),
                        status="active",
                        source="datagov",
                    )
                    session.add(scheme)
                    existing_slugs.add(slug)
                    added += 1

        await session.commit()
        print(f"data.gov.in ingestion: added {added} schemes, skipped {skipped} duplicates/empty")

    await engine.dispose()
    print("data.gov.in ingestion complete!")


if __name__ == "__main__":
    asyncio.run(ingest())
