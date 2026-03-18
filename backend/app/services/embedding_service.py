"""Embedding generation and management."""

import asyncio
import hashlib
import logging
import uuid

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Scheme, SchemeEmbedding
from app.services.mistral_service import embed_texts

logger = logging.getLogger(__name__)


def scheme_to_text(scheme: Scheme) -> str:
    """Convert scheme to text for embedding."""
    parts = [scheme.name]
    if scheme.description:
        parts.append(scheme.description)
    if scheme.benefits:
        parts.append(f"Benefits: {scheme.benefits}")
    if scheme.eligibility_criteria:
        parts.append(f"Eligibility: {scheme.eligibility_criteria}")
    return " ".join(parts)[:8000]  # Truncate to avoid token limits


async def generate_embeddings_batch(
    session: AsyncSession, schemes: list[Scheme], batch_size: int = 10
) -> int:
    """Generate embeddings for a batch of schemes."""
    count = 0
    for i in range(0, len(schemes), batch_size):
        batch = schemes[i : i + batch_size]
        texts = [scheme_to_text(s) for s in batch]
        hashes = [hashlib.sha256(t.encode()).hexdigest() for t in texts]

        # Check which need updating
        to_embed = []
        for j, scheme in enumerate(batch):
            existing = (
                await session.execute(
                    select(SchemeEmbedding).where(SchemeEmbedding.scheme_id == scheme.id)
                )
            ).scalar_one_or_none()
            if existing and existing.text_hash == hashes[j]:
                continue
            to_embed.append((j, scheme, hashes[j], existing))

        if not to_embed:
            continue

        # Retry with exponential backoff for rate limits
        embed_input = [texts[j] for j, _, _, _ in to_embed]
        embeddings = None
        for attempt in range(5):
            try:
                embeddings = await embed_texts(embed_input)
                break
            except Exception as e:
                if "429" in str(e) or "rate" in str(e).lower():
                    wait = 2 ** attempt * 5  # 5, 10, 20, 40, 80 seconds
                    logger.warning("Rate limited, waiting %ds (attempt %d/5)", wait, attempt + 1)
                    await asyncio.sleep(wait)
                else:
                    raise
        if embeddings is None:
            logger.error("Failed to embed batch after 5 retries, skipping")
            continue

        for (j, scheme, text_hash, existing), embedding in zip(to_embed, embeddings):
            if existing:
                existing.embedding = embedding
                existing.text_hash = text_hash
            else:
                # Delete any stale row from a previous partial run
                await session.execute(
                    delete(SchemeEmbedding).where(SchemeEmbedding.scheme_id == scheme.id)
                )
                session.add(
                    SchemeEmbedding(
                        id=uuid.uuid4(),
                        scheme_id=scheme.id,
                        embedding=embedding,
                        text_hash=text_hash,
                    )
                )
            count += 1

        await session.commit()
        if i + batch_size < len(schemes):
            await asyncio.sleep(1)  # Rate limit buffer between batches

    return count
