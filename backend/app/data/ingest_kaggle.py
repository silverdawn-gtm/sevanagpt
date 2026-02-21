"""Ingest schemes from the Kaggle dataset: jainamgada45/indian-government-schemes.

Downloads the dataset via the Kaggle API, reads the CSV with pandas,
maps columns to the Scheme model, fuzzy-matches categories/ministries,
deduplicates by slug, and sets source='kaggle'.
"""

import asyncio
import os
import tempfile
import uuid

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Category, Ministry, Scheme, Tag, scheme_tags
from app.utils.slug import slugify


def match_name(name: str, lookup: dict):
    """Fuzzy-match a name against a lookup dict (lowered keys).

    Returns the first value whose key is a substring of *name* or vice-versa,
    falling back to None.
    """
    if not name:
        return None
    name_lower = name.lower().strip()
    for key, obj in lookup.items():
        if key in name_lower or name_lower in key:
            return obj
    return None


def download_dataset() -> str:
    """Download the Kaggle dataset and return the path to the CSV file."""
    # Configure Kaggle credentials from settings
    os.environ.setdefault("KAGGLE_USERNAME", settings.KAGGLE_USERNAME)
    os.environ.setdefault("KAGGLE_KEY", settings.KAGGLE_KEY)

    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()

    tmpdir = tempfile.mkdtemp(prefix="kaggle_schemes_")
    api.dataset_download_files(
        "jainamgada45/indian-government-schemes",
        path=tmpdir,
        unzip=True,
    )

    # Find the CSV file in the downloaded directory
    csv_files = [f for f in os.listdir(tmpdir) if f.endswith(".csv")]
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in downloaded dataset at {tmpdir}")

    return os.path.join(tmpdir, csv_files[0])


def normalize_row(row: pd.Series) -> dict:
    """Map a raw CSV row to Scheme-compatible field dict.

    The Kaggle dataset columns may vary; we handle the most common column
    names seen in jainamgada45/indian-government-schemes.
    """

    def _str(val) -> str | None:
        if pd.isna(val):
            return None
        return str(val).strip() or None

    # Try various column name conventions
    name = (
        _str(row.get("Scheme Name"))
        or _str(row.get("scheme_name"))
        or _str(row.get("name"))
        or _str(row.get("Name"))
        or _str(row.get("Title"))
        or _str(row.get("title"))
    )

    if not name:
        return {}

    return {
        "name": name,
        "description": (
            _str(row.get("Description"))
            or _str(row.get("description"))
            or _str(row.get("Details"))
            or _str(row.get("details"))
        ),
        "benefits": (
            _str(row.get("Benefits"))
            or _str(row.get("benefits"))
            or _str(row.get("Benefit"))
        ),
        "eligibility_criteria": (
            _str(row.get("Eligibility"))
            or _str(row.get("eligibility"))
            or _str(row.get("Eligibility Criteria"))
        ),
        "application_process": (
            _str(row.get("Application Process"))
            or _str(row.get("application_process"))
            or _str(row.get("How to Apply"))
        ),
        "documents_required": (
            _str(row.get("Documents Required"))
            or _str(row.get("documents_required"))
            or _str(row.get("Documents"))
        ),
        "official_link": (
            _str(row.get("Official Link"))
            or _str(row.get("URL"))
            or _str(row.get("url"))
            or _str(row.get("Link"))
        ),
        "category": (
            _str(row.get("Category"))
            or _str(row.get("category"))
            or _str(row.get("Sector"))
        ),
        "ministry": (
            _str(row.get("Ministry"))
            or _str(row.get("ministry"))
            or _str(row.get("Department"))
        ),
        "level": "central",
    }


async def ingest():
    """Main ingestion entry point for the Kaggle dataset."""
    if not settings.KAGGLE_USERNAME or not settings.KAGGLE_KEY:
        print("KAGGLE_USERNAME / KAGGLE_KEY not set -- skipping Kaggle ingestion")
        return

    print("Downloading Kaggle dataset...")
    try:
        csv_path = download_dataset()
    except Exception as e:
        print(f"Failed to download Kaggle dataset: {e}")
        return

    print(f"Reading CSV from {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows from Kaggle CSV")

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
        tags_lookup = {
            t.name.lower(): t
            for t in (await session.execute(select(Tag))).scalars().all()
        }

        # Collect existing slugs for deduplication
        existing_slugs = set(
            (await session.execute(select(Scheme.slug))).scalars().all()
        )

        added = 0
        skipped = 0

        for _, row in df.iterrows():
            data = normalize_row(row)
            if not data or not data.get("name"):
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
                source="kaggle",
            )
            session.add(scheme)
            existing_slugs.add(slug)
            added += 1

        await session.commit()
        print(f"Kaggle ingestion: added {added} schemes, skipped {skipped} duplicates/empty rows")

    await engine.dispose()
    print("Kaggle ingestion complete!")


if __name__ == "__main__":
    asyncio.run(ingest())
