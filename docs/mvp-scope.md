# Post Search MVP — MVP Scope

## Stack

- FastAPI (Python 3.12) + PostgreSQL 16 (tsvector/GIN FTS)
- Docker Compose (app + db)
- No Elasticsearch, Redis, or Kafka

## Functional Requirements

| FR | Description | Status |
|----|-------------|--------|
| FR1 | Keyword search with relevance-ranked results | ✅ |
| FR3 | Filter by author, date range, language | ✅ |
| FR4 | Real-time indexing (posts searchable immediately) | ✅ |
| FR5 | Cursor-based stateless pagination | ✅ |
| FR6 | Highlight matching terms in snippets | ✅ |

## Key Design Decisions

1. Postgres FTS over Elasticsearch — no extra infra at MVP scale
2. Synchronous indexing (generated tsvector) over Kafka — ~1ms INSERT overhead
3. Soft deletes (is_archived) over GIN tombstoning — avoids expensive index maintenance
4. Stateless HMAC-signed cursors over server-side cursors — zero memory per search
5. ts_headline at query time over stored positions — ~5ms per query page
6. No semantic search — deferred to V2 (pgvector + embedding model)

## Out of Scope

- Semantic/embedding search (V2)
- Kafka event pipeline
- Redis hot index / SSD segment tiering
- Sharding / scatter-gather
- Authentication / authorization
- Rate limiting
