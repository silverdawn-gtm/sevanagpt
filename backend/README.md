# SevanaGPT Backend

FastAPI-powered backend for SevanaGPT — an AI-driven Indian government scheme discovery platform. Provides REST APIs for scheme browsing, hybrid search, multilingual chatbot, voice interaction, and eligibility checking.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI 0.115.6 + Uvicorn |
| Database | PostgreSQL 16 with pgvector |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| LLM | Mistral AI (primary), Groq (fallback) |
| Embeddings | Mistral Embed (1024-dim vectors) |
| Translation | Bhashini NMT + Google Translate fallback |
| Voice | Bhashini ASR/TTS |
| HTTP Client | httpx (async) |

## Prerequisites

- Python 3.12+
- Docker & Docker Compose (for PostgreSQL + pgvector)
- API keys (optional but recommended):
  - [Mistral AI](https://console.mistral.ai) — chat + embeddings
  - [Groq](https://console.groq.com) — free chat fallback
  - [Bhashini](https://bhashini.gov.in) — voice + translation

## Quick Start

### 1. Start the database

```bash
docker compose up -d db
```

This starts PostgreSQL 16 with pgvector on port **5433**.

### 2. Set up Python environment

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure environment

Copy and edit `.env`:

```env
DATABASE_URL=postgresql+asyncpg://myscheme:myscheme_dev@localhost:5433/myscheme
DATABASE_URL_SYNC=postgresql://myscheme:myscheme_dev@localhost:5433/myscheme

# Mistral AI — for chat and embeddings
MISTRAL_API_KEY=your-key-here

# Groq (free fallback for chat)
GROQ_API_KEY=your-key-here

# Bhashini (voice/translation) — optional
BHASHINI_USER_ID=
BHASHINI_API_KEY=
```

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Seed and ingest data

```bash
# Seed reference data (categories, states, ministries, tags)
python -m app.data.seed

# Ingest central schemes (46 central + 54 state)
python -m app.data.ingest_hf

# Ingest state-specific schemes (113 schemes for 14 states)
python -m app.data.ingest_state_schemes

# Ingest from MyScheme.gov.in API (~4,500 schemes)
python -m app.data.ingest_myscheme

# Generate vector embeddings for semantic search (requires Mistral API key)
python -m app.data.generate_embeddings
```

Or run everything at once:

```bash
python -m app.data.ingest_all
```

### 6. Start the server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at http://localhost:8000/docs

## Project Structure

```
backend/
├── app/
│   ├── api/v1/              # API route handlers
│   │   ├── schemes.py       # /schemes - list, detail, featured
│   │   ├── categories.py    # /categories - browse by category
│   │   ├── states.py        # /states - browse by state (with level filter)
│   │   ├── ministries.py    # /ministries - browse by ministry
│   │   ├── search.py        # /search - hybrid keyword + semantic search
│   │   ├── chat.py          # /chat - AI chatbot endpoints
│   │   ├── voice.py         # /voice - ASR, TTS, voice chat
│   │   ├── translate.py     # /translate - text translation
│   │   └── eligibility.py   # /eligibility - scheme eligibility checker
│   │
│   ├── chatbot/             # Chatbot logic
│   │   ├── fsm.py           # Finite State Machine for conversation flow
│   │   └── prompts.py       # LLM prompt templates (language-aware)
│   │
│   ├── data/                # Data ingestion pipeline
│   │   ├── seed.py          # Seed categories, states, ministries, tags
│   │   ├── ingest_hf.py     # Central + MH/TN/UP/RJ state schemes
│   │   ├── ingest_state_schemes.py  # 14-state specific schemes
│   │   ├── ingest_myscheme.py       # MyScheme.gov.in API (~4,500 schemes)
│   │   ├── ingest_kaggle.py         # Kaggle dataset (optional)
│   │   ├── ingest_datagov.py        # data.gov.in API (optional)
│   │   ├── generate_embeddings.py   # Batch vector embedding generation
│   │   ├── pre_translate.py         # Pre-translate scheme names on startup
│   │   └── ingest_all.py            # Orchestrator for all ingestion steps
│   │
│   ├── models/              # SQLAlchemy models
│   │   ├── scheme.py        # Scheme, Category, State, Ministry, Tag, etc.
│   │   └── chat.py          # Conversation, Message
│   │
│   ├── schemas/             # Pydantic response schemas
│   │   └── scheme.py        # SchemeListItem, SchemeDetail, StateOut, etc.
│   │
│   ├── services/            # Business logic layer
│   │   ├── chat_service.py       # Chat pipeline (FSM + LLM + search)
│   │   ├── search_service.py     # Hybrid search (keyword + semantic + RRF)
│   │   ├── mistral_service.py    # LLM chat/embedding (Mistral + Groq)
│   │   ├── bhashini_service.py   # Voice ASR/TTS + NMT translation
│   │   ├── translate_service.py  # Google Translate with caching
│   │   ├── embedding_service.py  # Batch embedding generation
│   │   └── eligibility_service.py # Eligibility matching engine
│   │
│   ├── utils/               # Utilities
│   │   ├── scheme_translate.py   # Translate scheme responses
│   │   ├── translations.py       # Pre-computed translation dictionaries
│   │   ├── languages.py          # Language code mappings
│   │   ├── rate_limit.py         # Rate limiting
│   │   └── slug.py               # URL slug generation
│   │
│   ├── config.py            # Pydantic settings (env vars)
│   ├── database.py          # Async engine + session factory
│   └── main.py              # FastAPI app entry point
│
├── alembic/                 # Database migration scripts
│   └── versions/            # Migration files
├── alembic.ini              # Alembic configuration
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container build
└── .env                     # Environment variables
```

## API Endpoints

### Schemes
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/schemes` | List schemes (filters: category, state, ministry, level, tag, search) |
| GET | `/api/v1/schemes/featured` | Get featured schemes |
| GET | `/api/v1/schemes/{slug}` | Scheme detail with FAQs |

### Taxonomy
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/categories` | List all categories with scheme counts |
| GET | `/api/v1/categories/{slug}` | Schemes in a category |
| GET | `/api/v1/states` | List all states/UTs with scheme counts |
| GET | `/api/v1/states/{slug}` | Schemes in a state (filter by `level=state\|central`) |
| GET | `/api/v1/ministries` | List all ministries |
| GET | `/api/v1/ministries/{slug}` | Schemes by ministry |

### Search
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/search` | Hybrid keyword + semantic search |
| GET | `/api/v1/search/suggest` | Auto-complete suggestions |

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/chat/message` | Send message, get AI response + scheme cards |
| GET | `/api/v1/chat/history/{session_id}` | Get conversation history |
| POST | `/api/v1/chat/reset/{session_id}` | Reset conversation |

### Voice
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/chat/voice` | Full voice pipeline: ASR → chat → TTS |
| POST | `/api/v1/voice/transcribe` | Speech-to-text |
| POST | `/api/v1/voice/synthesize` | Text-to-speech |

### Eligibility
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/eligibility/check` | Check eligibility based on user profile |
| GET | `/api/v1/eligibility/options` | Get filter options (genders, categories, states) |

## Key Implementation Details

### Hybrid Search (Reciprocal Rank Fusion)

Search combines three strategies and merges results using RRF:

1. **Keyword search** — ILIKE pattern matching across scheme name, description, benefits, and eligibility fields
2. **Semantic search** — pgvector cosine distance using Mistral 1024-dim embeddings
3. **Translation search** — Keyword search on the `scheme_translations` table for non-English queries

Results are merged using the formula: `score = 1 / (k + rank + 1)` where `k=60`.

### Chatbot FSM

The conversational AI uses a Finite State Machine with these states:

```
GREETING → NEED_EXTRACTION → SCHEME_SEARCH → SCHEME_DETAIL → CLOSING
                                  ↕
                           DISAMBIGUATION
```

- **Intent classification**: Mistral/Groq LLM classifies user intent, with keyword-based fallback
- **Entity extraction**: Extracts age, gender, state, category, income from conversation context
- **Language-aware**: System prompts instruct the LLM to respond in the user's language
- **Scheme card translation**: Scheme names and descriptions are translated for non-English users
- **Fallback responses**: Pre-built responses in 12 languages when no LLM API key is configured

### Data Ingestion Pipeline

```
seed.py → ingest_hf.py → ingest_state_schemes.py → ingest_myscheme.py → ingest_kaggle.py → ingest_datagov.py → generate_embeddings.py
```

| Source | Schemes | Description |
|--------|---------|-------------|
| ingest_hf.py | ~100 | Hand-curated central + 4 major state schemes |
| ingest_state_schemes.py | ~113 | State schemes for 14 states |
| ingest_myscheme.py | ~4,530 | Official MyScheme.gov.in API |
| ingest_kaggle.py | Variable | Kaggle datasets (requires API key) |
| ingest_datagov.py | Variable | data.gov.in (requires API key) |

All ingestion scripts use slug-based deduplication and are idempotent (safe to re-run).

### Multilingual Support

12 Indian languages supported: English, Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam, Punjabi, Odia, Urdu.

Translation is layered:
1. **scheme_translations table** — pre-computed translations (instant)
2. **Batch Google Translate** — on-demand with caching
3. **Static dictionaries** — pre-translated category, state, ministry names
4. **Bhashini NMT** — for voice pipeline translation

## Make Commands

From the project root:

```bash
make db-up      # Start PostgreSQL container
make db-down    # Stop all containers
make migrate    # Run alembic upgrade head
make seed       # Seed reference data
make ingest     # Ingest HF schemes
make embed      # Generate embeddings
make backend    # Start backend server
make frontend   # Start frontend dev server
```

## Database Reset

To completely reset and re-ingest:

```bash
docker compose down -v
docker compose up -d db
# Wait ~5 seconds for DB to be healthy
cd backend
alembic upgrade head
python -m app.data.ingest_all
```
