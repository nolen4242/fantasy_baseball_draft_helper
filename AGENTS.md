# AGENTS.md

## Cursor Cloud specific instructions

### Project Structure
- **Backend**: Python Flask app in `src/api/app.py`, services in `src/services/`, models in `src/models/`
- **Frontend**: Vanilla TypeScript in `frontend/src/`, compiled to `frontend/static/js/` via `npm run build`
- **HTML templates**: `frontend/templates/index.html` (Jinja2, served by Flask)
- **CSS**: `frontend/static/css/style.css`

### Running the App
- Backend: `python -m src.api.app` (runs Flask on port 5001)
- Frontend build: `npm run build` (compiles TypeScript)
- Frontend watch: `npm run dev` (TypeScript watch mode)

### Key Commands
- **Build**: `npm run build` — must compile cleanly before committing
- **Dev server**: `python -m src.api.app` — starts Flask dev server at `http://localhost:5001`
- No separate frontend dev server; Flask serves the compiled JS and templates

### Caveats
- The `tsconfig.json` compiles from `frontend/src/` to `frontend/static/js/` — always run `npm run build` after changing `.ts` files
- Backend API returns `categories` (category needs) as a dict keyed by category name, not an array — frontend converts this
- Backend API returns `teams` (draft recap) as a dict keyed by team name — frontend converts to array
- The app uses `window` globals (e.g., `window.draftPlayer`, `window.showPlayerDetails`) for onclick handlers in template strings — all exposed via `exposeGlobalMethods()` in `app.ts`
- The `DraftManager` class in `draft-manager.ts` is mostly a placeholder; main logic is in `App` class in `app.ts`
