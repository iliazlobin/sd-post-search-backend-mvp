# Post Search MVP

A FastAPI-based full-text search backend for user posts, backed by PostgreSQL 16's built-in `tsvector`/GIN full-text search — no Elasticsearch, no Redis, no Kafka.

## Stack

- **FastAPI** (Python 3.12) — async HTTP layer
- **PostgreSQL 16** — primary store + inverted index via generated `tsvector` column + GIN index
- **SQLAlchemy 2.0** — async ORM with `asyncpg`
- **Alembic** — schema migrations
- **Docker Compose** — local dev deployment

## Quick Start

```bash
# Start the stack
docker compose up -d --build

# Run acceptance tests
docker compose exec app pytest verify/acceptance -q

# Run white-box tests (requires a running DB)
docker compose exec app pytest tests/ -q
```

## API

| Method | Path                                    | Description                |
|--------|----------------------------------------|----------------------------|
| GET    | /healthz                               | Health check               |
| POST   | /api/v1/users                          | Create a user              |
| POST   | /api/v1/posts                          | Create a post              |
| GET    | /api/v1/posts/{post_id}                | Post detail with author    |
| GET    | /api/v1/posts/{post_id}/index-status   | Check indexing status      |
| DELETE | /api/v1/posts/{post_id}                | Soft-delete a post         |
| POST   | /api/v1/search                         | Full-text search           |

### Search

**Request:**
```json
POST /api/v1/search
{
  "query": "hello world",
  "mode": "lexical",
  "filters": {
    "author_id": "uuid",
    "date_from": "2026-01-01T00:00:00",
    "date_to": "2026-06-30T23:59:59",
    "language": "en"
  },
  "page_size": 20,
  "page_token": "base64hmac..."
}
```

**Response:**
```json
{
  "results": [
    {
      "post_id": "uuid",
      "author_id": "uuid",
      "author_username": "alice",
      "text_snippet": "hello <mark>world</mark> ...",
      "highlights": ["world"],
      "score": 0.68,
      "created_at": "2026-07-01T12:00:00Z"
    }
  ],
  "next_page_token": "base64hmac..."
}
```

## Functional Requirements (MVP)

- FR1: Keyword search with relevance-ranked results
- FR3: Filter by author, date range, language
- FR4: Real-time indexing (posts searchable immediately)
- FR5: Cursor-based stateless pagination
- FR6: Highlight matching terms in snippets

## Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Postgres FTS over Elasticsearch | Single-node MVP; zero extra infra. GIN-indexed tsvector provides sub-10ms lookup at this scale. |
| D2 | Synchronous indexing (generated column) over Kafka | tsvector computation adds ~1ms to INSERT — no background workers needed. |
| D3 | Soft deletes (is_archived) over GIN tombstoning | Avoids expensive GIN index page scans on delete. |
| D4 | Stateless HMAC-signed cursors over server-side cursors | No memory per active search; re-execution cost is negligible. |
| D5 | ts_headline at query time over stored term positions | Applied only to final page (max 100 posts) — ~5ms overhead. |
| D6 | No semantic search in MVP | Deferred to V2 (requires pgvector + embedding model). |
