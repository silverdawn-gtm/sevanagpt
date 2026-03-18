# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SevanaGPT is an AI-powered Indian government scheme discovery platform. Users can search, browse, and chat about 4,668 government schemes in 22 Indian languages. The system uses hybrid search (keyword + semantic via pgvector), an FSM-based chatbot, and multilingual translation via IndicTrans2 (GPU-accelerated, with optional LoRA fine-tuning) with Google Translate fallback.

## Architecture

Four services orchestrated via `docker-compose.yml`, all running in Docker:

1. **db** — PostgreSQL 16 + pgvector (`pgvector/pgvector:pg16`, port 5433). Stores schemes, embeddings, translations, chat history.
2. **backend** — FastAPI (Python 3.12, port 8000). Async throughout (SQLAlchemy 2.0 + asyncpg). Houses the chatbot FSM, hybrid search, data ingestion, and translation services. Alembic reads `DATABASE_URL` env var for Docker (`db:5432`), falls back to `alembic.ini` for local dev (`localhost:5433`).
3. **frontend** — Next.js 16 (React 19, TypeScript 5, Tailwind 4, port 3000). App Router with language context for i18n. Output mode: `standalone`.
4. **indictrans** — IndicTrans2 neural translation microservice (FastAPI, port 7860, base image `pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime`). Loads `ai4bharat/indictrans2-en-indic-dist-200M` with `transformers>=4.35.0,<4.45.0` (pinned for compatibility). Supports optional LoRA adapters via `peft` for domain-specific fine-tuning (adapter path mounted at `/app/adapters`). Uses GPU via NVIDIA runtime with `MAX_BATCH_SIZE=4` (tuned for 6GB VRAM). Model cache persisted via `indictrans_models` Docker volume. Requires HuggingFace token (gated model with fine-grained token needing "public gated repos" permission).

## Current State

- **Database**: 4,668 schemes ingested from HuggingFace, MyScheme.gov.in API, and state-specific sources
- **Translations**: 22 languages total. 11 via MyScheme API (hi, bn, ta, te, mr, gu, kn, ml, pa, or, ur); 11 additional via IndicTrans2/Google Translate (as, ne, sa, sd, mai, doi, kok, sat, mni, bodo, lus). Note: `bodo` and `sat` have NO Google Translate fallback (IndicTrans2-only)
- **Embeddings**: 1024-dim Mistral vectors, generated with rate-limit retry logic (batch_size=10, 1s delay between batches, exponential backoff on 429)
- **API keys**: `backend/.env.txt` contains `MISTRAL_API_KEY` and `GROQ_API_KEY` (do NOT commit)
- **Docker volumes**: `pgdata` (database), `indictrans_models` (model cache), `./indictrans/adapters` bind-mount (LoRA adapters)

## Common Commands

All from project root via Makefile:

```bash
make db-up          # Start PostgreSQL container
make db-down        # Stop all containers
make backend        # uvicorn with --reload on port 8000
make frontend       # next dev on port 3000
make indictrans     # uvicorn on port 7860
make migrate        # alembic upgrade head
make seed           # Seed categories, states, ministries, tags
make ingest         # Run full data ingestion pipeline
make embed          # Generate Mistral embeddings
make test           # pytest (backend only)
```

Docker (full stack):
```bash
docker compose up -d                    # Start all services
docker compose up -d --build            # Rebuild and start
docker compose up -d db backend frontend  # Start without indictrans
docker compose down                     # Stop all
```

Data pipeline (run inside backend container):
```bash
docker exec myscheme-backend python -m app.data.ingest_all           # Full pipeline: seed → ingest → embed
docker exec myscheme-backend python -m app.data.generate_embeddings  # Embeddings only
docker exec myscheme-backend python -m app.data.ingest_translations  # MyScheme API translations (11 langs)
docker exec myscheme-backend python -m app.data.run_translations --all  # IndicTrans/Google translations (22 langs)
docker exec myscheme-backend python -m app.data.run_translations sa mai doi  # Specific languages
```

Frontend-specific:
```bash
cd frontend && npm run dev      # Dev server
cd frontend && npm run build    # Production build
cd frontend && npm run lint     # ESLint
```

Run a single backend test:
```bash
cd backend && pytest tests/test_search.py -v
cd backend && pytest tests/test_search.py::test_function_name -v
```

## Backend Key Patterns

- **API routes** in `backend/app/api/v1/` — each file is a router (schemes, chat, search, translate, eligibility, categories, states, ministries)
- **Services** in `backend/app/services/` — business logic layer. `chat_service.py` orchestrates the chatbot; `search_service.py` implements hybrid search with Reciprocal Rank Fusion (RRF)
- **Chatbot FSM** in `backend/app/chatbot/fsm.py` — states: GREETING → NEED_EXTRACTION → SCHEME_SEARCH → SCHEME_DETAIL → CLOSING (with DISAMBIGUATION)
- **LLM**: Mistral AI (primary) with Groq as fallback, configured in `mistral_service.py`
- **Embeddings**: 1024-dim Mistral vectors stored in pgvector, used for semantic search. Rate-limit handling with exponential backoff in `embedding_service.py`
- **Models** in `backend/app/models/` — Scheme (core), SchemeEmbedding (pgvector), SchemeTranslation, Conversation, Message
- **Data ingestion** in `backend/app/data/` — multiple sources (HuggingFace, MyScheme.gov.in API, state-specific, Kaggle). Idempotent with slug-based deduplication. Run order: seed → ingest → embed
- **Translation pipeline**: `ingest_translations.py` fetches from MyScheme API; `pre_translate.py`/`run_translations.py` uses IndicTrans2 with Google Translate fallback. `BATCH_SIZE=8` (GPU-friendly chunks), `CHUNK_CHAR_LIMIT=4500`, 2 concurrent workers to avoid OOM. Translation priority: IndicTrans2 first → Google Translate fallback (not Bhashini)
- **Scheme translation helper** in `backend/app/utils/scheme_translate.py` — shared utility for translating scheme content across all endpoints. Priority: scheme_translations cache → batch translate → static name maps (for 11 MyScheme languages). Translates name, description, benefits, eligibility, application process, documents required, and nested category/state/ministry names
- **Migrations**: Alembic with async PostgreSQL. `alembic/env.py` reads `DATABASE_URL` env var (for Docker). Config in `backend/alembic.ini`, migrations in `backend/alembic/versions/`

## Frontend Key Patterns

- **App Router** with path alias `@/*` → `src/*`
- **Language context** in `src/context/LanguageContext.tsx` — persists to localStorage, loads translation JSON from `public/locales/{lang}/common.json`
- **API client** in `src/lib/api.ts` — fetch wrapper pointing to `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`)
- **Chat hook** in `src/hooks/useChat.ts` — manages messages, session, and exposes `addVoiceResponse` for voice input flow. Includes `reset` function to clear messages and notify backend. Session IDs generated client-side (`session_{timestamp}_{random}`)
- **Chat components** in `src/components/chat/` — HomeChat (welcome screen with suggestion buttons from i18n keys), ChatWindow, ChatInput, VoiceButton (Web Speech API)
- **Browse pages** use a route group `(browse)/` with shared layout

## Environment Variables

Backend env vars live in `backend/.env.txt`, loaded by docker-compose via `env_file`. Key vars:
- `DATABASE_URL` — async PostgreSQL connection string (Docker: `postgresql+asyncpg://myscheme:myscheme_dev@db:5432/myscheme`)
- `MISTRAL_API_KEY`, `GROQ_API_KEY` — LLM providers
- `INDICTRANS_URL` — URL to indictrans service (Docker: `http://indictrans:7860`). Empty string = disabled
- `INDICTRANS_TIMEOUT` — single request timeout (default 10s)
- `INDICTRANS_BATCH_TIMEOUT` — batch request timeout (default 60s)
- `INDICTRANS_ENABLED` — toggle IndicTrans2 on/off (default true)
- `CORS_ORIGINS` — allowed frontend origins
- `KAGGLE_USERNAME`, `KAGGLE_KEY`, `DATAGOV_API_KEY` — optional data source credentials

Frontend: `NEXT_PUBLIC_API_URL` — backend URL (default `http://localhost:8000/api/v1`)

Indictrans build arg: `HF_TOKEN` — HuggingFace token for gated model access
Indictrans env var: `INDICTRANS_LORA_ADAPTER_PATH` — path to LoRA adapter directory (Docker: `/app/adapters/ml_govscheme`)
Indictrans env vars (optional): `INDICTRANS_DEVICE` (auto-detects cuda/cpu), `INDICTRANS_MAX_BATCH_SIZE` (default 4), `INDICTRANS_MAX_LENGTH` (default 256), `INDICTRANS_NUM_BEAMS` (default 1)

## Known Issues & Gotchas

- **IndicTrans2 + transformers version**: Must pin `transformers<4.45.0` — newer versions break the custom IndicTrans tokenizer (`_special_tokens_map` error). Use `torch_dtype` not `dtype` for model loading. Also pin `peft>=0.7.0,<0.11.0` for LoRA compatibility.
- **IndicTrans2 `use_cache=False`**: The `generate()` call uses `use_cache=False` to work around a `past_key_values` bug in the custom IndicTrans2 model code with newer transformers versions.
- **IndicTrans2 OOM fallback**: If a GPU batch fails with OOM, it falls back to translating one-by-one. Texts are truncated to 500 chars before translation.
- **Google Translate special lang codes**: Some languages need non-obvious codes: `mni` → `mni-Mtei`, `kok` → `gom`. `bodo` and `sat` have NO Google Translate support at all.
- **Docker BuildKit networking**: Build steps can access the internet but `huggingface_hub` may report misleading "connection" errors when the real issue is 403 (token permissions). Check the actual HTTP status.
- **Mistral rate limits**: Free tier hits 429 frequently. Embedding generation uses exponential backoff (5s, 10s, 20s, 40s, 80s).
- **OOM during translations**: Reduce `CONCURRENT_WORKERS` (default 2) and `BATCH_SIZE` (default 8) in `pre_translate.py` if backend gets OOM-killed (exit code 137). For indictrans GPU OOM, reduce `INDICTRANS_MAX_BATCH_SIZE` (default 4, tuned for 6GB VRAM).
- **MyScheme API duplicates**: The API can return duplicate slugs — `ingest_translations.py` deduplicates by `scheme_id` to avoid unique constraint violations.
- **`docker compose up --build` kills exec processes**: Never rebuild a container while `docker exec` tasks are running in it. Use `docker cp` to hot-patch files instead.

## Workflow Orchestration

### 1. Plan Node Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately — don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes — don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests — then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

## Task Management
1. **Plan First**: Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to `tasks/todo.md`
6. **Capture Lessons**: Update `tasks/lessons.md` after corrections

## Core Principles
- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact**: Changes should only touch what's necessary. Avoid introducing bugs.
