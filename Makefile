# SiteSync — one-command dev loop.  (Windows: run the two commands in `dev` in two terminals.)
.PHONY: install dev backend frontend seed test build

install:
	pip install -r backend/requirements.txt
	npm --prefix frontend install

backend:
	cd backend && python -m uvicorn app.main:app --reload --port 8000

frontend:
	npm --prefix frontend run dev

dev:
	$(MAKE) -j2 backend frontend

seed:
	cd backend && python -m app.seed.run

test:
	cd backend && python -m pytest -q tests

build:            # single-port mode: FastAPI serves frontend/dist on :8000
	npm --prefix frontend run build
