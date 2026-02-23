"""Shared test fixtures for SevanaGPT backend tests."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import StaticPool, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import Category, Scheme, State, Tag

# ---------------------------------------------------------------------------
# In-memory SQLite async engine (no real Postgres needed for unit tests)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # pgvector Vector column doesn't exist in SQLite — register a fake type
    @event.listens_for(eng.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with eng.begin() as conn:
        # Create all tables (skip Vector columns gracefully)
        await conn.run_sync(Base.metadata.create_all)

    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(engine):
    """Async HTTP test client wired to the FastAPI app with test DB."""
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def sample_category(db_session):
    cat = Category(
        id=uuid.uuid4(),
        name="Education",
        slug="education",
        icon="book",
        display_order=1,
    )
    db_session.add(cat)
    await db_session.flush()
    return cat


@pytest_asyncio.fixture
async def sample_state(db_session):
    state = State(
        id=uuid.uuid4(),
        name="Karnataka",
        slug="karnataka",
        code="KA",
        is_ut=False,
    )
    db_session.add(state)
    await db_session.flush()
    return state


@pytest_asyncio.fixture
async def sample_tag(db_session):
    tag = Tag(
        id=uuid.uuid4(),
        name="Scholarship",
        slug="scholarship",
    )
    db_session.add(tag)
    await db_session.flush()
    return tag


@pytest_asyncio.fixture
async def sample_schemes(db_session, sample_category, sample_state, sample_tag):
    """Create a set of test schemes with varied eligibility criteria."""
    schemes = []

    s1 = Scheme(
        id=uuid.uuid4(),
        name="National Scholarship for Students",
        slug="national-scholarship-students",
        description="Scholarship for students from economically weaker sections",
        benefits="Up to Rs 50,000 per year",
        eligibility_criteria="Student from EWS with family income below 2.5 lakh",
        level="central",
        status="active",
        featured=True,
        target_gender=["All"],
        min_age=16,
        max_age=30,
        target_social_category=["SC", "ST", "OBC", "General"],
        target_income_max=250000,
        is_student=True,
        is_bpl=False,
        is_disability=False,
        category_id=sample_category.id,
    )
    s1.tags.append(sample_tag)
    s1.states.append(sample_state)

    s2 = Scheme(
        id=uuid.uuid4(),
        name="Women Empowerment Programme",
        slug="women-empowerment-programme",
        description="Financial support for women entrepreneurs",
        benefits="Loan subsidy up to Rs 5 lakh",
        eligibility_criteria="Women aged 18-60 from any state",
        level="central",
        status="active",
        featured=False,
        target_gender=["Female"],
        min_age=18,
        max_age=60,
        target_social_category=["All"],
        is_student=False,
    )

    s3 = Scheme(
        id=uuid.uuid4(),
        name="Disability Support Scheme",
        slug="disability-support-scheme",
        description="Monthly pension for disabled persons",
        benefits="Rs 2000 per month",
        eligibility_criteria="Persons with 40% or more disability",
        level="central",
        status="active",
        is_disability=True,
        target_gender=["All"],
    )

    s4 = Scheme(
        id=uuid.uuid4(),
        name="BPL Housing Scheme",
        slug="bpl-housing-scheme",
        description="Housing for Below Poverty Line families",
        benefits="Free housing unit",
        level="state",
        status="active",
        is_bpl=True,
        target_income_max=100000,
    )
    s4.states.append(sample_state)

    s5 = Scheme(
        id=uuid.uuid4(),
        name="Inactive Old Scheme",
        slug="inactive-old-scheme",
        description="This scheme has been discontinued",
        level="central",
        status="inactive",
    )

    for s in [s1, s2, s3, s4, s5]:
        db_session.add(s)
        schemes.append(s)

    await db_session.flush()
    return schemes


# ---------------------------------------------------------------------------
# Mock fixtures for external services
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_indictrans():
    """Patch IndicTrans2 client to return predictable translations."""
    with patch("app.services.indictrans_client._get_client") as mock:
        mock.return_value = None  # Disabled — forces Google Translate fallback
        yield mock


@pytest.fixture
def mock_google_translate():
    """Patch Google Translate to avoid real API calls."""
    with patch("app.services.translate_service._google_translate_sync") as single, \
         patch("app.services.translate_service._google_translate_batch_sync") as batch:
        single.side_effect = lambda text, lang: f"[{lang}]{text}"
        batch.side_effect = lambda texts, lang: [f"[{lang}]{t}" for t in texts]
        yield single, batch


@pytest.fixture
def mock_llm():
    """Patch LLM calls (Mistral/Groq) to avoid real API calls."""
    with patch("app.services.mistral_service.chat_complete", new_callable=AsyncMock) as chat, \
         patch("app.services.mistral_service.classify_intent", new_callable=AsyncMock) as classify, \
         patch("app.services.mistral_service.embed_single", new_callable=AsyncMock) as embed:
        chat.return_value = "Test response from LLM"
        classify.return_value = {"intent": "search_scheme", "entities": {}}
        embed.return_value = [0.0] * 1024
        yield chat, classify, embed
