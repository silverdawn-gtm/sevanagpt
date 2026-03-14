.PHONY: db-up db-down backend frontend migrate seed ingest ingest-all embed download-model indictrans test

db-up:
	docker compose up -d db

db-down:
	docker compose down

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

migrate:
	cd backend && alembic upgrade head

seed:
	cd backend && python -m app.data.seed

ingest:
	cd backend && python -m app.data.ingest_all

ingest-all:
	cd backend && python -m app.data.ingest_all

embed:
	cd backend && python -m app.data.generate_embeddings

download-model:
	cd indictrans && python download_model.py

indictrans:
	cd indictrans && uvicorn app.main:app --host 0.0.0.0 --port 7860

test:
	cd backend && pytest
