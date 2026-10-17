# Decisions

One line each: decision + reason.

## Phase 0
- Python 3.12 venv at `.venv`: it has wheels for torch, OpenSlide and CONCH's dependencies; Delta uses its own module torch (AGENTS.md §5).
- Frontend pinned to Vite 6.4.4 / Vitest 3.2.7: newer Vite needs Node ≥ 22.12, and this machine has Node 22.5.1.
- `@testing-library/jest-dom` pinned to 6.9.1: npm marks 6.10.0 as a broken release.
- Tailwind CSS 4 through `@tailwindcss/vite`: current major; Phase 5 tokens go in its CSS `@theme`.
- Frontend scaffolded by hand instead of `create-vite`, so every version is pinned and nothing extra ships.
- pytest config lives in `backend/pyproject.toml`; tests run from the repo root with `pytest backend`.
- Added `make setup` and `make setup-real`, so teammates can build the environment with one command.
- `make dev` starts only the frontend until the API exists (Phase 4).
- `config.yaml` sits at the repo root; `PROJECT_CONFIG` can point elsewhere (e.g. tests, Delta).
- On this Mac, `make` only runs as `DEVELOPER_DIR=/Library/Developer/CommandLineTools make …`: `xcode-select` points at Xcode.app, whose make shim fails. A human fix (e.g. `sudo xcode-select -s /Library/Developer/CommandLineTools`) is out of scope for an agent.
