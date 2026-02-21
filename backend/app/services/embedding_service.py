"""Embedding generation and management."""

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Scheme, SchemeEmbedding
from app.services.mistral_service import embed_texts


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

        embeddings = await embed_texts([texts[j] for j, _, _, _ in to_embed])

        for (j, scheme, text_hash, existing), embedding in zip(to_embed, embeddings):
            if existing:
                existing.embedding = embedding
                existing.text_hash = text_hash
            else:
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

    return count
