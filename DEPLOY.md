# Deploy — Post Search MVP

Slug: `post-search`

## Prerequisites

- Docker Engine 24+ with Compose plugin (`docker compose version`)
- curl (for healthcheck probes)
- A running Docker daemon
- Port 8050 free on the host (overridable via `APP_PORT`)

## Quick Start — From Clean Checkout to Running

```bash
# 1. Clone / cd into the project
cd /path/to/post-search

# 2. Copy the env template (optional — built-in defaults work)
cp .env.example .env

# 3. Build and start the stack (app + postgres)
#    APP_PORT controls the host-side port; in-container port is always 8000.
APP_PORT=8050 docker compose up --build -d

# 4. Wait for startup (migrations run automatically in the container CMD)
sleep 10

# 5. Verify the stack is healthy
curl -sf http://localhost:8050/healthz
# → {"status":"ok"}

# 6. Quick functional smoke test — create a user and a post
curl -sf http://localhost:8050/api/v1/users \
  -H 'Content-Type: application/json' \
  -d '{"username": "smoke_test"}'
# → {"user_id":"...","username":"smoke_test"}

# Grab the user_id from the response and create a post:
curl -sf http://localhost:8050/api/v1/posts \
  -H 'Content-Type: application/json' \
  -d '{"author_id":"<user_id>","text":"hello world from post-search"}'
# → {"post_id":"...","text":"hello world from post-search",...}

# Search for it:
curl -sf -X POST http://localhost:8050/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"hello","mode":"lexical"}'
# → {"results":[...],"next_page_token":null}
```

Migrations run automatically on container startup (Alembic `upgrade head` in the
CMD before `uvicorn` starts).

## Port Configuration

| Variable   | Default | Description                                    |
|-----------|---------|------------------------------------------------|
| `APP_PORT` | `8050`  | Host-side port mapped to in-container `8000`   |

```bash
# Run on a different port
APP_PORT=9090 docker compose up -d
```

## Environment

The app is configured entirely through environment variables:

```bash
cp .env.example .env
# Edit .env to override defaults — the example has all variable names
```

The `docker-compose.yml`'s `environment:` block sets the critical values
(`DATABASE_URL`, `SECRET_KEY`). The `.env` file augments these with optional
settings.

Secrets (`SECRET_KEY`) belong in `.env` — never committed to the repo.

## Health Checks

Every service has a Docker HEALTHCHECK. Compose dependency waits ensure
the stack doesn't start serving before PostgreSQL is ready.

| Service  | Healthcheck command                                                 | Interval |
|----------|---------------------------------------------------------------------|----------|
| db       | `pg_isready -U postsearch`                                          | 5s       |
| app      | `python -c "import urllib.request; ..." http://localhost:8000/healthz` | 10s      |

To manually probe:

```bash
docker inspect --format='{{.State.Health.Status}}' post-search-db
docker inspect --format='{{.State.Health.Status}}' post-search-app
```

The health endpoint returns `{"status":"ok"}` when the app is reachable.

## Logs

```bash
# Follow app logs
docker compose logs -f app

# Tail recent logs
docker compose logs app --tail=100
docker compose logs db --tail=50
```

## Testing

```bash
# White-box unit tests (requires a running Postgres — use compose stack)
docker compose exec app python -m pytest tests/ -v
# → 21 passed

# Lint (ruff)
pip install ruff
ruff check src/ tests/ verify/
ruff format --check src/ tests/ verify/

# Black-box acceptance tests (requires running stack on APP_PORT)
API_BASE_URL="http://localhost:8050" python -m pytest verify/acceptance -v
# → 32 passed (or whatever the count is)
```

## CI/CD

Three GitHub Actions workflows live in `.github/workflows/`:

| Workflow         | Trigger             | What it does                                              |
|-----------------|---------------------|-----------------------------------------------------------|
| `lint.yml`      | PR + push to `main` | `ruff check` + `ruff format --check`                      |
| `ci.yml`        | PR + push to `main` | Install deps, run unit tests, build Docker image          |
| `functional.yml` | PR + push to `main` | `docker compose up`, run acceptance tests, `docker compose down` |

All three must pass before a PR can merge.

## Stop & Cleanup

```bash
# Stop containers (keeps volumes — Postgres data persists)
docker compose down

# Full teardown (wipes all data)
docker compose down --volumes --remove-orphans
```

## Production Notes

- Change `SECRET_KEY` to a strong random value (e.g. `openssl rand -hex 32`).
- Use a managed Postgres instance with automated backups.
- The GIN index on `fts_vector` is auto-maintained by Postgres; periodic
  `REINDEX` may improve query performance under heavy write load.
- Archived posts (soft-deleted) accumulate in the `posts` table; schedule a
  cleanup job if desired.
