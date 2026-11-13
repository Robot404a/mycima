"""Poster delivery.

Real posters are downloaded once from the TMDB CDN and cached on disk, so the
cinema UI keeps working offline and the API never exposes broken images. When a
poster cannot be fetched, a generated SVG poster (title, year, genres) is served
instead.
"""

from __future__ import annotations

import html
import threading
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Movie

router = APIRouter(prefix="/media", tags=["media"])

CACHE_CONTROL = "public, max-age=86400"
_FAILED: dict[str, float] = {}
_FAILED_LOCK = threading.Lock()
_FAILED_TTL_SECONDS = 600


def _cache_file(slug: str) -> Path:
    return settings.media_cache_dir / f"{slug}.jpg"


def _can_retry(slug: str) -> bool:
    with _FAILED_LOCK:
        last = _FAILED.get(slug)
        if last is None:
            return True
        if time.monotonic() - last > _FAILED_TTL_SECONDS:
            _FAILED.pop(slug, None)
            return True
        return False


def _mark_failed(slug: str) -> None:
    with _FAILED_LOCK:
        _FAILED[slug] = time.monotonic()


def _download_poster(slug: str, poster_path: str) -> Path | None:
    if not poster_path.startswith("/"):
        return None
    if not _can_retry(slug):
        return None
    target = _cache_file(slug)
    try:
        settings.media_cache_dir.mkdir(parents=True, exist_ok=True)
        with httpx.Client(timeout=settings.poster_timeout_seconds, follow_redirects=True) as client:
            response = client.get(settings.poster_base_url + poster_path)
        if response.status_code != 200 or not response.content:
            _mark_failed(slug)
            return None
        target.write_bytes(response.content)
        return target
    except (httpx.HTTPError, OSError):
        _mark_failed(slug)
        return None


def _wrap(text: str, width: int = 16, max_lines: int = 4) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max(0, width - 1)] + "…"
    return lines or [text[:width]]


def _placeholder_svg(movie: Movie) -> str:
    hue = sum(ord(char) for char in movie.slug) % 360
    title_lines = _wrap(movie.title)
    start_y = 520 - (len(title_lines) - 1) * 34
    title_markup = "".join(
        f'<text x="50" y="{start_y + index * 52}" font-family="Georgia, serif" '
        f'font-size="46" font-weight="700" fill="#fdf6e3">{html.escape(line)}</text>'
        for index, line in enumerate(title_lines)
    )
    genre_line = html.escape(" · ".join((movie.genres or [])[:3]))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="500" height="750" viewBox="0 0 500 750">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="hsl({hue}, 48%, 16%)"/>
      <stop offset="55%" stop-color="hsl({(hue + 35) % 360}, 55%, 26%)"/>
      <stop offset="100%" stop-color="hsl({(hue + 70) % 360}, 60%, 10%)"/>
    </linearGradient>
  </defs>
  <rect width="500" height="750" fill="url(#bg)"/>
  <circle cx="410" cy="120" r="150" fill="hsl({(hue + 20) % 360}, 70%, 60%)" opacity="0.14"/>
  <circle cx="90" cy="640" r="190" fill="hsl({(hue + 300) % 360}, 70%, 55%)" opacity="0.12"/>
  <text x="50" y="90" font-family="Helvetica, Arial, sans-serif" font-size="18"
        letter-spacing="6" fill="#e7c873">MYCIMA</text>
  {title_markup}
  <text x="50" y="{start_y + len(title_lines) * 52 + 14}" font-family="Helvetica, Arial, sans-serif"
        font-size="22" fill="#cbd5e1">{movie.release_year} · {genre_line}</text>
  <text x="50" y="700" font-family="Helvetica, Arial, sans-serif" font-size="16"
        fill="#94a3b8">{html.escape(movie.director or "")}</text>
</svg>
"""


@router.get(
    "/posters/{filename}",
    summary="Movie poster (cached JPEG, or a generated SVG placeholder)",
    response_class=Response,
)
def get_poster(filename: str, db: Session = Depends(get_db)) -> Response:
    slug = filename.rsplit(".", 1)[0].strip().lower()
    movie = db.scalar(select(Movie).where(Movie.slug == slug))
    if movie is None:
        raise HTTPException(status_code=404, detail="Poster not found.")

    cached = _cache_file(slug)
    if cached.exists() and cached.stat().st_size > 0:
        return FileResponse(cached, media_type="image/jpeg", headers={"Cache-Control": CACHE_CONTROL})

    if movie.poster_path:
        downloaded = _download_poster(slug, movie.poster_path)
        if downloaded is not None:
            return FileResponse(downloaded, media_type="image/jpeg", headers={"Cache-Control": CACHE_CONTROL})

    return Response(
        content=_placeholder_svg(movie),
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )
