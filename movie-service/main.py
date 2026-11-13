"""MyCima Movie Service.

Owns the catalog database (movies_db): movies, cinemas, halls, seat layouts and
showtimes. Read-only for clients; mutations are exposed under /admin and
protected by an admin JWT forwarded by the API gateway.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db, init_db
from app.models import Movie
from app.routers import admin, cinemas, halls, media, movies, showtimes
from app.seed import seed_database

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(settings.service_name)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if settings.seed_on_startup:
        with SessionLocal() as db:
            seed_database(db)
    logger.info("movie service ready")
    yield
    logger.info("movie service stopped")


app = FastAPI(
    title="MyCima Movie Service",
    description=(
        "Catalog service of the MyCima distributed cinema platform: movies, cinemas, "
        "halls, seat layouts and showtimes."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Length", "Content-Range"],
)

app.include_router(movies.router)
app.include_router(showtimes.router)
app.include_router(cinemas.router)
app.include_router(halls.router)
app.include_router(media.router)
app.include_router(admin.router)


@app.get("/", tags=["meta"], summary="Service banner")
def root() -> dict:
    return {
        "service": settings.service_name,
        "docs": "/docs",
        "health": "/health",
        "resources": ["/movies", "/cinemas", "/halls", "/showtimes"],
    }


@app.get("/health", tags=["meta"], summary="Health check")
def health(db: Session = Depends(get_db)) -> dict:
    try:
        movie_count = db.scalar(select(func.count(Movie.id)))
        database_ok = True
    except Exception:  # pragma: no cover - only when the database is unreachable
        movie_count = None
        database_ok = False
    return {
        "status": "ok" if database_ok else "degraded",
        "service": settings.service_name,
        "database": database_ok,
        "movies": movie_count,
        "timestamp": time.time(),
    }
