PY ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: install build start backend frontend dev test eval up down clean

install:
	python3 -m venv .venv
	$(PIP) install -e "backend[dev]"
	cd frontend && npm install

build:
	cd frontend && npm run build

# One-command start: build the SPA, then serve UI + API from one process.
start: build
	cd backend && ../$(PY) -m uvicorn app.main:app --host 127.0.0.1 --port 8000

backend:
	cd backend && ../$(PY) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

frontend:
	cd frontend && npm run dev

dev:
	@echo "Run 'make backend' and 'make frontend' in two terminals, then open http://127.0.0.1:5173"

test:
	cd backend && ../$(PY) -m pytest

eval:
	cd backend && ../$(PY) -m app.eval.run --with-decisions

up:
	docker compose up --build

down:
	docker compose down

clean:
	rm -rf data/utilityguard.db data/utilityguard.db-wal data/utilityguard.db-shm
