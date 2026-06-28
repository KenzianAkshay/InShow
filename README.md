# ShowSphere

Exhibitor Services Agent Platform: a collection of agents for trade-show
planning, servicing, and execution, working over a shared, evolving semantic
layer in Neo4j.

## Run locally

Requires Docker Desktop.

```
# Mac / Linux
cp .env.example .env
bash scripts/start.sh

# Windows
Copy-Item .env.example .env
./scripts/start.ps1
```

Open http://localhost:3000 and sign in with `user` / `password`.

Stop the stack: `bash scripts/stop.sh` (Mac/Linux) or `./scripts/stop.ps1`
(Windows).

## Environment

Set the API key for whichever model provider your agents use, in `.env`:

- `ANTHROPIC_API_KEY` — for Claude agents
- `OPENAI_API_KEY` — for OpenAI agents
- `NEO4J_PASSWORD` — Neo4j password (default `password`)

## Architecture

- `frontend/` — Next.js app; the single ingress on port 3000, proxies `/api`
  to the backend.
- `backend/` — FastAPI (`uv`), serves `/api`. SQLite for operational data
  (users, agents, data sources, chat). Neo4j for the ontology layer.
- Three services managed by `docker compose`: `frontend`, `backend`, `neo4j`.

## Tests

- Backend: `pytest` (in `backend/`).
- Frontend: build-time type checks (`npm run build` in `frontend/`).
- End-to-end: Playwright in `e2e/` against the running stack:

```
cd e2e
npm install
npx playwright install chromium
npm test   # requires the compose stack running on port 3000
```

## Plan

See `docs/PLAN.md` for the full implementation plan.
