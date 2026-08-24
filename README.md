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

The API listens on `http://127.0.0.1:8000`. Docs: `/docs`.

### Frontend (Vite + React)

```bash
cd frontend
npm install
npm run dev
```

The UI is on `http://localhost:5173` and proxies `/api` and `/health` to the backend.

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

Tradenet Chat talks to whatever is at `NEO4J_URI` (default `bolt://127.0.0.1:7687`). Load the tradenet CSVs into Neo4j first — the Docker and `LOAD CSV` steps live in the tradenet README (`docker run … neo4j:latest` on ports 7474/7687, then Browser import of `nodes_countries.csv`, `nodes_categories.csv`, and `rels_trades_with.csv`).

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
