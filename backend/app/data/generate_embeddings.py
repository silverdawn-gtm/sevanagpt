"""Generate embeddings for all schemes."""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Scheme
from app.services.embedding_service import generate_embeddings_batch


async def main():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        schemes = (
            await session.execute(select(Scheme).where(Scheme.status == "active"))
        ).scalars().all()
        print(f"Found {len(schemes)} active schemes")

        count = await generate_embeddings_batch(session, schemes, batch_size=5)
        print(f"Generated/updated {count} embeddings")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
