# 🤖 AI Assistant Service

Conversational booking assistant of **MyCima**. It turns natural language into real
bookings: it discovers films and showtimes in the **Movie service**, asks the
**Reservation service** for seat suggestions and holds them, and answers in the guest's
language. It never pays and never invents data.

All its calls go through the **API gateway** with the guest's own JWT, so the chatbot can
never do more than the signed-in user.

---

## Architecture

```
Frontend ──REST──► Gateway ──► AI Assistant ──► Gateway ──► Movie service
                     │            │                    └──► Reservation service
                     │            └──► LLM provider (OpenAI-compatible, tool calling)
                     └──► User / Movie / Reservation / Notification
```

| Piece | Role |
|---|---|
| `agent.py` | Agent loop: LLM → tool calls → tool results → final answer (max `LLM_MAX_ITERATIONS`, then one tools-off summary so gathered data is never lost to the fallback) |
| `tools.py` | The 5 tools, mapped to the real platform endpoints |
| `llm.py` | OpenAI-compatible client with model fallback chain |
| `fallback.py` | Deterministic degradation: searches the catalogue and suggests seats without any LLM |
| `security.py` | JWT verification (shared `shared.auth` when available) |
| `db.py` / `models.py` | Conversation history + pending seat proposal in `ai_assistant_db` |
| `prompts.py` | System prompt and tool schema |

**Guardrails:** seats are chosen by the reservation engine, never by the LLM; `hold_seats`
requires an explicit confirmation in the guest's latest message; only the seat groups
returned by `suggest_seats` can be held; the assistant can hold but never pay.

### Topic guard (`guard.py`)

The assistant must not answer general questions (history, politics, science, coding, trivia…).
A prompt rule is only probabilistic, so every message is screened **before** the agent runs:

1. obvious booking talk (genres, seats, showtimes, greetings, short confirmations) is allowed
   immediately — no extra call, no added latency;
2. anything else goes through a tiny classifier call (`temperature=0`, ~4 tokens) that answers
   `ALLOW` or `REFUSE`;
3. a refused message gets a one-sentence redirect and **never reaches the answering model**, so
   no off-topic answer can be produced;
4. if the classifier is unavailable or answers unexpectedly, the message is allowed (fail open)
   so an LLM outage never breaks the booking flow.

Refused replies carry `"refused": true` in the response; the booking payload is untouched.

---

## Endpoints

All mounted behind the gateway as `/api/assistant/...` (JWT required).

| Method | Path | Description |
|---|---|---|
| POST | `/assistant/chat` | `{message, session_id?}` → `{session_id, reply, pending_confirmation, hold, status}` |
| POST | `/assistant/confirm-hold` | `{session_id}` → holds the pending seats (used by the seat map's confirm button) · 410 if the proposal expired · 409 if the seats were taken |
| GET | `/assistant/sessions?limit=` | My conversations |
| GET | `/assistant/sessions/{id}` | Messages, pending proposal and last hold |
| DELETE | `/assistant/sessions/{id}` | Delete a conversation |
| GET | `/health` | Service, database and LLM configuration |

`pending_confirmation` carries what the seat map needs to highlight seats:

```json
{
  "showtime_id": 52,
  "seat_ids": ["H9", "H10"],
  "suggestions": [{"row": "H", "seats": ["H9", "H10"], "score": 0.6}],
  "total_price": 100.0,
  "currency": "MAD",
  "movie": {"id": 1, "title": "Inception", "poster_url": "/media/posters/inception.jpg"},
  "cinema": "Pathé Californie",
  "hall": "Salle 1",
  "starts_at": "2026-11-16T19:30:00Z",
  "date": "2026-11-16",
  "time": "19:30",
  "proposal_expires_at": "2026-11-15T16:00:00+00:00"
}
```

---

## Tools and the APIs they use

| Tool | Real call (through the gateway) |
|---|---|
| `search_movies(query, genre, mood, date)` | `GET /movies?q=&genre=&mood=&date=&now_showing=true` |
| `get_showtimes(movie_id, date, cinema_id)` | `GET /movies/{id}/showtimes?date=&cinema_id=` |
| `get_seat_availability(showtime_id)` | `GET /showtimes/{id}/seats` (reservation) + `GET /showtimes/{id}` (movie) |
| `suggest_seats(showtime_id, count)` | `GET /showtimes/{id}/suggest?count=` + `GET /showtimes/{id}/seats` |
| `hold_seats(showtime_id, seat_ids, confirm)` | `POST /holds` with `{showtime_id, seats}` |

Contracts were taken from the implemented services: the Movie service returns
`{items: [...]}` with `price`/`currency`, `hall.rows`, `hall.seats_per_row`, and the
Reservation service returns `suggestions` and holds shaped as
`{id, showtime_id, seats, total, expires_at, seconds_left}`.

---

## LLM configuration

Any OpenAI-compatible endpoint works. The default is Gemini's compatible API:

```
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_API_KEY=...                 # never commit; keep it in the untracked .env
LLM_MODEL=gemini-flash-lite-latest
LLM_MODEL_FALLBACKS=gemini-2.5-flash,gemini-2.5-flash-lite
```

If the LLM is unreachable, `fallback.py` still answers, finds a film in the real catalogue
and proposes real seats, so the booking flow keeps working.

---

## Run it

Local (SQLite, no Docker):

```bash
cd ai-assistant-service
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env        # then put your own LLM_API_KEY in .env
uvicorn main:app --reload --port 8005
```

Docker (whole platform, from the repository root):

```bash
docker compose up -d --build
# gateway on :8000, movie :8003, reservation :8004, AI :8005
```

The compose entry reads `ai-assistant-service/.env` (git-ignored) and overrides
`DATABASE_URL` with the service's Postgres database.

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./assistant.db` | Postgres `ai_assistant_db` in Compose |
| `JWT_SECRET` / `JWT_ALGORITHM` | dev values | Must match the user service and gateway |
| `GATEWAY_INTERNAL_URL` | `http://gateway:8000/api` | Where the tools send their calls |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` / `LLM_MODEL_FALLBACKS` | Gemini compatible API | LLM provider |
| `LLM_TIMEOUT_SECONDS` | `45` | Per-model timeout |
| `LLM_MAX_ITERATIONS` | `5` | Agent loop limit |
| `CINEMA_TIMEZONE` | `Africa/Casablanca` | Local date/time shown to guests |
| `MAX_SEATS_PER_HOLD` | `8` | Tool limit, matches the reservation rule |
| `PROPOSAL_TTL_MINUTES` | `15` | How long a seat proposal can be held from the UI |
| `HISTORY_LIMIT` | `40` | Messages sent back to the LLM |

---

## Tests

```bash
cd ai-assistant-service
pytest tests -q
```

16 tests run on a throwaway SQLite database with a fake upstream that returns the exact
Movie/Reservation payloads, plus a scripted LLM:

- health and LLM configuration, 401 without token, 422 on empty message;
- tool contracts: catalogue search params, showtime payload → local date/time, seat
  suggestion → `pending_confirmation` with seats, price and venue;
- guardrails: hold refused without explicit confirmation, refused for seats that were not
  suggested, allowed after "yes, hold them", proposal consumed afterwards;
- `confirm-hold` endpoint: success, 409 conflict, 410 expired proposal;
- graceful degradation when the LLM is down (real catalogue + real seat suggestion);
- per-user isolation of conversations, history and deletion;
- history normalization (no orphan tool messages reach the provider);
- topic guard: off-topic messages refused without calling the agent (WWII, coding, sport,
  recipes), booking talk skips the guard, and a guard failure fails open.
