# Reservation Service

Seat availability, temporary seat holds (locks) and bookings. FastAPI + PostgreSQL (psycopg 3, plain SQL).
Paths below are what the service sees; the frontend calls them through the gateway as `/api/...`.

## Run it locally (alone)

```powershell
cd reservation-service
py -3.12 -m venv .venv ; .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
docker compose -f docker-compose.dev.yml up -d      # own Postgres on localhost:5433
python -m uvicorn main:app --reload --port 8001
```
The service creates its tables itself at startup. If the repo's `shared/` folder exists it is used automatically (auth, JSON logging).
Docs & try-it page: http://localhost:8001/docs · Tests: `python -m pytest` (separate `reservation_test` database).
Service + DB in Docker: `docker compose -f docker-compose.dev.yml --profile app up -d --build` (service on port 8003).

## Run it with the whole system
The service is declared in the repo-root `docker-compose.yml` (one shared Postgres, one database per service):
```yaml
  reservation-service:
    build:
      context: .
      dockerfile: reservation-service/Dockerfile
    environment:
      DATABASE_URL: postgresql://reservation_svc:reservation_svc_pass@postgres:5432/reservation_db
      JWT_SECRET: ${JWT_SECRET:-mycima-dev-secret-change-me-in-production}
      MOVIE_LOOKUP: ${MOVIE_LOOKUP:-stub}
    deploy:
      replicas: 2          # the gateway round-robins over every replica behind this name
    depends_on:
      postgres:
        condition: service_healthy
```
No `container_name` and no `ports:` on purpose (both prevent running several replicas). And in `db/init.sql`:
```sql
CREATE ROLE reservation_svc LOGIN PASSWORD 'reservation_svc_pass';
CREATE DATABASE reservation_db OWNER reservation_svc;
```
`init.sql` only runs on an empty `pgdata` volume: for an existing one, run `docker compose down -v` once (this resets ALL team databases) or create the role/database by hand.

## Flow
1. `GET /showtimes/{id}/seats` — seat map (public).
2. `POST /holds` — lock seats for `HOLD_TTL_SECONDS` (default 10 min). Picking seats again replaces your previous hold for that showtime.
3. `POST /holds/{id}/confirm` (or `POST /bookings`) — turn the hold into a booking. Safe to repeat.
4. `POST /bookings/{id}/cancel` — frees the seats.

## Endpoints
| Method & path | Auth | Notes |
|---|---|---|
| `GET /health` | – | 503 if the DB is down |
| `GET /showtimes/availability?ids=1,2,3` | – | `{showtimes:[{showtime_id,total,available,held,booked}]}` |
| `GET /showtimes/{id}/availability` | – | same, one showtime |
| `GET /showtimes/{id}/seats` | optional | `{price, rows, seats_per_row, seats:[{label,row,number,status,mine}]}` · status = available/held/booked |
| `GET /showtimes/{id}/suggest?count=2` | – | best groups of adjacent seats: `{suggestions:[{row,seats,score}]}` |
| `POST /holds` | user | body `{showtime_id, seats:["A5","A6"]}` → 201 hold · **409** `{detail:{message, unavailable_seats}}` |
| `GET /holds?status=active` | user | my holds |
| `GET /holds/{id}` · `DELETE /holds/{id}` | user | view / release |
| `POST /holds/{id}/confirm` | user | optional body `{payment_ref}` → 201 booking · **410** if the hold expired |
| `POST /bookings` | user | body `{hold_id, payment_ref?}` (same as confirm) |
| `GET /bookings` · `GET /bookings/{id}` | user | my bookings |
| `POST /bookings/{id}/cancel` | user | not allowed once the showtime started (409) |
| `GET /admin/bookings` `GET /admin/holds` `GET /admin/stats` `POST /admin/bookings/{id}/cancel` | admin | filters: status, showtime_id, user_id, limit, offset |

Hold object: `{id, user_id, showtime_id, status, seats, total, created_at, expires_at, seconds_left}`  
Booking object: `{id, user_id, showtime_id, hold_id, status, seats, total_amount, payment_ref, created_at, cancelled_at}`

## Things to agree with the team (all isolated in one place each)
| Topic | Where | Now |
|---|---|---|
| Hall layout, price, start time | `movie_client.py` (`_parse`) | `MOVIE_LOOKUP=stub`: hall A–H × 12 seats, price 8.00. `http`: expects `GET /showtimes/{id}` → `{price, starts_at, hall:{rows, seats_per_row}}` |
| Token format | `auth.py` | uses `shared.auth` (user id must be numeric: `sub`). Without `shared/` a local PyJWT fallback is used |
| Notification / Payment calls | `service.after_booking_confirmed()` | only logs; plug the other services in here |
| ID types | `db/schema.sql` | `user_id`, `showtime_id` are BIGINT |
