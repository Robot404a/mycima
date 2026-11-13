# Reservation Service

Seat availability, temporary seat holds (locks) and bookings. FastAPI + PostgreSQL (psycopg 3, plain SQL).
Paths below are what the service sees; the frontend calls them through the gateway as `/api/...`.

## Run it locally

```powershell
cd reservation-service
py -3.12 -m venv .venv ; .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
docker compose up -d                        # Postgres on localhost:5433
python -m uvicorn main:app --reload --port 8001
```
Docs & try-it page: http://localhost:8001/docs · Tests: `python -m pytest` (uses a separate `reservation_test` database).
Everything in Docker: `docker compose --profile app up -d --build`.

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
| Token format, `shared/` | `auth.py`, `logging_setup.py` | uses `shared.*` automatically when the folder exists; otherwise PyJWT with `JWT_SECRET`. User id must be numeric (`sub`/`id`/`user_id`) |
| Notification / Payment calls | `service.after_booking_confirmed()` | only logs; plug the other services in here |
| ID types | `db/schema.sql` | `user_id`, `showtime_id` are BIGINT |
