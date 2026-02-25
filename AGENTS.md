# AGENTS.md

## Cursor Cloud specific instructions

### Overview

Fantasy Baseball Draft Helper — a monolithic Python Flask + TypeScript web app. No database, no Docker, no external services. All persistence is file-based (CSV + JSON in `data/`).

### Running the app

```bash
python3 run.py
```

Starts on **port 5001** (not 5000). The app loads player data from CSVs in `data/batters/` and `data/pitchers/`. Use the "Reload CBS" and "Reload Steamer" buttons in the UI header, or call the `/api/players/load-cbs` and `/api/players/load-steamer` endpoints to load data.

### Building the frontend

TypeScript sources live in `frontend/src/` and compile to `frontend/static/js/`. Pre-compiled JS is committed, so `npm run build` is only needed after editing `.ts` files. Use `npm run dev` for watch mode.

### Testing

- `python3 -m pytest tests/ -v` — runs the test suite. Currently only fixtures exist in `tests/conftest.py` (no test files yet).
- No dedicated linter configuration (no ESLint, flake8, pyproject.toml, etc.).

### Caveats

- `pip install` goes to `~/.local/` by default (not writable to system site-packages). Ensure `~/.local/bin` is on PATH if running `flask` or `pytest` directly.
- Draft state and team rosters are persisted as JSON in `data/teams/` and `data/drafts/`. The `conftest.py` auto-cleanup fixture wipes these after each test.
- The app uses `flask-cors` so the API can be called from any origin during development.
