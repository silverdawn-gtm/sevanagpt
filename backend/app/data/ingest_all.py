"""Unified ingestion runner.

Orchestrates: seed -> ingest_hf -> ingest_kaggle -> ingest_datagov -> generate_embeddings.
Each step is wrapped so that a failure in one source does not prevent others from running.
Reports the total scheme count at the end.
"""

import asyncio
import traceback

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Scheme


async def run_step(name: str, coro_func):
    """Run a single ingestion step, catching and logging any errors."""
    print(f"\n{'=' * 60}")
    print(f"STEP: {name}")
    print(f"{'=' * 60}")
    try:
        await coro_func()
        print(f"[OK] {name} completed successfully")
    except Exception as e:
        print(f"[ERROR] {name} failed: {e}")
        traceback.print_exc()


async def get_total_scheme_count() -> int:
    """Query the database for the total number of schemes."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        result = await session.execute(select(func.count(Scheme.id)))
        count = result.scalar() or 0
    await engine.dispose()
    return count


async def ingest_all():
    """Run all ingestion steps in order."""
    from app.data.seed import seed_all
    from app.data.ingest_hf import ingest as ingest_hf
    from app.data.ingest_state_schemes import ingest as ingest_state_schemes
    from app.data.ingest_myscheme import ingest as ingest_myscheme
    from app.data.ingest_kaggle import ingest as ingest_kaggle
    from app.data.ingest_datagov import ingest as ingest_datagov
    from app.data.generate_embeddings import main as generate_embeddings

    # Step 1: Seed reference data (categories, states, ministries, tags)
    await run_step("Seed reference data", seed_all)

    # Step 2: Ingest from embedded/HuggingFace dataset (central schemes)
    await run_step("Ingest HuggingFace / embedded schemes", ingest_hf)

    # Step 3: Ingest state-specific schemes
    await run_step("Ingest state-specific schemes", ingest_state_schemes)

    # Step 4: Ingest from MyScheme.gov.in (official government API)
    await run_step("Ingest MyScheme.gov.in", ingest_myscheme)

    # Step 5: Ingest from Kaggle
    await run_step("Ingest Kaggle dataset", ingest_kaggle)

    # Step 6: Ingest from data.gov.in
    await run_step("Ingest data.gov.in", ingest_datagov)

    # Step 7: Generate embeddings for all schemes
    await run_step("Generate embeddings", generate_embeddings)

    # Report totals
    total = await get_total_scheme_count()
    print(f"\n{'=' * 60}")
    print(f"ALL INGESTION COMPLETE -- Total schemes in database: {total}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(ingest_all())
