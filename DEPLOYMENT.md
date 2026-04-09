# TalentFlow ATS — Deployment Guide

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Environment Variables](#environment-variables)
- [Local Development](#local-development)
- [Vercel Serverless Deployment](#vercel-serverless-deployment)
- [vercel.json Configuration](#verceljson-configuration)
- [Database Considerations for Serverless](#database-considerations-for-serverless)
- [Build Commands](#build-commands)
- [CI/CD Notes](#cicd-notes)
- [Troubleshooting](#troubleshooting)

---

## Overview

TalentFlow ATS is a FastAPI-based Applicant Tracking System designed to run as a serverless application on Vercel. This guide covers every step required to go from a local development setup to a production deployment.

---

## Prerequisites

- **Python 3.11+** installed locally
- **pip** or **uv** package manager
- **Git** for version control
- **Vercel CLI** (`npm i -g vercel`) for deployment
- A **Vercel account** (free tier is sufficient for testing)
- A **persistent database** for production (see [Database Considerations](#database-considerations-for-serverless))

---

## Environment Variables

Create a `.env` file in the project root for local development. For Vercel, configure these in the Vercel dashboard under **Settings → Environment Variables**.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | `sqlite+aiosqlite:///./talentflow.db` | Database connection string. Use PostgreSQL for production. |
| `SECRET_KEY` | Yes | *(none)* | Secret key for JWT signing. Generate with `openssl rand -hex 32`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | JWT access token lifetime in minutes. |
| `ENVIRONMENT` | No | `development` | Set to `production` for deployed environments. |
| `CORS_ORIGINS` | No | `*` | Comma-separated list of allowed CORS origins. Restrict in production. |
| `LOG_LEVEL` | No | `info` | Logging level: `debug`, `info`, `warning`, `error`, `critical`. |

### Example `.env` (local development)

```env
DATABASE_URL=sqlite+aiosqlite:///./talentflow.db
SECRET_KEY=a]3f9c7e2b1d4a8f0e6c5b3d7a9f1e2c4b6d8a0f3e5c7b9d1a4f6e8c0b2d5a7
ACCESS_TOKEN_EXPIRE_MINUTES=60
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
LOG_LEVEL=debug
```

### Example environment variables (production on Vercel)

```env
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/talentflow
SECRET_KEY=<generate-a-strong-random-hex-string>
ACCESS_TOKEN_EXPIRE_MINUTES=30
ENVIRONMENT=production
CORS_ORIGINS=https://your-domain.vercel.app,https://your-custom-domain.com
LOG_LEVEL=warning
```

> **Security note:** Never commit `.env` files to version control. The `.gitignore` file should include `.env`.

---

## Local Development

### 1. Clone the repository

```bash
git clone https://github.com/your-org/talentflow-ats.git
cd talentflow-ats
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

```bash
cp .env.example .env
# Edit .env with your local values
```

### 5. Run the development server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`. Interactive docs are at `http://localhost:8000/docs`.

### 6. Run tests

```bash
pytest -v
```

---

## Vercel Serverless Deployment

### Step 1: Install the Vercel CLI

```bash
npm install -g vercel
```

### Step 2: Log in to Vercel

```bash
vercel login
```

### Step 3: Link the project

From the project root directory:

```bash
vercel link
```

Follow the prompts to link to an existing Vercel project or create a new one.

### Step 4: Configure environment variables on Vercel

Using the CLI:

```bash
vercel env add DATABASE_URL production
vercel env add SECRET_KEY production
vercel env add ENVIRONMENT production
vercel env add CORS_ORIGINS production
```

Or configure them in the Vercel dashboard: **Project → Settings → Environment Variables**.

### Step 5: Deploy

Preview deployment:

```bash
vercel
```

Production deployment:

```bash
vercel --prod
```

### Step 6: Verify

After deployment, visit the provided URL. Check the health endpoint:

```bash
curl https://your-project.vercel.app/api/health
```

---

## vercel.json Configuration

Place this file in the project root:

```json
{
  "version": 2,
  "builds": [
    {
      "src": "app/main.py",
      "use": "@vercel/python",
      "config": {
        "maxLambdaSize": "50mb",
        "runtime": "python3.11"
      }
    }
  ],
  "routes": [
    {
      "src": "/static/(.*)",
      "dest": "/app/static/$1"
    },
    {
      "src": "/(.*)",
      "dest": "app/main.py"
    }
  ],
  "env": {
    "ENVIRONMENT": "production"
  },
  "regions": ["iad1"]
}
```

### Configuration breakdown

| Key | Purpose |
|---|---|
| `builds[].src` | Entry point for the Python serverless function. |
| `builds[].use` | Vercel builder for Python projects. |
| `builds[].config.maxLambdaSize` | Maximum bundle size. Increase if dependencies are large. |
| `builds[].config.runtime` | Python version. Must match your local development version. |
| `routes` | URL rewriting rules. All non-static requests route to the FastAPI app. |
| `regions` | Deployment region. Choose the region closest to your database. |

### Important notes on vercel.json

- The `@vercel/python` builder expects a WSGI/ASGI `app` object exported from the entry point file. FastAPI's `app` object in `app/main.py` satisfies this requirement.
- Static files (CSS, JS, images) should be served from a `/static/` directory and routed separately to avoid hitting the serverless function for every asset request.
- The `maxLambdaSize` may need to be increased if you add heavy dependencies (e.g., ML libraries for resume parsing).

---

## Database Considerations for Serverless

### SQLite Limitations on Vercel

**SQLite is NOT suitable for production on Vercel.** Here is why:

1. **Ephemeral filesystem:** Vercel serverless functions run on read-only filesystems. SQLite requires write access to the filesystem for its database file and WAL (Write-Ahead Logging) journal. Writes will fail silently or raise errors.

2. **No shared state:** Each serverless function invocation may run on a different container. There is no shared filesystem between invocations, so data written by one request is invisible to the next.

3. **Cold starts:** Each cold start creates a fresh container with no persisted SQLite data.

4. **Concurrent access:** SQLite uses file-level locking. Concurrent serverless invocations cannot safely coordinate locks across containers.

### SQLite is acceptable for

- Local development
- Running tests in CI/CD
- Single-instance non-serverless deployments (e.g., a VM or Docker container)

### Recommended production databases

| Database | Connection String Format | Notes |
|---|---|---|
| **PostgreSQL (recommended)** | `postgresql+asyncpg://user:pass@host:5432/dbname` | Best choice for production. Use Neon, Supabase, or Vercel Postgres. |
| **PostgreSQL via Neon** | `postgresql+asyncpg://user:pass@ep-xxx.us-east-2.aws.neon.tech/dbname?sslmode=require` | Serverless-friendly with connection pooling. |
| **PostgreSQL via Supabase** | `postgresql+asyncpg://postgres:pass@db.xxx.supabase.co:5432/postgres` | Free tier available. Use the connection pooler URL for serverless. |
| **Vercel Postgres** | Provided via `POSTGRES_URL` env var | Native Vercel integration. Requires the `@vercel/postgres` package or direct asyncpg connection. |

### Migration from SQLite to PostgreSQL

1. Update `DATABASE_URL` in your environment variables to point to PostgreSQL.
2. Install the async PostgreSQL driver:

   ```bash
   pip install asyncpg
   ```

3. Ensure `asyncpg` is listed in `requirements.txt`.
4. Run database migrations (if using Alembic):

   ```bash
   alembic upgrade head
   ```

5. The SQLAlchemy models and async session configuration in `app/core/database.py` work with both SQLite (via `aiosqlite`) and PostgreSQL (via `asyncpg`) without code changes — only the connection string differs.

### Connection pooling for serverless

Serverless functions create and destroy database connections frequently. Configure connection pooling to avoid exhausting database connections:

```python
# In app/core/database.py — these settings are important for serverless
engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,           # Keep pool small for serverless
    max_overflow=10,       # Allow burst connections
    pool_timeout=30,       # Seconds to wait for a connection
    pool_recycle=300,      # Recycle connections every 5 minutes
    pool_pre_ping=True,    # Verify connections before use
)
```

> **Note:** `pool_size` and `max_overflow` are not supported by `aiosqlite`. These settings are only applied when using PostgreSQL with `asyncpg`.

---

## Build Commands

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run the application

```bash
# Development (with auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production (single worker, suitable for containers)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1

# Production (multiple workers, for VM deployments)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Run tests

```bash
# Run all tests
pytest -v

# Run with coverage
pytest --cov=app --cov-report=term-missing -v

# Run a specific test file
pytest tests/test_auth.py -v

# Run tests matching a pattern
pytest -k "test_login" -v
```

### Linting and formatting (if configured)

```bash
# Type checking
mypy app/

# Linting
ruff check app/

# Formatting
ruff format app/
```

### Database migrations (if using Alembic)

```bash
# Generate a new migration
alembic revision --autogenerate -m "description of changes"

# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

---

## CI/CD Notes

### GitHub Actions (recommended)

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Cache pip dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run tests
        env:
          DATABASE_URL: sqlite+aiosqlite:///./test.db
          SECRET_KEY: test-secret-key-for-ci-only
          ENVIRONMENT: testing
        run: |
          pytest -v --tb=short

      - name: Check code quality
        run: |
          pip install ruff mypy
          ruff check app/
          ruff format --check app/

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          vercel-args: "--prod"
```

### Required GitHub Secrets for CI/CD

| Secret | How to obtain |
|---|---|
| `VERCEL_TOKEN` | Vercel dashboard → Settings → Tokens → Create |
| `VERCEL_ORG_ID` | Run `vercel link` locally, check `.vercel/project.json` |
| `VERCEL_PROJECT_ID` | Run `vercel link` locally, check `.vercel/project.json` |

### Branch strategy

| Branch | Purpose | Deployment |
|---|---|---|
| `main` | Production-ready code | Auto-deploys to production on Vercel |
| `develop` | Integration branch | Preview deployments on Vercel |
| `feature/*` | Feature branches | Preview deployments on pull requests |

### Pre-deployment checklist

- [ ] All tests pass locally (`pytest -v`)
- [ ] No linting errors (`ruff check app/`)
- [ ] Environment variables are configured on Vercel
- [ ] `DATABASE_URL` points to a persistent database (not SQLite) for production
- [ ] `SECRET_KEY` is a strong, unique random value (not the development default)
- [ ] `CORS_ORIGINS` is restricted to your actual frontend domains
- [ ] `ENVIRONMENT` is set to `production`

---

## Troubleshooting

### Common deployment issues

**1. `ModuleNotFoundError` on Vercel**

Ensure all dependencies are listed in `requirements.txt`. Vercel installs packages from this file during the build step. Run `pip freeze > requirements.txt` if unsure, but prefer maintaining a curated list.

**2. `500 Internal Server Error` with no logs**

Check Vercel function logs: **Project → Deployments → (select deployment) → Functions → (select function) → Logs**. Common causes:
- Missing environment variables
- Database connection failures
- Import errors from missing packages

**3. Database connection timeouts**

For serverless deployments, ensure your database accepts connections from Vercel's IP ranges. Most managed databases (Neon, Supabase, Vercel Postgres) handle this automatically. If using a self-hosted database, whitelist `0.0.0.0/0` or use Vercel's IP allowlist.

**4. `RuntimeError: no running event loop` or `MissingGreenlet`**

This indicates synchronous database access in an async context. Ensure:
- All SQLAlchemy queries use `async_session` with `await`
- All relationships use `lazy="selectin"` (not the default `lazy="select"`)
- ChromaDB calls (if any) are wrapped with `run_in_threadpool()`

**5. Cold start latency**

Vercel serverless functions have cold start times of 1-3 seconds for Python. To mitigate:
- Keep `requirements.txt` minimal — remove unused packages
- Use `maxLambdaSize` wisely — smaller bundles start faster
- Consider Vercel's Edge Functions for latency-critical endpoints (requires adaptation)

**6. `413 Request Entity Too Large`**

Vercel has a 4.5 MB request body limit for serverless functions. For file uploads (e.g., resumes), consider:
- Uploading directly to a storage service (S3, Vercel Blob) from the client
- Using presigned URLs to bypass the serverless function for large payloads

**7. SQLite errors in production**

If you see `sqlite3.OperationalError: attempt to write a readonly database` or similar, you are using SQLite on Vercel's read-only filesystem. Switch to PostgreSQL as described in [Database Considerations](#database-considerations-for-serverless).

---

## Architecture Notes for Serverless

```
Client Request
      │
      ▼
┌─────────────┐
│   Vercel     │
│   Edge       │
│   Network    │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│   Vercel     │────▶│  PostgreSQL   │
│   Serverless │     │  (Neon /      │
│   Function   │     │   Supabase)   │
│  (FastAPI)   │     └──────────────┘
└─────────────┘
```

Each incoming request is handled by a serverless function running the FastAPI application. The function connects to an external PostgreSQL database for persistent storage. Static assets are served directly from Vercel's edge network without invoking the function.