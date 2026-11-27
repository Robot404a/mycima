# 🎬 MyCima — AI-Powered Distributed Cinema Reservation Platform

**Intelligent Cinema. Connected Services.**

MyCima is a cinema booking platform built on a **distributed microservices architecture**.
Users can browse the catalogue, pick a showtime, choose seats on an interactive seat map and
pay for a reservation — either through the classic web interface or through an **LLM assistant**
that searches the catalogue, suggests seats and holds them in natural language.

The project demonstrates core distributed-systems concerns: independent services, inter-service
communication over REST and gRPC, database-per-service ownership, concurrency control,
idempotency, fault tolerance and containerised deployment.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

---

## Table of contents

- [Architecture](#architecture)
- [Services](#services)
- [Technology stack](#technology-stack)
- [Design decisions](#design-decisions)
- [Quick start](#quick-start)
- [Demo accounts](#demo-accounts)
- [End-to-end walkthrough](#end-to-end-walkthrough)
- [API overview](#api-overview)
- [AI assistant](#ai-assistant)
- [Payment service and gRPC](#payment-service-and-grpc)
- [Testing](#testing)
- [Configuration reference](#configuration-reference)
- [Troubleshooting](#troubleshooting)
- [Project structure](#project-structure)
- [Current limitations](#current-limitations)
- [Team](#team)

---

## Architecture

```
                              Browser
                                 │  HTTP :3000
                        ┌────────▼─────────┐
                        │    Frontend      │  React 18 + Vite, served by nginx
                        │     (nginx)      │  proxies /api and /media
                        └────────┬─────────┘
                                 │  /api/**
                        ┌────────▼─────────┐
                        │     Gateway      │  :8000 — JWT validation, routing,
                        │     FastAPI      │  auth rate limiting, timeouts,
                        └──┬───┬───┬───┬───┘  502/503/504, health fan-out
          ┌────────────────┘   │   │   └─────────────────┐
          │                    │   │                     │
   ┌──────▼─────┐   ┌──────────▼─┐ ┌▼──────────────┐ ┌───▼────────────┐
   │    User    │   │   Movie    │ │  Reservation  │ │    Payment     │
   │   :8001    │   │   :8003    │ │    :8004      │ │ :8006 / :50052 │
   └──────┬─────┘   └─────┬──────┘ └─┬─────────┬───┘ └───────┬────────┘
          │               │          │         │             │
      users_db       movies_db  reservation_db │        payment_db
                                               │ HTTP (booking events)
                                        ┌──────▼───────┐
                                        │ Notification │
                                        │    :8007     │
                                        └──┬────────┬──┘
                                           │        │ SMTP
                                   notification_db  Mailpit :8025

   AI Assistant :8005 ── tools ──▶ Gateway (with the guest's JWT) ──▶ Movie / Reservation
          │
          └── HTTPS ──▶ external LLM provider (OpenAI-compatible)
```

**Request path.** The browser only ever talks to nginx, which forwards `/api/**` to the gateway.
The gateway authenticates the JWT, strips `/api`, picks the target service and forwards the
request (identity included). In normal use the browser only talks to nginx, which only talks to
the gateway; the other services' ports are published on the host for debugging and Swagger UI,
and can be removed for a production deployment.

**Internal calls.**

- Reservation → Movie: showtime, hall layout and price.
- Reservation → Notification: booking emails (internal token).
- Payment → Reservation: hold lookup and confirmation.
- AI Assistant → Gateway → Movie / Reservation: all tools run with the guest's own JWT, so the
  assistant can never act with more rights than the signed-in user.

---

## Services

| Service | Responsibility | Stack | Port (host) | Database | Documentation |
|---|---|---|---|---|---|
| **frontend** | Catalogue, showtimes, 2D/3D seat map, checkout, bookings, admin back-office, assistant widget | React 18, Vite, React Router, three.js, nginx | 3000 | — | — |
| **gateway** | Single entry point, JWT validation, routing, auth rate limiting, timeouts, upstream health | FastAPI, httpx | 8000 | — | `/docs` |
| **user-service** | Registration, login, profiles, roles, demo admin seeding | FastAPI, SQLAlchemy, bcrypt, PyJWT | 8001 | `users_db` | [README](user-service/README.md) |
| **movie-service** | Movies, cinemas, halls, seat layouts, showtimes, posters, seeding | FastAPI, SQLAlchemy | 8003 | `movies_db` | [README](movie-service/README.md) |
| **reservation-service** | Seat availability, temporary holds, bookings, cancellation, admin stats | FastAPI, psycopg 3, plain SQL | 8004 | `reservation_db` | [README](reservation-service/README.md) |
| **payment-service** | Simulated payments, idempotency, refunds, stats — REST **and** gRPC | FastAPI, SQLAlchemy, grpcio | 8006 / 50052 | `payment_db` | [README](payment-service/README.md) |
| **notification-service** | Booking emails, delivery log, background retry, Mailpit integration | FastAPI, psycopg 3 | 8007 | `notification_db` | [README](notification-service/README.md) |
| **ai-assistant-service** | Conversational booking: LLM agent, tools, topic guard, deterministic fallback | FastAPI, SQLAlchemy, OpenAI-compatible API | 8005 | `ai_assistant_db` | [README](ai-assistant-service/README.md) |
| **postgres** | One PostgreSQL instance, one database and one role per service | PostgreSQL 16 | 5432 | 6 databases | — |
| **mailpit** | Local SMTP catcher with a web inbox | Mailpit | 1025 / 8025 | — | — |

---

## Technology stack

| Layer | Choice |
|---|---|
| Backend services | Python 3.12, FastAPI, Uvicorn |
| Data access | SQLAlchemy 2 (user, movie, payment, AI) and psycopg 3 with plain SQL (reservation, notification) |
| Database | PostgreSQL 16 — **one database per service**, no cross-database foreign keys |
| Synchronous communication | REST/JSON through the gateway, plus **gRPC** for the payment contract |
| Authentication | JWT (HS256) issued by the user service, verified at the gateway and by every service |
| Frontend | React 18, Vite, React Router, three.js (`@react-three/fiber`), lucide-react |
| Edge | nginx serving the built frontend and proxying `/api` and `/media` |
| AI | Any OpenAI-compatible chat-completions endpoint with tool calling (Gemini compatible API by default) |
| Containers | Docker, Docker Compose |
| Tests | pytest, FastAPI `TestClient`, real PostgreSQL for concurrency tests |

---

## Design decisions

### Why microservices?

Each domain owns its data and can be deployed, scaled and restarted independently: identity,
catalogue, reservations, payments, notifications and AI. A single shared database would have
recreated a distributed monolith, so every service gets its own database and role
(`db/init.sql`). Identifiers coming from another service (`user_id`, `showtime_id`) are stored
as plain values, never as foreign keys.

### REST and gRPC

REST/JSON is used for everything the browser consumes and for most internal calls, because it is
simple, cacheable and inspectable. The payment service additionally exposes a **gRPC contract**
(`payment-service/proto/payment.proto`) on port 50051: a typed, compact, HTTP/2 binary protocol
well suited to a critical internal operation. Both transports share the exact same business
logic (`PaymentService`), so behaviour cannot diverge; authentication travels in gRPC metadata,
never in the request body, and the client-supplied amount is ignored.

### Preventing double booking

The single source of truth is a **partial unique index** in PostgreSQL
(`uq_seat_active` on `seat_claims`). When two users claim the same seat at the same instant,
PostgreSQL lets exactly one `INSERT` succeed; the other gets a unique violation, which the
service turns into `409 Conflict`. No application-level lock is involved, so the guarantee holds
even with several service instances. Holds expire automatically (`HOLD_TTL_SECONDS`, 10 minutes
by default) and a background sweep frees abandoned seats.

### Payment idempotency

`POST /api/payments` requires an `Idempotency-Key` header. The key is stored with a fingerprint
of the request: replaying the same request returns the original payment (`200`), reusing the key
with a different body returns `409`. `payments.hold_id` is also unique, so two concurrent
requests cannot charge the same hold twice. The amount is always the authoritative total returned
by the reservation service — never a value sent by the client.

### Booking as a saga

A booking spans three services: `hold → charge → confirm`. There is no distributed transaction.
The payment is written first, then reservation confirmation is attempted as a **separate,
retryable step** that never triggers a second charge; `POST /api/payments/{id}/retry-confirmation`
replays it safely. If confirmation ultimately fails, the payment can be refunded through the
admin endpoint.

### Fault tolerance

- The gateway maps upstream failures to explicit `502`, `503` and `504` responses and applies
  per-upstream timeouts.
- Startup is resilient: services retry their database connection instead of crashing.
- A notification failure never breaks a booking: the notification service stores the email
  first, answers `201`, and retries delivery in the background.
- The AI assistant degrades gracefully: fallback models first, then a **deterministic
  no-LLM fallback** that still produces a holdable seat proposal.
- Health endpoints (`/health` on every service, `/api/health/upstreams` on the gateway) expose
  the state of each dependency.

### Notifications: synchronous call, asynchronous delivery

Reservation notifies the notification service over an internal authenticated HTTP call
(`X-Internal-Token`), not through a broker. This keeps the stack small and debuggable: the
notification service persists the email before attempting SMTP, so a mail outage only delays
delivery. A message broker (RabbitMQ/Kafka) is the natural next step for stronger decoupling —
see [Current limitations](#current-limitations).

---

## Quick start

### Prerequisites

- **Docker Desktop** with Docker Compose v2 (Linux containers)
- **Git**
- Optional, only for running a service outside Docker: Python 3.12 and Node.js 20+

Everything else (PostgreSQL, nginx, Mailpit) runs in containers.

### 1. Clone the repository

```bash
git clone https://github.com/Robot404a/mycima.git
cd mycima
```

### 2. Configure the environment

The root `.env` is **optional**: `docker-compose.yml` provides development defaults.
To override them, copy the example file:

```bash
cp .env.example .env
```

The AI assistant needs an LLM key. Its `.env` file is **required** by Compose:

```bash
cp ai-assistant-service/.env.example ai-assistant-service/.env
```

Then edit `ai-assistant-service/.env` and set at least:

```dotenv
LLM_API_KEY=your-real-key
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_MODEL=gemini-flash-lite-latest
```

> ⚠️ `ai-assistant-service/.env` is git-ignored. Never commit a real key.
> Without this file, `docker compose up` stops with an "env file not found" error.

### 3. Start the platform

```bash
docker compose up --build
```

The first build takes a few minutes. Services wait for PostgreSQL, apply their own schema at
startup, and the movie service seeds cinemas, halls, films and showtimes automatically.
Wait until `docker compose ps` lists the containers as running and
`http://localhost:8000/api/health/upstreams` reports every upstream as reachable, then open
**http://localhost:3000**.

To run in the background:

```bash
docker compose up --build -d
docker compose ps
```

### 4. Useful URLs

| What | URL |
|---|---|
| Application | http://localhost:3000 |
| Admin back-office | http://localhost:3000/admin |
| API gateway | http://localhost:8000 |
| Gateway Swagger | http://localhost:8000/docs |
| Gateway health | http://localhost:8000/health |
| Upstream health fan-out | http://localhost:8000/api/health/upstreams |
| User service | http://localhost:8001/docs |
| Movie service | http://localhost:8003/docs |
| Reservation service | http://localhost:8004/docs |
| AI assistant | http://localhost:8005/docs |
| Payment service | http://localhost:8006/docs |
| Notification service | http://localhost:8007/docs |
| Mailpit inbox | http://localhost:8025 |
| Payment gRPC | `localhost:50052` |

### 5. Stop or reset

```bash
docker compose down          # stop and remove containers, keep data
docker compose down -v       # also delete the volumes (all data, all databases)
```

`down -v` is the reliable way to replay `db/init.sql` from scratch. It destroys every service's
data, so use it only in development.

---

## Demo accounts

The user service seeds an administrator at startup, using `ADMIN_EMAIL`, `ADMIN_PASSWORD` and
`ADMIN_FULL_NAME` from the environment.

| Role | Email | Password |
|---|---|---|
| Administrator | `admin@mycima.com` | `admin12345` |

Regular users are **not** seeded: create one from http://localhost:3000/register.

---

## End-to-end walkthrough

1. **Register** a user (or log in as the administrator).
2. **Browse** the catalogue, open a film and pick a showtime.
3. **Select seats** on the seat map. The frontend calls `POST /api/holds`; the hold locks the
   seats for 10 minutes (configurable) and starts a countdown.
4. **Checkout**: the frontend sends `POST /api/payments` with a fresh `Idempotency-Key`.
   The payment service reads the authoritative total from the reservation service, simulates the
   charge, then confirms the hold. The reservation becomes `confirmed`.
5. **Notification**: the reservation service calls the notification service, which stores and
   sends the email. Open http://localhost:8025 to read it.
6. **Assistant alternative**: open the chat widget and ask, for example,
   *"two regular seats for the next showing of Dune"*. The assistant searches the catalogue,
   asks the reservation service for adjacent seats, shows a proposal, and only creates a hold
   after you explicitly confirm. It never pays.

To exercise failure paths in a demo, set `PAYMENT_SIMULATION_ENABLED=true` in `.env` and send
`"simulate_outcome": "failure"` in the payment body.

---

## API overview

All routes below are reached through the gateway with the `/api` prefix. Every service also
exposes its own Swagger UI on its port.

| Area | Main endpoints |
|---|---|
| Authentication | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/users/me`, `PATCH /api/users/me` |
| Catalogue | `GET /api/movies`, `GET /api/movies/{id-or-slug}`, `GET /api/movies/{ref}/showtimes`, `GET /api/showtimes`, `GET /api/showtimes/{id}`, `GET /api/cinemas`, `GET /api/halls` |
| Seats | `GET /api/showtimes/{id}/seats`, `GET /api/showtimes/{id}/suggest`, `GET /api/showtimes/{id}/availability` |
| Holds | `POST /api/holds`, `GET /api/holds`, `GET /api/holds/{id}`, `DELETE /api/holds/{id}` |
| Bookings | `POST /api/holds/{id}/confirm`, `POST /api/bookings`, `GET /api/bookings/me`, `GET /api/bookings/{id}`, `POST /api/bookings/{id}/cancel` |
| Payments | `POST /api/payments` (**`Idempotency-Key` required**), `GET /api/payments`, `GET /api/payments/{id}`, `POST /api/payments/{id}/retry-confirmation` |
| Notifications | `GET /api/notifications/me`, `GET /api/notifications/unread-count`, `POST /api/notifications/read-all` |
| Assistant | `POST /api/assistant/chat`, `GET /api/assistant/sessions`, `GET /api/assistant/sessions/{id}` |
| Administration | `/api/admin/users`, `/api/admin/movies`, `/api/admin/showtimes`, `/api/admin/halls`, `/api/admin/bookings`, `/api/admin/holds`, `/api/admin/stats`, `/api/admin/payments`, `/api/admin/notifications` |
| Health | `GET /api/health`, `GET /api/health/upstreams` |

Example — create a payment:

```bash
# Any unique string works as an idempotency key.
# Reuse the same value to replay the request instead of charging twice.
curl -X POST http://localhost:8000/api/payments \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-key-0001" \
  -d '{"hold_id":"<hold-uuid>","method":"CARD","currency":"MAD"}'
```

*Examples use bash/zsh syntax; on PowerShell, put the command on a single line.*

Replaying the same request with the same key returns the original payment instead of charging
again.

---

## AI assistant

The assistant is a separate service, not a feature baked into the frontend.

- **Role of the model**: understand the request, choose which tool to call, and phrase the
  answer. It never accesses a database, never invents a film, a showtime, a seat or a price, and
  **never pays**.
- **Inputs**: a chat message plus a session identifier; the conversation history is persisted in
  `ai_assistant_db`.
- **Outputs**: a natural-language reply, plus an optional structured seat proposal or hold that
  the frontend renders as a card.
- **Tools** (all executed through the gateway with the guest's JWT): search movies, list
  showtimes, read seat availability, suggest adjacent seats, create a hold.
- **Topic guard**: off-topic messages are refused before the answering agent runs; if the
  classifier is unavailable the guard fails open so an LLM outage never blocks a booking.
- **Confirmation rule**: a hold is created only after the guest explicitly confirms the
  proposal.
- **Fallbacks**: a chain of models (`LLM_MODEL` then `LLM_MODEL_FALLBACKS`), and if none
  answers, a deterministic no-LLM flow that still produces a real, holdable proposal.

Configuration lives in `ai-assistant-service/.env`; see
[ai-assistant-service/README.md](ai-assistant-service/README.md).

---

## Payment service and gRPC

The payment service exposes the **same business logic over two transports**:

- **REST** on port 8000 (host 8006), used by the frontend through the gateway.
- **gRPC** on port 50051 (host 50052), contract in
  [`payment-service/proto/payment.proto`](payment-service/proto/payment.proto):

```proto
service PaymentService {
  rpc Charge (ChargeRequest) returns (ChargeResponse);
}
```

Authentication is carried in the `authorization` gRPC metadata. The `amount` field of the
contract is intentionally ignored: the amount is always read from the reservation service.
With [`grpcurl`](https://github.com/fullstorydev/grpcurl) installed, from the repository root:

```bash
grpcurl -plaintext \
  -proto payment-service/proto/payment.proto \
  -H "authorization: Bearer $TOKEN" \
  -d '{"hold_id":"<hold-uuid>","amount":"0","currency":"MAD"}' \
  localhost:50052 nocturne.payment.PaymentService/Charge
```

---

## Testing

Each service has its own test suite, run with pytest. There are **148 test functions** at the
time of writing.

| Service | Test functions | External dependency |
|---|---:|---|
| payment-service | 48 | none (temporary SQLite + fake reservation service) |
| reservation-service | 29 | PostgreSQL on `localhost:5433` |
| ai-assistant-service | 27 | none (temporary SQLite + stubbed LLM) |
| notification-service | 17 | PostgreSQL on `localhost:5434` |
| user-service | 16 | none (temporary SQLite) |
| movie-service | 11 | none (temporary SQLite) |

Run a suite:

```bash
cd payment-service
python -m pytest
```

Suites that need a real PostgreSQL start their own database container:

```bash
# reservation-service — database on 5433, tests use a separate reservation_test database
docker compose -f reservation-service/docker-compose.dev.yml up -d reservation-db
cd reservation-service && python -m pytest

# notification-service — database on 5434
docker compose -f notification-service/docker-compose.dev.yml up -d notification-db
cd notification-service && python -m pytest
```

The most important test is the concurrency test in `reservation-service/tests/test_api.py`:
ten clients race for the same seat against a real PostgreSQL, and the test asserts exactly one
`201 Created` and nine `409 Conflict`. It proves that the anti-double-booking guarantee comes
from the database constraint, not from luck.

---

## Configuration reference

### Root `.env` (optional — defaults are in `docker-compose.yml`)

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_PASSWORD` | `admin123` | PostgreSQL superuser password |
| `JWT_SECRET` | dev value | Shared HS256 secret; must be identical everywhere |
| `JWT_ALGORITHM` | `HS256` | Token algorithm |
| `JWT_EXPIRE_MINUTES` | `120` | Token lifetime |
| `ADMIN_EMAIL` | `admin@mycima.com` | Seeded administrator |
| `ADMIN_PASSWORD` | `admin12345` | Seeded administrator password |
| `ADMIN_FULL_NAME` | `MyCima Admin` | Seeded administrator name |
| `PAYMENT_SIMULATION_ENABLED` | `false` | Allows clients to force a payment outcome (demos) |
| `INTERNAL_API_KEY` | dev value | Shared secret for internal service-to-service calls |
| `HOLD_TTL_SECONDS` | `600` | Seat hold lifetime (10 minutes) |
| `MAX_SEATS_PER_HOLD` | `8` | Maximum seats in one hold |
| `LOG_LEVEL` | `INFO` | Log verbosity |

> These variables are read by `docker-compose.yml` with the defaults shown above; they can be
> added to `.env` to override them even though they are not all listed in `.env.example`.

### `ai-assistant-service/.env` (required)

| Variable | Purpose |
|---|---|
| `LLM_API_KEY` | Key for the OpenAI-compatible provider |
| `LLM_BASE_URL` | Provider endpoint (Gemini compatible API by default) |
| `LLM_MODEL`, `LLM_MODEL_FALLBACKS` | Primary model and fallback chain |
| `LLM_TIMEOUT_SECONDS`, `LLM_MAX_ITERATIONS` | Timeout and tool-loop bound |
| `GATEWAY_INTERNAL_URL` | Platform entry point used by the tools |
| `JWT_SECRET` | Must match the gateway's secret |
| `PROPOSAL_TTL_MINUTES` | Lifetime of a seat proposal before confirmation |

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `502 Bad Gateway` on http://localhost:3000 | Docker Desktop is not running, or the containers are stopped. Start Docker, then `docker compose ps` and `docker compose up -d`. |
| Compose stops with `env file .../ai-assistant-service/.env not found` | Create it: `cp ai-assistant-service/.env.example ai-assistant-service/.env`, then set `LLM_API_KEY`. |
| `port is already allocated` | Another process or an older container uses the port. Run `docker compose down`, or change the host port mapping. |
| A service restarts with "database does not exist" | `db/init.sql` only runs on an **empty** volume. Either `docker compose down -v` (destroys all data) or create the missing role and database manually. |
| No emails in Mailpit | Open http://localhost:8025, then check `docker compose logs notification-service`. A failed send is stored and retried automatically. |
| Payment returns `503` | The reservation service is unreachable; check its health at http://localhost:8004/health. |
| Assistant answers with a generic fallback | The LLM key or quota is missing. Check `docker compose logs ai-assistant-service`. |
| Changes not visible after an edit | Rebuild the image: `docker compose up --build -d <service>`. |

Logs:

```bash
docker compose logs -f gateway
docker compose logs -f reservation-service payment-service notification-service
```

---

## Project structure

```text
mycima/
├── ai-assistant-service/    # LLM agent, tools, guard, fallback
├── db/
│   └── init.sql             # roles and databases, one per service
├── frontend/                # React app, nginx config, Dockerfile
├── gateway/                 # routing, JWT, auth rate limit, health
├── movie-service/           # catalogue, halls, showtimes, seeding
├── notification-service/    # email log, SMTP delivery, retries
├── payment-service/         # REST + gRPC, idempotency, refunds, proto/
├── reservation-service/     # holds, bookings, seat claims, SQL schema
├── shared/                  # JWT helpers and JSON logging shared by services
├── docker-compose.yml       # full platform
├── .env.example
└── README.md
```

Every service directory contains its own README with endpoints, tests and isolated development
instructions.

---

## Current limitations

These are known and documented on purpose:

- **One PostgreSQL instance** hosts all six databases. It is a single point of failure; production
  would use one managed cluster (or at least a primary plus replica) per critical service.
- **Notifications are delivered over a synchronous internal call**, with persistence and
  background retries, but without a broker. A message queue would decouple the two services
  further and survive a crash between acknowledgement and delivery.
- **The booking saga has no automatic compensation.** If the charge succeeds and reservation
  confirmation keeps failing, an administrator must trigger the refund.
- **Development secrets** (database passwords, JWT secret, internal key) are committed as
  defaults for local use. They must be replaced by real secrets for any deployment.
- **No metrics or tracing** yet: structured JSON logs and health endpoints exist, but there is no
  Prometheus/Grafana or OpenTelemetry pipeline.
- **The reservation service runs as a single instance** in the provided Compose file. The gateway
  already balances over the DNS records of the service name, so running several replicas only
  requires removing the fixed `container_name` and the host port mapping, then scaling with
  `docker compose up -d --scale reservation-service=2`.

---

## Team

- [@Robot404a](https://github.com/Robot404a)
- [@Abdelaali-dev-06](https://github.com/Abdelaali-dev-06)
- [@Youssefboulahnya](https://github.com/Youssefboulahnya)

---

**MyCima — Bringing intelligent cinema experiences to life.**
