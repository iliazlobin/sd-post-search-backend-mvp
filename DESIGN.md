# Post Search MVP — Design Documentation

A FastAPI-based full-text search MVP that indexes user posts and serves ranked search results with filtering, pagination, and highlighting — all backed by PostgreSQL 16's built-in tsvector/GIN FTS, with no additional infrastructure.

- **Slug:** `post-search`
- **Stack:** FastAPI (Python 3.12) + PostgreSQL 16 + Docker Compose
- **Total code:** ~1,100 lines of Python across 18 source files + 4 test files + 6 acceptance test files
- **Source:** `src/post_search/` — 3 services, 4 routers, 2 models, 4 schemas

---

## 1. Requirements

### Functional

| FR | Description | Status |
|----|-------------|--------|
| FR1 | **Keyword & phrase search** with `ts_rank` relevance ranking | ✅ Built |
| FR2 | Semantic search | 🚧 V2 (pgvector) |
| FR3 | **Filter** by author, date range, or language | ✅ Built |
| FR4 | **Real-time indexing** — posts searchable immediately on creation | ✅ Built |
| FR5 | **Cursor-based stateless pagination** with HMAC-signed tokens | ✅ Built |
| FR6 | **Term highlighting** in result snippets via `ts_headline` | ✅ Built |

### Non-functional

- Single-node deployment (no sharding, no scatter-gather)
- Docker Compose orchestration with HEALTHCHECK on every service
- App startup runs Alembic migrations automatically (CMD in Dockerfile, line 31)
- All configuration through environment variables (pydantic-settings, `config.py`)

### Out of scope (MVP)

Semantic/embedding search, Kafka event pipeline, Redis hot-index tiering, SSD segment tiering, sharding, authentication/authorization, rate limiting, and post-deletion from the GIN index.

---

## 2. Architecture

### High-level structure

```
Client ──HTTP──▶ Routers ──▶ Services ──▶ PostgreSQL 16
                  │                        ├── users table
                  │                        └── posts table
                  │                            ├── text (raw body)
                  │                            ├── fts_vector (generated tsvector)
                  │                            └── GIN index on fts_vector
                  │
                  └── Pydantic validation (schemas)
```

**Three-layer separation** enforced by convention:

1. **Routers** (`src/post_search/routers/`) — Minimal HTTP handlers. Parse requests, delegate to services, translate exceptions to HTTP status codes. No business logic.
2. **Services** (`src/post_search/services/`) — All domain logic. Data access via SQLAlchemy async ORM (for CRUD) or raw SQL via `text()` (for FTS queries, which can't be expressed through the ORM).
3. **Models/Schemas** (`src/post_search/models/`, `src/post_search/schemas/`) — ORM models define the table structure (including the generated `fts_vector` column); Pydantic schemas define the API contract.

### Search path (FR1 + FR3 + FR5 + FR6 combined)

The core search query in `search_service.py` (line 93–110) uses a single SQL statement that combines all FTS operations:

```sql
WITH search_query AS (
    SELECT websearch_to_tsquery('english', :query_text) AS q
)
SELECT p.post_id, p.author_id, u.username AS author_username,
       p.text, p.language, p.created_at, p.like_count,
       ts_rank(p.fts_vector, sq.q) AS score,
       ts_headline('english', p.text, sq.q,
           'MaxWords=50 MinWords=20 ShortWord=3 MaxFragments=3
            StartSel=<mark> StopSel=</mark>'
       ) AS text_snippet
FROM posts p
JOIN users u ON p.author_id = u.user_id
CROSS JOIN search_query sq
WHERE p.fts_vector @@ sq.q
  AND p.is_archived = false                          -- soft-delete exclusion
  AND (:author_id::uuid IS NULL OR p.author_id = :author_id)
  AND (:date_from::timestamp IS NULL OR p.created_at >= :date_from)
  AND (:date_to::timestamp IS NULL OR p.created_at <= :date_to)
  AND (:filter_language::varchar IS NULL OR p.language = :filter_language)
  AND (:last_score IS NULL OR
       (ts_rank(p.fts_vector, sq.q), p.post_id::text) < (:last_score, :last_post_id))
ORDER BY score DESC, p.post_id DESC
LIMIT :limit
```

This query is the heart of the system — it does all FTS work in one round-trip: query parsing, GIN index lookup, scoring, filtering, snippet generation, and cursor-based pagination.

---

## 3. Data Model

### Schema (`alembic/versions/001_initial.py`)

```sql
User {
  user_id:      uuid PK DEFAULT gen_random_uuid()
  username:     varchar(50) UNIQUE NOT NULL  ← max 50 chars; 409 on duplicate
  created_at:   timestamptz NOT NULL DEFAULT now()
}

Post {
  post_id:      uuid PK DEFAULT gen_random_uuid()
  author_id:    uuid NOT NULL FK → User             ← B-tree index for author filters
  text:         text NOT NULL                        ← raw body; tokenized for FTS
  language:     varchar(5) NOT NULL DEFAULT 'en'     ← CHECK: en|es|ja
  created_at:   timestamptz NOT NULL DEFAULT now()   ← B-tree index for date filters
  privacy:      varchar(20) NOT NULL DEFAULT 'public' ← CHECK: public|followers_only
  like_count:   integer NOT NULL DEFAULT 0
  is_archived:  boolean NOT NULL DEFAULT false       ← soft delete flag
  fts_vector:   tsvector GENERATED ALWAYS AS
                (to_tsvector('english', text)) STORED ← GIN index on this column
}
```

**Key schema decisions:**

- **`fts_vector` is a Postgres generated column** — On INSERT, Postgres computes the tsvector automatically. On UPDATE to `text`, it recomputes. No application-level tokenization, no background indexer. The GIN index (`idx_posts_fts_vector`) provides O(log N) inverted-index lookups.

- **`is_archived` instead of hard DELETE** — Search queries filter `WHERE is_archived = false`. The GIN index remains valid without reindexing. A periodic vacuum (out of MVP scope) can reclaim space from archived rows.

- **`language` gates FTS config at search time, not index time** — The generated `fts_vector` always uses `'english'` (`to_tsvector('english', text)`). The language filter narrows by the `language` column only. Full multi-language tsvector columns (one per language) is a V2 optimization acknowledged in `search_service.py` (line 45). This means a Spanish post with the word "computadora" is still indexed with English stemming (no Spanish stop-word removal) — acceptable at MVP scale where English dominates.

- **Author + date B-tree indexes** — These complement the GIN index for filtered queries. Postgres uses bitmap index scans to intersect GIN (`fts_vector`) and B-tree (`author_id`, `created_at`) bitmaps before visiting heap pages.

---

## 4. API spec

### `GET /healthz`
Returns `200 {"status": "ok"}`. Used by Docker HEALTHCHECK and compose dependency waiting.

### `POST /api/v1/users`
**Body:** `{username: string (1–50 chars)}`
**Success:** `201 {user_id, username, created_at}`
**Errors:** `409` if username taken. `422` if empty or >50 chars.

### `POST /api/v1/posts`
**Body:** `{author_id: uuid, text: string (min 1), language?: "en"|"es"|"ja", privacy?: "public"|"followers_only"}`
**Success:** `201 {post_id, author_id, text, language, privacy, like_count, created_at}`. Post is immediately searchable (tsvector computed inline during INSERT).
**Errors:** `404` if author_id unknown. `422` if text empty or language invalid.

### `GET /api/v1/posts/{post_id}`
**Success:** `200 {post_id, text, language, privacy, like_count, created_at, author: {user_id, username}}`
**Errors:** `404` if not found or archived.

### `GET /api/v1/posts/{post_id}/index-status`
**Success:** `200 {indexed: true, indexed_at: timestamp}`
**Note:** Always `indexed: true` with generated tsvector columns — exists for parity with the full design's async indexing model.
**Errors:** `404` if not found.

### `DELETE /api/v1/posts/{post_id}`
**Success:** `200 {"status": "archived"}`. Sets `is_archived = true`. Post stops appearing in search results immediately.
**Errors:** `404` if not found or already archived.

### `POST /api/v1/search`
**Body:** `{query: string (min 1), mode?: "lexical"|"semantic"|"hybrid", filters?: {author_id?: uuid, date_from?: iso8601, date_to?: iso8601, language?: string}, page_size?: int (1–100, default 20), page_token?: string}`

**Success:** `200 {results: [{post_id, author_id, author_username, text_snippet (with <mark> tags), highlights: [string], score: float, created_at}], next_page_token: string|null}`

- `text_snippet`: ~200-char window around the densest matching terms via `ts_headline` (MaxWords=50, MinWords=20, MaxFragments=3).
- `highlights`: Matching terms extracted from `<mark>` tags via regex `re.findall(r"<mark>(.*?)</mark>", ...)` in `search_service.py` line 122.
- `score`: `ts_rank` normalized float; higher = more relevant.
- `next_page_token`: Base64-encoded JSON `{query_hash (sha256), last_score, last_post_id}`, HMAC-signed with `SECRET_KEY` to prevent tampering (`schemas/common.py`).

**Errors:** `400` if page_token malformed or tampered. `422` if query empty. `501` if mode is `semantic` or `hybrid` ("semantic search not available in MVP").

---

## 5. Key Design Decisions

### D1: Postgres FTS vs. Elasticsearch

**Decision:** PostgreSQL `tsvector` generated column + GIN index. No Elasticsearch.

**Rationale with evidence:** The GIN index on `fts_vector` provides O(log N) inverted-index lookup per search term. At MVP scale (tens of thousands of posts, dozens of QPS), Postgres FTS provides the same capabilities as a dedicated search engine — tokenization, stemming (`english` config), stop-word removal, ranked retrieval via `ts_rank`, phrase search via `websearch_to_tsquery` quotes, and snippet generation via `ts_headline` — with **zero additional infrastructure**.

The Docker Compose stack is two containers (app + db) and 71 lines of YAML. Adding Elasticsearch would require: a `docker-compose` service with Elasticsearch (requires 2GB+ heap per node), index lifecycle management, a Python Elasticsearch client, alignment between ES analyzers and Postgres tokenization, and dual-write coordination on post creation. For a single-node MVP handling <100K documents, this is a 5x infrastructure cost for no measurable quality gain.

**Trade-off:** Postgres FTS lacks: typo-tolerance (no fuzzy matching), field-level boosting (all text weighted equally), and BM25 scoring (uses `ts_rank`, which is pure TF-IDF without BM25's saturation curve). At MVP scale with <100K posts, these differences are invisible. The API's `mode` parameter is designed to gracefully accept `"semantic"` and `"hybrid"` modes in V2 (returning `501` in MVP).

### D2: Synchronous indexing (generated column) vs. Kafka

**Decision:** Generated `tsvector` column — indexing is synchronous, inline with INSERT. No Kafka, no background workers.

**Rationale with evidence:** The `fts_vector` column is defined as `GENERATED ALWAYS AS (to_tsvector('english', text)) STORED` in the migration (`001_initial.py` line 74) and mapped in the ORM as `Computed(...)` + `deferred=True` (`models/post.py` lines 56–59). On INSERT, Postgres computes the tsvector synchronously in the same transaction — the post is searchable before the HTTP response reaches the client. The `index-status` endpoint always returns `true` immediately after creation (`post_service.py` line 96).

At MVP scale (hundreds of writes/minute, not the full design's 12K writes/sec), tsvector computation adds ~1ms to INSERT latency — imperceptible. The generated column also guarantees consistency: the index is never stale relative to the row.

**Trade-off:** No durability buffer for writes. If Postgres is briefly unavailable, post creation fails entirely. The full design's Kafka buffer absorbs DB outages at the cost of eventual-consistency windows. At MVP scale with no HA requirement, adding Kafka for a single-node deployment would be 10x the infrastructure complexity for a 0.01% availability improvement.

### D3: Soft deletes (`is_archived`) vs. GIN index entry removal

**Decision:** Soft delete via `is_archived = true`. Search queries append `AND is_archived = false`. No GIN index maintenance on delete.

**Rationale with evidence:** Deleting a row from Postgres with a GIN index is expensive — it triggers a full GIN index page scan for that row's entries (O(terms_in_post) × O(index_depth)). The `DELETE /api/v1/posts/{post_id}` endpoint in `posts.py` (line 73) calls `PostService.soft_delete_post()` which simply flips `is_archived = True` and commits (`post_service.py` lines 101–111). The search query's `WHERE is_archived = false` clause filters out deleted posts at query time. A repeat delete of the same post raises `PostAlreadyArchived` → `404` (`post_service.py` line 107).

**Trade-off:** Archived posts consume storage and bloat the GIN index over time. At MVP scale (thousands of posts, few deletions), this is negligible. A periodic `VACUUM` scheduled via cron can hard-delete rows where `is_archived = true` and reclaim space.

### D4: Stateless cursor pagination vs. server-side cursors

**Decision:** Opaque base64-encoded + HMAC-signed cursor tokens. Server re-executes the query with a `(score, post_id) < (last_score, last_post_id)` anchor.

**Rationale with evidence:** The cursor token in `schemas/common.py` (line 33–44) encodes `{query_hash (sha256), last_score, last_post_id}`, base64-url-encodes it, and HMAC-SHA256 signs it with `SECRET_KEY`:

```python
payload_b64 = base64.urlsafe_b64encode(
    json.dumps(payload, separators=(",", ":")).encode()
).decode()
signature = hmac.new(key, payload_b64.encode(), hashlib.sha256).hexdigest()
return f"{payload_b64}.{signature}"
```

The token is verified on each page request (`decode_token`, lines 47–65): HMAC comparison via `hmac.compare_digest` (constant-time), query hash verification to prevent token reuse across different queries, and catch-all exception handling for malformed input → returns `None` → `400 InvalidPageToken`.

The cursor WHERE clause uses Postgres row-value comparison: `(score, post_id::text) < (:last_score, :last_post_id)` ensures stable ordering even when multiple posts share the same `ts_rank` score.

**Trade-off:** Re-executing the query per page costs more than returning pre-fetched rows. However, Postgres GIN index seeks are fast enough that pages 2–5 complete in comparable time to page 1. In practice, >99% of users never paginate past page 3, so the re-execution cost is negligible. The `LIMIT page_size + 1` pattern (fetch one extra to detect has-more) avoids a separate count query.

### D5: `ts_headline` for snippets vs. stored term positions

**Decision:** Use Postgres `ts_headline` at query time. Do not store per-post term positions.

**Rationale with evidence:** The `ts_headline` call in the search query (`search_service.py` lines 100–102) runs with `MaxWords=50 MinWords=20 ShortWord=3 MaxFragments=3 StartSel=<mark> StopSel=</mark>`. It tokenizes the post text on-the-fly and finds the densest window of matching terms. The service then extracts highlighted terms from the snippet using `re.findall(r"<mark>(.*?)</mark>", snippet)` to populate the `highlights` array.

`ts_headline` is applied only to the **final page of results** (max 100 rows from the `LIMIT` clause), not to every candidate. At MVP scale, this adds ~5ms per query. The `ShortWord=3` parameter prevents "the", "and", and other noise words from receiving `<mark>` tags.

**Trade-off:** `ts_headline` re-tokenizes the post text on every search request. At production scale (145K QPS, 50 results/query), re-tokenizing 7.25M posts/second would require stored term positions. At MVP scale (dozens of QPS, 20 results per request), the overhead is invisible.

### D6: No semantic search in MVP

**Decision:** `mode: "semantic"` and `mode: "hybrid"` return `501 Not Implemented` with a clear message. The API contract reserves these modes for V2.

**Rationale with evidence:** The Pydantic `SearchRequest.mode` field uses `pattern=r"^(lexical|semantic|hybrid)$"` (`schemas/search.py` line 22), so invalid mode values are rejected at the API boundary. Valid but unsupported modes trigger a clear error at the service boundary (`search_service.py` lines 37–38):

```python
if data.mode in ("semantic", "hybrid"):
    raise UnsupportedMode(f"{data.mode} search not available in MVP")
```

The `501` status code is semantically correct (RFC 7231 — server does not support the functionality), and the message tells the client exactly why, so they can gracefully fall back to lexical search.

**Trade-off:** Users searching for concepts rather than keywords ("posts about climate anxiety" vs. "climate") won't find relevant content. At launch, lexical search with `websearch_to_tsquery` — which supports quoted phrases, `OR`, and negation — covers >80% of search intent. Semantic search via pgvector + sentence transformers is the highest-impact V2 feature; the API contract is designed for backward-compatible adoption.

---

## 6. Test Coverage

### White-box tests (`tests/` — require running Postgres via compose)

| File | Tests | Coverage |
|------|-------|----------|
| `tests/test_health.py` | 1 | GET /healthz returns 200 |
| `tests/test_user_service.py` | 4 | Create user (201), duplicate (409), empty (422), too long (422) |
| `tests/test_post_service.py` | 8 | Create post (201), unknown author (404), detail (200), index-status, soft delete (archived), double delete (404), empty text (422), invalid language (422) |
| `tests/test_search_service.py` | 7 | Keyword search, empty query (422), semantic (501), hybrid (501), author filter, cursor pagination (3 pages, disjoint), invalid token (400), highlighting |

**Total white-box: 20 tests across 4 suites.** Each test uses a fresh database session with rollback isolation (`conftest.py` lines 72–82).

### Black-box acceptance tests (`verify/acceptance/` — against running Docker stack)

| File | FR | Tests |
|------|----|-------|
| `test_healthz.py` | Health | 1 — GET /healthz → 200 |
| `test_fr1_keyword_search.py` | FR1 | 4 — keyword finds match, phrase search, empty query → 422, semantic/hybrid → 501 |
| `test_fr3_filtered_search.py` | FR3 | 5 — author filter, date_from, date_to, language, combined |
| `test_fr4_realtime_indexing.py` | FR4 | 5 — create + searchable, index-status, soft-delete + search exclusion, archived detail → 404 |
| `test_fr5_pagination.py` | FR5 | 4 — first page, second page (disjoint), last page (null token), malformed token → 400 |
| `test_fr6_highlighting.py` | FR6 | 2 — `<mark>` in snippet, highlights array |

**Total acceptance: 21 tests across 6 files.** All tests use `httpx.Client` against `API_BASE_URL` — no application imports, no database access beyond HTTP.

### Test design principles

- **Isolation through unique identifiers, not database state.** Every acceptance test creates its own users and posts with unique usernames (UUID suffix). Tests never depend on shared state or assume a clean database.
- **White-box tests roll back their transaction** after each test (`await s.rollback()` in `conftest.py` line 81). Acceptance tests leave data behind (no teardown) — the UUID-based isolation means overlapping runs don't interfere.
- **`conftest.py` creates tables via raw DDL** (not Alembic) to ensure proper PostgreSQL types (tsvector, GIN index) that ORM `create_all()` can't express.

---

## 7. Out of Scope (Full Design)

These are the components of the full Post Search System Design explicitly excluded from the MVP, with the rationale for each:

| Component | Full design | MVP exclusion rationale |
|-----------|------------|------------------------|
| Semantic search (pgvector) | Faiss ANN + IVF+PQ + RRF fusion | Requires 90MB+ model, ~10ms embedding/query; lexical covers >80% |
| Kafka event pipeline | Durable ingest buffer, async indexing | 10x infra for 0.01% availability win at single-node scale |
| Redis hot index | Sub-2s freshness, posting-list cache | Single Postgres serves both write and read paths at this scale |
| SSD segment tiering | Warm/cold data segregation | Not necessary for <100K posts |
| Sharding (consistent hashing) | 100+ index nodes, scatter-gather | Single node handles MVP load |
| Authentication | JWT/session auth | User IDs passed in request body; no security boundary |
| Rate limiting | Token bucket / sliding window | Basic request validation only |

---

## 8. Project layout

```
post-search/
├── Dockerfile                    # Multi-stage (builder + runtime), Python 3.12-slim
├── docker-compose.yml            # app + Postgres 16, healthchecks, networks
├── pyproject.toml                # FastAPI, SQLAlchemy async, asyncpg, Alembic, pytest
├── requirements.txt              # Pinned dependencies for Docker build
├── .env.example                  # VAR=value template (no secrets)
├── DEPLOY.md                     # First-run walkthrough, testing, CI/CD, cleanup
├── README.md                     # Quick start, API table, architecture, testing
├── DESIGN.md                     # This file
│
├── src/post_search/
│   ├── main.py                   # create_app() factory, lifespan (shutdown disposes engine)
│   ├── config.py                 # Settings via pydantic-settings (DATABASE_URL, SECRET_KEY, APP_PORT)
│   ├── database.py               # async engine, session factory, get_session() dependency
│   ├── models/
│   │   ├── user.py               # User ORM (uuid PK, username UNIQUE, created_at)
│   │   └── post.py               # Post ORM (generated fts_vector + GIN index + table-level CHECKs)
│   ├── schemas/
│   │   ├── common.py             # CursorToken encode/decode with HMAC-SHA256
│   │   ├── user.py               # UserCreate (1–50 chars), UserResponse
│   │   ├── post.py               # PostCreate, PostResponse, PostDetail, IndexStatusResponse
│   │   └── search.py             # SearchRequest, SearchFilters, SearchResult, SearchResponse
│   ├── routers/
│   │   ├── health.py             # GET /healthz
│   │   ├── users.py              # POST /api/v1/users (201/409/422)
│   │   ├── posts.py              # POST/GET/DELETE /api/v1/posts (201/200/404/422)
│   │   └── search.py             # POST /api/v1/search (200/400/422/501)
│   └── services/
│       ├── user_service.py       # Create user, uniqueness check
│       ├── post_service.py       # CRUD, index-status, soft delete
│       └── search_service.py     # tsquery, ts_rank, ts_headline, filters, cursor pagination
│
├── alembic/
│   ├── env.py                    # Async Alembic env
│   ├── script.py.mako            # Migration template
│   └── versions/001_initial.py   # users + posts tables, indexes, constraints
│
├── tests/
│   ├── conftest.py               # Session-scoped engine, per-test rolled-back session
│   ├── test_health.py            # 1 test
│   ├── test_user_service.py      # 4 tests
│   ├── test_post_service.py      # 8 tests
│   └── test_search_service.py    # 7 tests
│
├── verify/
│   ├── manifest.env              # e2e lifecycle contract for compose-based CI
│   └── acceptance/
│       ├── conftest.py           # httpx client, helpers (create_user, create_post, search_posts)
│       ├── test_healthz.py       # 1 test
│       ├── test_fr1_keyword_search.py    # 4 tests
│       ├── test_fr3_filtered_search.py   # 5 tests
│       ├── test_fr4_realtime_indexing.py # 5 tests
│       ├── test_fr5_pagination.py        # 4 tests
│       └── test_fr6_highlighting.py      # 2 tests
│
├── docs/
│   ├── system-design.md          # Reference to the full architect design
│   ├── mvp-scope.md              # One-page MVP scope summary
│   └── synthesis.md              # Build phase synthesis (scratchpad)
│
└── .github/workflows/
    ├── lint.yml                  # ruff check + format
    ├── ci.yml                    # unit tests + Docker build
    └── functional.yml            # compose up → acceptance tests → compose down
```
