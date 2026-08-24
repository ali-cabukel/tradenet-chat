# Tradenet Chat

Conversational agent that writes read-only Cypher against a Neo4j graph. The default schema is the tradenet Country / Category / `TRADES_WITH` trade network.

## Setup

### Backend (Poetry)

```bash
cd backend
cp .env.template .env
# set OPENAI_API_KEY (or LLM_PROVIDER=ollama) and Neo4j credentials
poetry install
poetry run tradenet-chat-api
```

The API listens on `http://127.0.0.1:8000`. Docs: `/docs`. Persistence defaults to SQLite at `backend/data/tradenet-chat.db`. To use Postgres instead, set `DATABASE_URL` (`postgres://` and `postgresql://` are rewritten to `postgresql+asyncpg://`):

```bash
DATABASE_URL=postgresql+asyncpg://tradenet:tradenet@127.0.0.1:5432/tradenet_chat
```

### Frontend (Vite + React)

```bash
cd frontend
npm install
npm run dev
```

The UI is on `http://localhost:5173` and proxies `/api` and `/health` to the backend.

## Docker Compose

Postgres, Neo4j, the API, and a production UI (nginx on port 8080) start together from the repo root. Copy `.env.example` to `.env` and set `OPENAI_API_KEY` (or use `backend/.env`).

```bash
cp .env.example .env
docker compose up --build
```

| Service | URL |
| ------- | --- |
| UI | http://localhost:8080 |
| API | http://localhost:8000 (`/docs`, `/health`) |
| Postgres | `localhost:5432` (`tradenet` / `tradenet` / `tradenet_chat`) |
| Neo4j Browser | http://localhost:7474 (`neo4j` / `tradenet`) |

The API waits until Postgres and Neo4j are healthy, then runs `create_all` plus additive column checks. Tables are created on first boot; there is no separate migration step.

To run only the databases and keep Poetry/Vite locally:

```bash
docker compose up postgres neo4j
```

Then point `backend/.env` at them (`DATABASE_URL=postgresql+asyncpg://tradenet:tradenet@127.0.0.1:5432/tradenet_chat`, `NEO4J_PASSWORD=tradenet`).

Put tradenet CSVs in `neo4j/import/` (or set `TRADENET_CSV_DIR` to the tradenet `data/neo4j` folder) and load them in Neo4j Browser with the `LOAD CSV` steps from the tradenet README. Raise `NEO4J_HEAP_MAX` if a large import hits memory limits.

Optional local LLM:

```bash
LLM_PROVIDER=ollama OLLAMA_BASE_URL=http://ollama:11434 docker compose --profile ollama up --build
```

## Auth

Register, then exchange email/password for a JWT (form-urlencoded, FastAPI Users):

| Method | Path | Notes |
| ------ | ---- | ----- |
| `POST` | `/api/auth/register` | JSON `{ "email", "password" }` |
| `POST` | `/api/auth/jwt/login` | `application/x-www-form-urlencoded` `username` + `password` |
| `GET` | `/api/users/me` | `Authorization: Bearer <token>` |

Chat (same bearer token):

| Method | Path |
| ------ | ---- |
| `POST` | `/api/chat/threads` |
| `GET` | `/api/chat/threads` |
| `DELETE` | `/api/chat/threads/{id}` | Deletes the thread after you confirm in the UI |
| `GET` | `/api/chat/threads/{id}/messages` |
| `POST` | `/api/chat/threads/{id}/messages` | May return `pending_approval` instead of a final `reply` |
| `GET` | `/api/chat/threads/{id}/approval` | Current gated tool calls waiting for you |
| `POST` | `/api/chat/threads/{id}/approvals` | JSON `{ "decision": "accept" \| "reject" }` |
| `PATCH` | `/api/chat/threads/{id}/messages/{message_id}/feedback` | JSON `{ "rating": "up" \| "down" \| null }` |
| `POST` | `/api/chat/threads/{id}/messages/{message_id}/regenerate` | Re-runs the latest assistant reply |

Health: `GET /health` (also `/api/health`).

## Neo4j (tradenet graph)

Tradenet Chat talks to whatever is at `NEO4J_URI` (default `bolt://127.0.0.1:7687`). Load the tradenet CSVs into Neo4j first — Docker Compose in this repo starts Neo4j on 7474/7687 with password `tradenet`, or follow the tradenet README (`docker run … neo4j:latest`). Then import `nodes_countries.csv`, `nodes_categories.csv`, and `rels_trades_with.csv` in Browser.

Writes are rejected. The agent may only `MATCH` / `RETURN` (and similar reads). Cypher, NewsAPI, and web news searches pause in the UI until you approve or reject them. Schema lookup and Wikipedia run without a prompt.

## News

Set `NEWS_API_KEY` in `backend/.env` for [NewsAPI.org](https://newsapi.org). Without it, the agent still searches news via DuckDuckGo, falling back to Google News RSS.

## Example questions

- Which countries export the most energy to Germany?
- Show food trade from the USA to Türkiye
- What are the top partners for US machinery exports?
- List node labels and relationship types in the graph
- What is Türkiye's population and GDP?
- Give a short profile of Germany (capital, population)
- What is the latest news on US–China trade?
- Any recent headlines about Turkish energy exports?
