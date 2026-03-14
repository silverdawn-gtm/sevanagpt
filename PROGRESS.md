# SevanaGPT - Task Progress Tracker

## Goal
Set up the PostgreSQL database in Docker, ingest all 4,600+ government schemes, and fix all codebase inconsistencies.

---

## Phase 1: Database Setup - COMPLETE
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.1 | Start PostgreSQL container via Docker | DONE | `docker compose up -d db` — healthy on port 5433 |
| 1.2 | Verify DB is healthy and accepting connections | DONE | pgvector/pgvector:pg16 |
| 1.3 | Run Alembic migrations (5 total) | DONE | All 5 migrations applied (through d4e5f6a7b8c9) |
| 1.4 | Seed reference data | DONE | 18 categories, 36 states, 64 ministries, 4627 tags |

## Phase 2: Data Ingestion - COMPLETE (4,743 schemes)
| # | Task | Status | Notes |
|---|------|--------|-------|
| 2.1 | Ingest HuggingFace/embedded schemes | DONE | 100 central schemes (source: manual) |
| 2.2 | Ingest state schemes | DONE | 113 state-specific schemes (source: embedded) |
| 2.3 | Ingest MyScheme.gov.in | DONE | 4,530 schemes (source: myscheme) |
| 2.4 | Verify total scheme count >= 4,600 | DONE | **4,743 total** (659 central + 4,084 state) |

## Phase 3: Fix Backend Inconsistencies - COMPLETE
| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.1 | Add `source`, `updated_at` to SchemeDetail schema | DONE | schemas/scheme.py |
| 3.2 | Add `extra` field to ChatHistoryMessage schema | DONE | schemas/chat.py |
| 3.3 | Fix migration defaults (status, featured, source) | DONE | New migration d4e5f6a7b8c9 |
| 3.4 | Update source field comment | DONE | Added myscheme, embedded to docs |
| 3.5 | Remove unused BHASHINI env vars from .env.example | DONE | Removed BHASHINI_USER_ID/API_KEY |
| 3.6 | Fix hardcoded CORS IP in config.py | DONE | Removed 192.168.0.244 |
| 3.7 | Add IndicTrans service to docker-compose.yml | DONE | Port 7860 |
| 3.8 | Add `test` target to Makefile | DONE | `make test` runs pytest |
| 3.9 | Update Makefile `ingest` to use ingest_all | DONE | Now runs full pipeline |
| 3.10 | Fix IndicTrans client initialization + logging | DONE | Better error messages |
| 3.11 | Add translate_service.py diagnostic logging | DONE | Logs IndicTrans success/fallback |

## Phase 4: Fix Frontend Inconsistencies - COMPLETE
| # | Task | Status | Notes |
|---|------|--------|-------|
| 4.1 | Fix null crash on .join() for nullable arrays | DONE | target_gender, target_social_category |
| 4.2 | Fix null coalescing bug (total ?? length) | DONE | categories, states, ministries pages |
| 4.3 | Remove hardcoded English fallback strings | DONE | scheme_detail keys |
| 4.4 | Fix language switching hydration bug | DONE | Sync localStorage read in useState init |
| 4.5 | Add translationsReady flag to LanguageContext | DONE | Prevents stale UI |
| 4.6 | Translate scheme_detail keys in 21 locale files | DONE | scheme_info, launch_date, deadline, benefit_type, helpline |
| 4.7 | Remove unused content_original from ChatMessage type | DONE | types.ts |

## Phase 5: Verification - COMPLETE
| # | Task | Status | Notes |
|---|------|--------|-------|
| 5.1 | Run backend tests | DONE | 109 passed, 49 pre-existing failures (need live server) |
| 5.2 | Verify migration chain | DONE | 5 migrations, head at d4e5f6a7b8c9 |
| 5.3 | Final scheme count verification | DONE | **4,743 schemes** (target: 4,600+) |

---

## Database Summary
```
Total schemes:  4,743
Categories:     18
States/UTs:     36
Ministries:     64
Tags:           4,627
Featured:       12

By source:     manual=100, embedded=113, myscheme=4,530
By level:      central=659, state=4,084
```

## Files Modified

### Backend
- `app/schemas/scheme.py` — Added source, updated_at to SchemeDetail
- `app/schemas/chat.py` — Added extra field to ChatHistoryMessage
- `app/models/scheme.py` — Updated source field comment
- `app/config.py` — Removed hardcoded CORS IP
- `app/services/indictrans_client.py` — Fixed client init logic + logging
- `app/services/translate_service.py` — Added IndicTrans diagnostic logging
- `.env.example` — Removed unused BHASHINI vars
- `alembic/versions/d4e5f6a7b8c9_fix_column_defaults.py` — New migration

### Frontend
- `src/context/LanguageContext.tsx` — Fixed hydration, added translationsReady
- `src/app/(browse)/schemes/[slug]/page.tsx` — Null checks, removed fallback strings
- `src/app/(browse)/categories/[slug]/page.tsx` — Fixed total coalescing
- `src/app/(browse)/states/[slug]/page.tsx` — Fixed total coalescing
- `src/app/(browse)/ministries/[slug]/page.tsx` — Fixed total coalescing
- `src/lib/types.ts` — Removed unused content_original
- `public/locales/*/common.json` — 21 locale files translated

### Infrastructure
- `docker-compose.yml` — Added indictrans service
- `Makefile` — Added test target, fixed ingest target

## Current Status: ALL TASKS COMPLETE
## Last Updated: 2026-02-24
