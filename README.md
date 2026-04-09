# TalentFlow ATS

**Applicant Tracking System** — A modern, full-featured recruitment management platform built with Python 3.11+ and FastAPI.

## Features

- **Job Management** — Create, publish, and manage job postings with detailed descriptions, requirements, and metadata
- **Candidate Tracking** — Track candidates through customizable hiring pipelines from application to offer
- **Application Processing** — Receive, review, and manage job applications with resume parsing and status tracking
- **Interview Scheduling** — Schedule and coordinate interviews with calendar integration and automated notifications
- **Interview Feedback** — Collect structured feedback from interviewers with scoring rubrics and recommendations
- **Team Collaboration** — Role-based access for recruiters, hiring managers, and interviewers
- **Audit Logging** — Full audit trail of all system actions for compliance and accountability
- **Dashboard & Analytics** — Real-time metrics on pipeline health, time-to-hire, and recruiter performance
- **Authentication & Authorization** — JWT-based auth with role-based permissions (Admin, Recruiter, Hiring Manager, Interviewer, Candidate)

## Tech Stack

| Layer | Technology |
|---|---|
| **Runtime** | Python 3.11+ |
| **Framework** | FastAPI |
| **Database** | SQLite (via aiosqlite) / PostgreSQL (via asyncpg) |
| **ORM** | SQLAlchemy 2.0 (async) |
| **Schemas** | Pydantic v2 |
| **Auth** | JWT (python-jose) + bcrypt |
| **Templates** | Jinja2 + Tailwind CSS |
| **Testing** | pytest + pytest-asyncio + httpx |
| **Server** | Uvicorn |

## Project Structure

```
talentflow-ats/
├── app/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          # Pydantic Settings configuration
│   │   ├── database.py        # Async SQLAlchemy engine & session
│   │   └── security.py        # JWT token creation/verification, password hashing
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py            # User model (all roles)
│   │   ├── job.py             # Job posting model
│   │   ├── candidate.py       # Candidate profile model
│   │   ├── application.py     # Job application model
│   │   ├── interview.py       # Interview scheduling & feedback models
│   │   └── audit_log.py       # Audit log model
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py            # User request/response schemas
│   │   ├── job.py             # Job request/response schemas
│   │   ├── candidate.py       # Candidate request/response schemas
│   │   ├── application.py     # Application request/response schemas
│   │   ├── interview.py       # Interview request/response schemas
│   │   └── audit_log.py       # Audit log response schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── user.py            # User CRUD & business logic
│   │   ├── job.py             # Job CRUD & publishing logic
│   │   ├── candidate.py       # Candidate management logic
│   │   ├── application.py     # Application processing logic
│   │   ├── interview.py       # Interview scheduling logic
│   │   └── audit_log.py       # Audit logging service
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py            # Login, register, token refresh
│   │   ├── users.py           # User management endpoints
│   │   ├── jobs.py            # Job posting endpoints
│   │   ├── candidates.py      # Candidate endpoints
│   │   ├── applications.py    # Application endpoints
│   │   ├── interviews.py      # Interview endpoints
│   │   └── dashboard.py       # Dashboard & analytics endpoints
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── auth.py            # Authentication dependencies
│   ├── templates/
│   │   ├── base.html          # Base layout with Tailwind CSS
│   │   ├── dashboard.html     # Dashboard view
│   │   ├── auth/
│   │   ├── jobs/
│   │   ├── candidates/
│   │   ├── applications/
│   │   └── interviews/
│   └── main.py                # FastAPI app entry point
├── tests/
│   ├── conftest.py            # Shared fixtures (async client, test DB)
│   ├── test_auth.py           # Authentication tests
│   ├── test_users.py          # User management tests
│   ├── test_jobs.py           # Job posting tests
│   ├── test_candidates.py     # Candidate tests
│   ├── test_applications.py   # Application tests
│   └── test_interviews.py     # Interview tests
├── .env                       # Environment variables (not committed)
├── .env.example               # Example environment variables
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## Setup Instructions

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Git

### 1. Clone the Repository

```bash
git clone <repository-url>
cd talentflow-ats
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example environment file and update values:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Application
APP_NAME=TalentFlow ATS
DEBUG=true

# Database
DATABASE_URL=sqlite+aiosqlite:///./talentflow.db

# Security
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]
```

For PostgreSQL (production):

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/talentflow
```

### 5. Run Database Migrations

The application automatically creates database tables on startup. To initialize the database manually:

```bash
python -c "
import asyncio
from app.core.database import engine, Base
from app.models import *

async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Database tables created.')

asyncio.run(init())
"
```

### 6. Start the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at:

- **Web UI**: [http://localhost:8000](http://localhost:8000)
- **API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Docs (ReDoc)**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Usage Guide by Role

### Admin

- Manage all users (create, update, deactivate accounts)
- Configure system settings
- View audit logs and system-wide analytics
- Full access to all features

### Recruiter

- Create and publish job postings
- Review incoming applications
- Schedule interviews and assign interviewers
- Move candidates through pipeline stages
- Generate hiring reports

### Hiring Manager

- View job postings for their department
- Review candidate profiles and applications
- Provide interview feedback and hiring decisions
- Approve/reject candidates at final stages

### Interviewer

- View assigned interview schedules
- Submit structured interview feedback with scores
- View candidate profiles for upcoming interviews

### Candidate

- Browse published job openings
- Submit applications with resume upload
- Track application status
- View interview schedules

## API Routes Summary

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register` | Register a new user |
| `POST` | `/api/auth/login` | Login and receive JWT token |
| `POST` | `/api/auth/refresh` | Refresh access token |
| `GET` | `/api/auth/me` | Get current user profile |

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/users` | List all users (Admin) |
| `GET` | `/api/users/{id}` | Get user by ID |
| `PUT` | `/api/users/{id}` | Update user |
| `DELETE` | `/api/users/{id}` | Deactivate user (Admin) |

### Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/jobs` | List job postings |
| `POST` | `/api/jobs` | Create a job posting |
| `GET` | `/api/jobs/{id}` | Get job details |
| `PUT` | `/api/jobs/{id}` | Update job posting |
| `DELETE` | `/api/jobs/{id}` | Delete job posting |
| `POST` | `/api/jobs/{id}/publish` | Publish a job posting |
| `POST` | `/api/jobs/{id}/close` | Close a job posting |

### Candidates

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/candidates` | List candidates |
| `POST` | `/api/candidates` | Create candidate profile |
| `GET` | `/api/candidates/{id}` | Get candidate details |
| `PUT` | `/api/candidates/{id}` | Update candidate profile |
| `DELETE` | `/api/candidates/{id}` | Delete candidate |

### Applications

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/applications` | List applications |
| `POST` | `/api/applications` | Submit an application |
| `GET` | `/api/applications/{id}` | Get application details |
| `PUT` | `/api/applications/{id}` | Update application |
| `PUT` | `/api/applications/{id}/status` | Update application status |
| `DELETE` | `/api/applications/{id}` | Withdraw application |

### Interviews

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/interviews` | List interviews |
| `POST` | `/api/interviews` | Schedule an interview |
| `GET` | `/api/interviews/{id}` | Get interview details |
| `PUT` | `/api/interviews/{id}` | Update interview |
| `DELETE` | `/api/interviews/{id}` | Cancel interview |
| `POST` | `/api/interviews/{id}/feedback` | Submit interview feedback |

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/dashboard/stats` | Get dashboard statistics |
| `GET` | `/api/dashboard/pipeline` | Get pipeline overview |

## Testing

### Run All Tests

```bash
pytest
```

### Run Tests with Verbose Output

```bash
pytest -v
```

### Run Specific Test File

```bash
pytest tests/test_auth.py -v
```

### Run Tests with Coverage

```bash
pip install pytest-cov
pytest --cov=app --cov-report=term-missing
```

### Run Async Tests Only

```bash
pytest -m asyncio -v
```

## Deployment Notes

### Production Checklist

1. **Environment Variables**
   - Set `DEBUG=false`
   - Generate a strong `SECRET_KEY` (use `openssl rand -hex 32`)
   - Configure `DATABASE_URL` for PostgreSQL
   - Set `CORS_ORIGINS` to your frontend domain(s)

2. **Database**
   - Use PostgreSQL with `asyncpg` driver for production
   - Run migrations before deploying
   - Set up regular database backups

3. **Server**
   - Use Gunicorn with Uvicorn workers:
     ```bash
     gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
     ```
   - Configure a reverse proxy (Nginx/Caddy) for TLS termination

4. **Docker** (optional)
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY . .
   EXPOSE 8000
   CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
   ```

5. **Security**
   - Enable HTTPS in production
   - Set secure cookie flags
   - Rate limit authentication endpoints
   - Keep dependencies updated

## License

**Private** — All rights reserved. This software is proprietary and confidential. Unauthorized copying, distribution, or modification is strictly prohibited.