# ShowSphere - Implementation Plan

ShowSphere is an Exhibitor Services Agent Platform: a collection of agents assisting
trade-show planning, servicing, and execution, working over a common, evolving
semantic layer held in a Neo4j graph database.

This is an 11-part plan. Each part is built and verified independently. The user
must explicitly approve each completed part before the next begins.

## Canonical architecture

- Three Docker services managed by `docker compose`:
  - `frontend` - Next.js app (Node process running `next start`).
  - `backend` - FastAPI, serving the API under `/api`. `uv` is the Python
    package manager inside this container.
  - `neo4j` - graph database for the ontology/semantic layer.
- Next.js serves all non-API routes; FastAPI serves `/api`. Single ingress port
  at the compose level.
- SQLite database file on a named volume in the backend; created on first run if
  missing. Holds operational data only.
- Neo4j holds the ontology/semantic layer only (the evolving knowledge graph).
- LLM provider is configurable per agent (Claude or OpenAI) behind a thin
  `LLMProvider` interface. API keys supplied via environment variables.
- Auth: httpOnly session cookie issued by FastAPI, in-memory session store,
  hardcoded `user`/`password`. A `users` table exists so multi-user is a later
  change, not a rewrite.

## Two data stores

- SQLite (operational): users, agents, data sources, chat sessions, messages.
- Neo4j (semantic): the ontology - instance nodes and relationships, plus a
  small meta-layer describing the evolving schema, with provenance for
  evolution and traversal highlighting.

## Conventions

- Color scheme and Enterprise theme from `agents.md`, applied as design tokens
  from Part 2 onward.
- Coding standards from `agents.md`: latest idiomatic library versions, keep it
  simple, no over-engineering, no defensive programming for its own sake, no
  emojis, minimal README, root-cause before fix.
- Start/stop server scripts for Mac, PC, and Linux live in `scripts/`.

## Test stack

- Backend: pytest.
- Frontend unit/integration: Vitest + React Testing Library.
- End-to-end: Playwright, driving the running compose stack.

---

## Part 1 - Plan

Goal: Produce this document and a forward-looking `frontend/AGENTS.md`, and get
user approval.

Deliverables:
- `docs/PLAN.md` (this file).
- `frontend/AGENTS.md` capturing frontend conventions (theme tokens, component
  structure, API access patterns) for later parts.

Acceptance: User approves the plan and architecture.

---

## Part 2 - Scaffolding

Goal: `docker compose up` brings up the backend and Neo4j, and serves a static
"hello world" HTML page that calls a real API endpoint and renders the response.

Scope:
- `docker-compose.yml` with `backend` and `neo4j` services and named volumes.
- FastAPI app with `GET /api/health` returning a real status payload (including
  Neo4j connectivity).
- A static page served as the placeholder frontend that fetches `/api/health`
  and renders the result.
- Design tokens for the color scheme / Enterprise theme defined once for reuse.

Acceptance: `docker compose up` works from a clean checkout; the page shows live
data from `/api/health`; Neo4j is reachable from the backend.

---

## Part 3 - Add Next.js frontend

Goal: Replace the static HTML with a real Next.js app served from its own
container. The hello-world call to `/api/health` still works.

Scope:
- `frontend` service added to compose, building and running the Next.js app.
- App shell using the theme tokens (nav, layout).
- Health check rendered from the Next.js app via `/api`.

Acceptance: Both containers run under compose; the Next.js app renders live
`/api/health` data through the single ingress.

---

## Part 4 - Login

Goal: Visiting `/` redirects to `/login` until the user signs in with
`user`/`password`. Logged-in users see a homepage and can log out.

Scope:
- FastAPI login/logout endpoints; httpOnly session cookie; in-memory session
  store; hardcoded credentials validated against the `users` table seed.
- Next.js login page, auth guard/redirect, logout control.

Acceptance: Unauthenticated access redirects to `/login`; correct credentials
log in and reach the homepage; logout clears the session.

---

## Part 5 - Data modeling

Goal: Define and create both schemas.

Scope:
- SQLite schema and migrations/bootstrap:
  - `users` (id, username, password_hash, created_at).
  - `agents` (id, name, type [`standard` | `ontology_creation`],
    model_provider, model_name, config JSON, data_source_id, created_at,
    updated_at).
  - `data_sources` (id, name, type, location, status, created_at).
  - `chat_sessions` (id, agent_id, user_id, created_at).
  - `messages` (id, session_id, role, content, metadata JSON, created_at) -
    metadata carries ontology traversal paths and canvas payloads.
- Neo4j ontology model:
  - Instance nodes and typed relationships (dynamic, since the ontology is
    auto-built and evolves).
  - A meta-layer (`:OntologyClass`, `:OntologyRelation`) describing the current
    schema.
  - Provenance on nodes/edges (which ingested datapoint created or updated
    them) to support evolution and traversal highlighting.
- Constraints/indexes for the meta-layer and provenance lookups.

Acceptance: Fresh start creates the SQLite DB and applies Neo4j constraints;
both schemas are documented and queryable.

---

## Part 6 - Agent management (CRUD)

Goal: Create, open, list, and delete agents, including the per-agent setup page.

Scope:
- Backend CRUD endpoints over the `agents` table.
- Agent list / dashboard in the frontend (create new, open existing).
- Per-agent setup page: choose model provider and model (Claude or OpenAI),
  select/attach a data source, and configure the ontology layer.

Acceptance: An agent can be created, configured, listed, reopened, and deleted;
configuration persists.

---

## Part 7 - Data ingestion and the Ontology Creation agent

Goal: Ingest a dataset and build/evolve the ontology in Neo4j.

Scope:
- Data source upload/selection and ingestion into the backend.
- The Ontology Creation agent with its own configuration and Research, Analysis,
  Reasoning, and Evaluation stages that produce a graph data model from the
  ingested dataset.
- Merge semantics: newly ingested datapoints integrate with the existing
  ontology (evolution), not replacement; provenance recorded.

Acceptance: Ingesting a dataset produces a connected ontology in Neo4j;
re-ingesting additional data extends rather than overwrites it.

---

## Part 8 - Agent chat and LLM provider abstraction

Goal: A working per-agent chat interface backed by the configured provider and
grounded on the ontology.

Scope:
- `LLMProvider` interface with Claude and OpenAI implementations, selected per
  agent from its config; keys via environment variables.
- Chat endpoint that retrieves relevant ontology context (graph query) and
  passes it to the provider; responses and traversal metadata persisted to
  `messages`.
- Chat UI per agent (history, send, streaming if straightforward).

Acceptance: A prompt to an agent returns a grounded response using the agent's
selected provider; the conversation persists and reloads.

---

## Part 9 - Live ontology visualization

Goal: The ontology graph is visible in every agent interaction, and each prompt
highlights the traversal path through animation.

Scope:
- Ontology graph view rendered alongside the chat.
- On each prompt, the traversal path returned from Part 8 is highlighted with
  animation over the graph.

Acceptance: Firing a prompt visibly animates the corresponding traversal in the
ontology view.

---

## Part 10 - Canvas board

Goal: A per-agent canvas that dynamically renders agent outputs.

Scope:
- Canvas surface alongside chat.
- Render agent-produced outputs: interactive maps, dashboards, bar/line charts,
  and graphs, driven by the user prompt and the agent response payload.

Acceptance: A prompt that yields a visual output renders it on the canvas;
multiple output types are supported.

---

## Part 11 - Ops and hardening

Goal: Operational scripts, end-to-end coverage, and minimal docs.

Scope:
- `scripts/` start and stop scripts for Mac, PC, and Linux.
- Playwright E2E covering login, agent creation, ingestion, chat, and canvas
  over the running compose stack.
- Minimal README (run instructions, env vars).

Acceptance: Scripts start/stop the stack on each platform; E2E passes against the
running stack.

---

## Part 12 - Show Projects (parent container, project-scoped ontology)

Goal: Group agents under a top-level Show Project whose ontology is shared by
all its agents and evolves as data sets are added.

Scope:
- New `show_projects` table; `agents` and `data_sources` carry `show_project_id`.
  Migration files existing rows under a "Default Show" project; the prior global
  Neo4j graph is backfilled with its project id so it stays visible.
- Ontology is scoped per project: entities/classes/relations carry `project_id`;
  uniqueness constraints are composite with `project_id` so the same uid/class
  name can exist in different projects. `read_ontology` and `retrieve_context`
  filter by project.
- API: `/api/projects` CRUD; `?project_id=` on agents, data-sources, and
  ontology; agent create requires `show_project_id`; uploads associate a project.
- Frontend: home lists Show Projects; `/projects/[id]` lists a project's agents;
  the live ontology graph and traversal animation are scoped to the project.

Acceptance: Two projects with overlapping values (e.g. City:Berlin) keep
separate graphs; a prompt animates only that project's nodes. Verified live:
project-2 traversal returned 8 project-2 nodes with zero project-1 leakage.
