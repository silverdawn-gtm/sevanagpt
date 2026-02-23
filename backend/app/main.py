import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware.timing import TimingMiddleware, metrics_endpoint

logger = logging.getLogger(__name__)


async def _background_pre_translate():
    """Pre-translate Hindi scheme names in background on startup."""
    await asyncio.sleep(5)  # Let server finish starting
    try:
        from app.data.pre_translate import pre_translate_language
        await pre_translate_language("hi")
    except Exception as e:
        logger.info("Background pre-translation skipped: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — kick off background pre-translation for Hindi
    task = asyncio.create_task(_background_pre_translate())
    yield
    # Shutdown
    task.cancel()


app = FastAPI(
    title="SevanaGPT API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TimingMiddleware)


@app.get("/health")
async def health():
    return {"status": "ok"}


app.add_route("/metrics", metrics_endpoint, methods=["GET"])


# Import and register routers
from app.api.v1.schemes import router as schemes_router
from app.api.v1.categories import router as categories_router
from app.api.v1.states import router as states_router
from app.api.v1.ministries import router as ministries_router
from app.api.v1.search import router as search_router
from app.api.v1.chat import router as chat_router
from app.api.v1.translate import router as translate_router
from app.api.v1.eligibility import router as eligibility_router

app.include_router(schemes_router, prefix="/api/v1")
app.include_router(categories_router, prefix="/api/v1")
app.include_router(states_router, prefix="/api/v1")
app.include_router(ministries_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(translate_router, prefix="/api/v1")
app.include_router(eligibility_router, prefix="/api/v1")
