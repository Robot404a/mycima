# 🎬 Movie Service

Catalog microservice of **MyCima** — the distributed cinema booking platform. It owns
`movies_db` and is the only service allowed to read or write the catalog.

Everything else in the platform reaches it through the API gateway
(`http://gateway:8000/api/...`), which strips the `/api` prefix before forwarding.

---

## Responsibilities

- Movies (title, original title, year, director, cast, genres, mood tags, synopsis,
  duration, rating, age rating, language, country, poster).
- Cinemas and halls, including the **seat layout** used to draw the seat map.
- Showtimes (movie + hall + start time + price + language + format).
- Poster delivery with a local cache and a generated fallback.
- Catalog search/filtering for the frontend and the AI assistant tools
  (`search_movies`, `get_showtimes`).
- Admin CRUD for movies, showtimes, cinemas and halls.

It never stores seat availability, holds or bookings — that belongs to the
reservation service, which initializes its seat states from `/halls/{id}/layout`.

---

## Endpoints

### Catalog (public, no token required)

| Method | Path | Description |
|---|---|---|
| GET | `/movies` | List / search movies |
| GET | `/movies?genre=&mood=&date=&cinema_id=&q=&sort=&limit=&offset=` | Filters: genre, mood tag, day with showtimes, cinema, free-text, sort (`rating`, `title`, `year`, `newest`) |
| GET | `/movies/genres` | Distinct genres |
| GET | `/movies/moods` | Distinct mood tags (used by the chatbot) |
| GET | `/movies/{id_or_slug}` | Movie details |
| GET | `/movies/{id_or_slug}/showtimes?date=&cinema_id=` | Upcoming showtimes of one movie |
| GET | `/showtimes?date=&movie_id=&cinema_id=&hall_id=` | Showtimes across the catalog |
| GET | `/showtimes/{id}` | One showtime with movie, hall and cinema |
| GET | `/cinemas?city=` | Cinemas |
| GET | `/cinemas/{id}` | Cinema with its halls |
| GET | `/halls?cinema_id=` | Halls |
| GET | `/halls/{id}` | Hall details |
| GET | `/halls/{id}/layout` | Full seat layout (`A1`, `A2`, …, aisles, blocked seats) |
| GET | `/media/posters/{slug}.jpg` | Poster (cached JPEG, or generated SVG placeholder) |
| GET | `/health` | Health + movie count + database status |

### Admin (requires a JWT with `role: admin`)

| Method | Path | Description |
|---|---|---|
| POST | `/admin/movies` | Add a movie (slug generated from the title) |
| PATCH | `/admin/movies/{id}` | Update a movie |
| DELETE | `/admin/movies/{id}` | Delete a movie and its showtimes |
| POST | `/admin/showtimes` | Schedule a showtime (409 on duplicate or hall clash) |
| DELETE | `/admin/showtimes/{id}` | Cancel a showtime |
| POST | `/admin/cinemas` | Add a cinema |
| POST | `/admin/halls` | Add a hall |
| DELETE | `/admin/halls/{id}` | Delete a hall |

Swagger UI: `http://localhost:8003/docs` (or the gateway URL).

### Showtime JSON

```json
{
  "id": 42,
  "movie_id": 1,
  "hall_id": 1,
  "starts_at": "2026-11-14T19:30:00Z",
  "price": 90.0,
  "price_cents": 9000,
  "currency": "MAD",
  "language": "VO",
  "format": "IMAX",
  "movie": { "id": 1, "slug": "inception", "title": "Inception", "...": "..." },
  "hall": { "id": 1, "name": "Salle 1 - IMAX", "screen_type": "imax", "total_seats": 306 },
  "cinema": { "id": 1, "name": "Megarama Casablanca", "city": "Casablanca" }
}
```

All datetimes are stored as **naive UTC** and exposed as ISO 8601 with a `Z` suffix.

---

## Seat layout

`GET /halls/{id}/layout` is what the reservation service uses to initialize its seat
states and what the frontend draws as SVG:

```json
{
  "hall_id": 1,
  "name": "Salle 1 - IMAX",
  "screen_type": "imax",
  "rows": 14,
  "seats_per_row": 22,
  "aisle_after": [4, 18],
  "row_labels": ["A", "B", "..."],
  "total_seats": 306,
  "cinema": { "id": 1, "name": "Megarama Casablanca", "city": "Casablanca" },
  "layout": [
    { "row": "A", "seats": [{ "id": "A1", "number": 1, "blocked": false }, "..."] }
  ]
}
```

`aisle_after` lists the 1-based seat numbers after which the map should draw an aisle.

---

## Seed data

Real cinemas and real films, inserted automatically at startup
(`SEED_ON_STARTUP`, idempotent — existing rows are kept).

- **5 cinemas**: Megarama Casablanca, Pathé Californie, Cinéma Rif (Casablanca),
  Megarama Marrakech, Cinéma Le Colisée (Rabat) — 8 halls, 5 screen types.
- **28 films** with real metadata: Inception, Interstellar, The Dark Knight,
  Oppenheimer, Dune: Part Two, Blade Runner 2049, Parasite, La La Land, Whiplash,
  Spirited Away, Your Name, The Grand Budapest Hotel, Everything Everywhere All at
  Once, The Godfather, Mad Max: Fury Road, Get Out, The Shawshank Redemption,
  Spider-Man: Across the Spider-Verse, Top Gun: Maverick, Knives Out, Coco, The Matrix,
  Barbie, John Wick: Chapter 4, Amélie, Les Chevaux de Dieu, Ali Zaoua, Casanegra.
- **Showtimes** for the next `SEED_DAYS` days (default 7), 4 slots a day per hall
  (11:30, 15:30, 19:30, 23:30 cinema local time), conflict-free by construction.
  Prices: 50 MAD standard, 80 MAD premium, 90 MAD IMAX, 130 MAD VIP.

Genres and mood tags (`cerebral`, `romantic`, `family`, `tense`, …) are what the AI
assistant uses for its `search_movies(genre, mood, date)` tool.

### Posters

`poster_path` values are TMDB CDN paths. The service downloads each poster on the first
request and caches it in `POSTER_CACHE_DIR` (default `./media_cache`, git-ignored).
If a poster is missing or the network is down, a generated SVG poster with the title,
year and genres is served instead, so the UI never shows a broken image.

---

## Run it

### Locally (SQLite, no Docker)

```bash
cd movie-service
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn main:app --reload --port 8003
```

Open http://localhost:8003/docs.

### Docker Compose

The Dockerfile expects the **repository root** as build context (same convention as the
gateway). Add this service to the root `docker-compose.yml`:

```yaml
  movie-service:
    build:
      context: .
      dockerfile: movie-service/Dockerfile
    environment:
      DATABASE_URL: postgresql+psycopg://movie:movie@postgres:5432/movies_db
      JWT_SECRET: ${JWT_SECRET:-dev-secret-change-me}
      SEED_ON_STARTUP: "true"
      POSTER_CACHE_DIR: /data/posters
    ports: ["8003:8000"]
    volumes:
      - movie-posters:/data/posters
    depends_on: [postgres]
```

And the database in `db/init.sql`:

```sql
CREATE DATABASE movies_db;
```

The gateway already targets this service with
`MOVIE_SERVICE_URL=http://movie-service:8000`.

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///.../movie_service.db` | PostgreSQL in Compose (`postgresql+psycopg://.../movies_db`) |
| `JWT_SECRET` | `dev-secret-change-me` | Shared secret with the user service / gateway |
| `JWT_ALGORITHM` | `HS256` | Token algorithm |
| `SEED_ON_STARTUP` | `true` | Seed catalog + showtimes on boot |
| `SEED_DAYS` | `7` | Days of showtimes to generate |
| `CINEMA_TIMEZONE` | `Africa/Casablanca` | Timezone of showtime wall-clock times |
| `POSTER_CACHE_DIR` | `./media_cache` | Where downloaded posters are stored |
| `POSTER_BASE_URL` | `https://image.tmdb.org/t/p/w500` | Poster CDN base URL |
| `POSTER_TIMEOUT_SECONDS` | `8` | Poster download timeout |
| `LOG_LEVEL` | `INFO` | Log verbosity |

---

## Tests

```bash
cd movie-service
pytest tests -q
```

The suite runs on a throwaway SQLite database and covers the health check, catalog
listing and real seed data, genre/mood filters, search, movie details, seeded
showtimes, day filtering, hall layouts, poster fallback, 404s, admin authorization
and the admin create/update/delete cycle.
