# Deploy — Post Search MVP

## Prerequisites

- Docker and Docker Compose (with Compose V2 plugin)
- Port 8050 free on the host (overridable via `APP_PORT`)

## First Run

```bash
# Clone the repo and cd to it, then:
docker compose up -d --build

# Verify the app is healthy
curl http://localhost:8050/healthz
# → {"status":"ok"}

# Ensure the DB is ready
docker compose logs db --tail=5

# Run acceptance tests
API_BASE_URL="http://localhost:8050" python -m pytest verify/acceptance -q
```

Migrations run automatically on container startup (Alembic `upgrade head` in the CMD).

## Configuration

All configuration is environment-driven via `pydantic-settings`. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postsearch:postsearch@db:5432/postsearch` | Async SQLAlchemy connection string |
| `SECRET_KEY` | `change-me-in-production` | HMAC key for signed page tokens |
| `APP_PORT` | `8000` | In-container app port (mapped to host via `APP_PORT` env) |

For local development without Docker Compose, copy `.env.example` to `.env` and adjust `DATABASE_URL`:

```bash
cp .env.example .env
# Edit .env to point DATABASE_URL at your local Postgres
uv run uvicorn post_search.main:app --reload
```

## Teardown

```bash
docker compose down --volumes --remove-orphans
```

## Production Notes

- Change `SECRET_KEY` to a strong random value.
- Use a managed Postgres instance with automated backups.
- The GIN index on `fts_vector` is auto-maintained by Postgres; periodic `REINDEX` may improve query performance under heavy write load.
- Archived posts (soft-deleted) accumulate in the `posts` table; schedule a cleanup job if desired.
