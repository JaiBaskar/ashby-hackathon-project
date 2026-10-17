# One-command entry points. `make test` needs no GPU, no internet and no Hugging Face token.
PY ?= .venv/bin/python
FAST := not realmodel and not gpu and not delta

.PHONY: setup setup-real dev test test-backend test-frontend test-real

setup:
	python3.12 -m venv .venv
	$(PY) -m pip install -r backend/requirements.txt
	cd frontend && npm ci

# Real CONCH (torch + conch). On Delta, use the pytorch-conda module's torch instead (AGENTS.md §5).
setup-real: setup
	$(PY) -m pip install -r backend/requirements-real.txt

# Next.js on http://localhost:3000. It forwards /api/* to FastAPI (API_URL, default http://localhost:8000),
# which runs the Python ML code. The FastAPI server arrives in Phase 4; until then this starts Next.js only.
dev:
	cd frontend && npm run dev

test: test-backend test-frontend

test-backend:
	$(PY) -m pytest backend -m "$(FAST)" -q

test-frontend:
	cd frontend && npm test

test-real:
	$(PY) -m pytest backend -m realmodel -v
