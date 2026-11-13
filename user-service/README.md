# User Service

Accounts, authentication and JWT issuing for MyCima. It owns the `users_db`
database: no other service reads its tables.

## Responsibilities

- Register and authenticate users (passwords hashed with bcrypt).
- Issue signed JWTs consumed by the gateway and the other services.
- Expose the authenticated user's profile.
- Give administrators a minimal user-management API.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | - | Liveness + database check |
| `POST` | `/auth/register` | - | Create an account, returns a JWT |
| `POST` | `/auth/login` | - | Log in, returns a JWT |
| `GET` | `/users/me` | Bearer | Current user profile |
| `PATCH` | `/users/me` | Bearer | Update full name and/or password |
| `GET` | `/admin/users` | Admin | Paginated list, optional `q` search |
| `GET` | `/admin/users/{id}` | Admin | One user |
| `PATCH` | `/admin/users/{id}/role` | Admin | Promote/demote (`user` or `admin`) |

The gateway strips the `/api` prefix, so `GET /api/users/me` through the gateway
reaches `GET /users/me` here. Swagger UI is available at `/docs`.

### Example

```bash
curl -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"ada@mycima.com","password":"secretpass1","full_name":"Ada"}'
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./users.db` | PostgreSQL in Docker; SQLite for local tests |
| `JWT_SECRET` | `mycima-dev-secret-change-me-in-production` | **Must match the gateway and every service** |
| `JWT_ALGORITHM` | `HS256` | Signing algorithm |
| `JWT_EXPIRE_MINUTES` | `120` | Token lifetime |
| `ADMIN_EMAIL` | - | Optional demo admin, created at startup if missing |
| `ADMIN_PASSWORD` | - | Password for the seeded admin (min. 8 characters) |
| `ADMIN_FULL_NAME` | `MyCima Admin` | Display name of the seeded admin |
| `LOG_LEVEL` | `INFO` | Log verbosity |

Password hashing uses `bcrypt` directly (bcrypt caps passwords at 72 bytes,
which the API validates). JWTs are signed with `PyJWT`, the same library the
gateway already declares.

## Run with Docker (recommended)

From the repository root:

```bash
docker compose up --build postgres user-service
```

The service listens on <http://localhost:8001> (Swagger at `/docs`).

## Run locally

```bash
# from the repository root, with a venv activated
pip install -r user-service/requirements-dev.txt
$env:PYTHONPATH = "."                       # PowerShell
python -m uvicorn main:app --app-dir user-service --reload --port 8001
```

Without `DATABASE_URL` the service uses a local SQLite file, which is enough to
try the API.

## Tests

```bash
cd user-service
pytest
```

The tests run against a temporary SQLite database and cover registration,
duplicate emails, login, expired tokens, profile updates and admin access
control.

## Layout

```
user-service/
├── main.py            FastAPI app, lifespan, /health
├── config.py          Environment settings
├── database.py        Engine, session factory, Base
├── models.py          User model
├── schemas.py         Pydantic requests/responses
├── dependencies.py    Bearer auth + admin guard
├── security.py        Token response builder
├── routers/           auth, users, admin
├── tests/             pytest suite
├── Dockerfile
└── requirements.txt
```

`shared/auth.py` (repository root) holds the token and password logic shared
with the gateway, so both sides always agree on the token format.
