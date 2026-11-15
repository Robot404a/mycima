# Notification service

Sends the emails for reservation events (booking confirmed, booking cancelled) and keeps a
log of every email in its own PostgreSQL database, so you can see what was sent, what failed,
and retry the failures.

Paths below are **without** the gateway's `/api` prefix (the gateway strips it).

## How it works

```
reservation-service ──POST /notifications──▶ notification-service ──SMTP──▶ Mailpit (dev) / real mail server
   (X-Internal-Token)                              │
                                                   └──▶ notification-db (table `notifications`)
```

1. When a booking is confirmed or cancelled, reservation-service calls `POST /notifications`
   with the user's email and the booking details (see `notification_client.py` there).
2. This service renders the email, **stores it**, then tries to send it over SMTP.
3. If SMTP fails, the row is saved as `failed` and a background loop retries it later.
4. The caller always gets `201`, so a mail outage never breaks a booking.

## Endpoints

| Method | Path | Who can call it | Purpose |
|---|---|---|---|
| `GET` | `/health` | anyone | Service + database status (`503` if the DB is down or the schema is pending) |
| `POST` | `/notifications` | **other services only** (`X-Internal-Token` header) | Create and send a notification |
| `GET` | `/notifications` | logged-in user | My notification history (`status`, `limit`, `offset` filters) |
| `GET` | `/notifications/{id}` | logged-in user | One of my notifications (`404` if it belongs to someone else) |
| `GET` | `/admin/notifications` | admin | All notifications (`status`, `user_id`, `limit`, `offset` filters) |
| `POST` | `/admin/notifications/{id}/retry` | admin | Force another attempt for a `failed` notification |

`POST /notifications` is never exposed through the gateway: it is only called service to service,
and is protected by a shared secret (`INTERNAL_API_KEY`).

### Request body (`POST /notifications`)

```json
{
  "user_id": 1,
  "recipient_email": "user@example.com",
  "type": "reservation_created",
  "reference_id": "booking-id",
  "data": {
    "movie_title": "Inception",
    "showtime": "Saturday 20 December 2026, 20:30",
    "seats": ["A1", "A2"],
    "total_price": "16.00"
  }
}
```

- `type`: `reservation_created` or `reservation_cancelled`.
- `data` only fills the email template; missing fields show as `-`. The rendered subject and
  body are what get stored.

### Notification status

| Status | Meaning |
|---|---|
| `pending` | Being sent right now (or stuck, in which case the retry loop picks it up) |
| `sent` | Delivered to the SMTP server |
| `failed` | SMTP error; see the `error` column. Will be retried automatically |

## Design decisions

- **Idempotent.** A unique index on `(type, reference_id)` means the same event sent twice
  creates one row and one email. The second call returns the existing row.
- **Retries.** Every `RETRY_INTERVAL_SECONDS` a background loop re-sends `failed` rows whose last
  attempt is older than `RETRY_DELAY_SECONDS`, up to `MAX_SEND_ATTEMPTS` attempts. Rows are claimed
  with `FOR UPDATE SKIP LOCKED`, so several replicas never send the same row twice. An admin retry
  ignores the attempts limit.
- **No DB connection is held while talking to SMTP.**
- **Own database.** This service has its own Postgres; the schema is created on startup from
  `db/schema.sql` (safe to run repeatedly and from several replicas).

## Database

One table, `notifications`:

| Column | Notes |
|---|---|
| `id` | `BIGSERIAL` primary key |
| `user_id` | `BIGINT` |
| `recipient_email`, `subject`, `body` | what was (or will be) sent |
| `type` | `reservation_created` / `reservation_cancelled` |
| `reference_id` | the booking id; unique together with `type` |
| `status`, `attempts`, `last_attempt_at`, `error` | delivery tracking |
| `created_at`, `sent_at` | timestamps |

## Configuration

All settings are environment variables with local-dev defaults (see `config.py`).

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql://notification:notification_dev@localhost:5434/notification` | Postgres connection |
| `DB_POOL_MIN` / `DB_POOL_MAX` | `2` / `10` | Connection pool size |
| `SMTP_HOST` / `SMTP_PORT` | `localhost` / `1025` | Mail server (Mailpit in dev) |
| `SMTP_USER` / `SMTP_PASSWORD` | empty | SMTP login (leave empty for Mailpit) |
| `SMTP_USE_TLS` | `false` | Use STARTTLS |
| `EMAIL_FROM` | `no-reply@mycima.local` | Sender address |
| `MAX_SEND_ATTEMPTS` | `3` | Automatic attempts before giving up |
| `RETRY_INTERVAL_SECONDS` | `30` | How often the retry loop runs |
| `RETRY_DELAY_SECONDS` | `60` | Minimum wait between two attempts of the same email |
| `INTERNAL_API_KEY` | `dev-internal-key-change-me` | Shared secret for service-to-service calls. **Must be the same value in reservation-service** |
| `JWT_SECRET` / `JWT_ALGORITHM` | dev secret / `HS256` | Only for the local auth fallback; must match the User service |

Change `INTERNAL_API_KEY` and `JWT_SECRET` outside development.

## Run it

### Standalone dev setup (database + Mailpit, optionally the service)

```bash
cd notification-service
docker compose -f docker-compose.dev.yml up -d                    # database + Mailpit only
docker compose -f docker-compose.dev.yml --profile app up -d --build   # + the service
```

| What | Where |
|---|---|
| Service | http://localhost:8004 (`/docs` for Swagger) |
| Caught emails (Mailpit) | http://localhost:8025 |
| Postgres | `localhost:5434` (database `notification`, user `notification`, password `notification_dev`) |

### With the whole system

The root `docker-compose.yml` defines `notification-db`, `mailpit` and `notification-service`
(service on port `8004`, Mailpit UI on `8025`). Inside the Docker network the service is reached at
`http://notification-service:8000`. Do not run it at the same time as the standalone dev setup:
they use the same ports.

## Connecting reservation-service

Set these on reservation-service (defaults in its `config.py`):

| Variable | Value |
|---|---|
| `NOTIFICATION_ENABLED` | `true` (it is `false` by default, so local runs and tests never need this service) |
| `NOTIFICATION_SERVICE_URL` | `http://notification-service:8000` inside the compose network, or `http://host.docker.internal:8004` when the two dev setups run separately |
| `INTERNAL_API_KEY` | same value as this service |

Cancellations made by an **admin** do not send an email: the token then holds the admin's address,
not the customer's.

## Tests

17 tests: email template and SMTP error handling, the internal-key guard, idempotency, per-user
privacy, admin endpoints, manual and automatic retries. They use a separate `notification_test`
database in the same Postgres container (wiped on every run) and a fake mail sender, so no real
email is sent.

Start the database, then run the tests in a throwaway container (PowerShell, from `notification-service/`):

```powershell
docker compose -f docker-compose.dev.yml up -d

docker run --rm `
  --add-host=host.docker.internal:host-gateway `
  -v "${PWD}:/app" -v "${PWD}/../shared:/shared" -w /app `
  -e TEST_DATABASE_URL="postgresql://notification:notification_dev@host.docker.internal:5434/notification_test" `
  python:3.12-slim `
  sh -c "pip install -q -r requirements.txt -r requirements-dev.txt && pytest -v"
```

Running `pytest -v` directly in a virtual environment also works, as long as Postgres is up on port 5434.
(On Windows machines where an application-control policy blocks the `psycopg` binary DLL, use the
Docker command above.)

## Files

```
notification-service/
├── db/schema.sql            table + indexes, applied on startup
├── tests/                   conftest.py, test_api.py, test_email_sender.py
├── auth.py                  JWT helpers + internal_only (service-to-service key check)
├── config.py                environment settings
├── db.py                    connection pool + schema bootstrap
├── email_sender.py          email templates + SMTP sending
├── logging_setup.py         structured logging + request log middleware
├── main.py                  FastAPI app and endpoints
├── schemas.py               request / response models
├── service.py               create, send, retry logic
├── Dockerfile               build from the repo root: docker build -f notification-service/Dockerfile .
├── docker-compose.dev.yml   standalone dev setup (database + Mailpit + service)
├── pytest.ini
├── requirements.txt
└── requirements-dev.txt
```

## Limitations

- The call from reservation-service is synchronous (3 s timeout), so a slow notification service
  delays the booking response slightly.
- Only plain-text emails and two notification types for now; add a template to `_TEMPLATES` in
  `email_sender.py` (and the type to the `CHECK` constraint in `db/schema.sql` and `schemas.py`) to
  add more.