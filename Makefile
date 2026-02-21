.PHONY: db-up db-down backend frontend migrate seed ingest embed

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
	cd backend && python -m app.data.ingest_hf

embed:
	cd backend && python -m app.data.generate_embeddings
