"""Tools of the assistant.

Each tool is a thin, typed wrapper over the real platform APIs, always called through
the gateway with the guest's own token:

- Movie service:      GET /movies, GET /movies/{id}/showtimes, GET /showtimes/{id}
- Reservation service: GET /showtimes/{id}/seats, GET /showtimes/{id}/suggest, POST /holds
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy.orm import Session

from config import settings
from models import AssistantSession
from utils import explicit_confirmation, iso, local_datetime_parts, money, parse_iso, utcnow

logger = logging.getLogger("ai-assistant-service.tools")


class ToolError(Exception):
    def __init__(self, detail, status_code: int = 502):
        self.detail = detail
        self.status_code = status_code
        super().__init__(str(detail))

    def public_message(self) -> str:
        if isinstance(self.detail, dict):
            return str(
                self.detail.get("message")
                or self.detail.get("detail")
                or json.dumps(self.detail, ensure_ascii=False)
            )
        return str(self.detail)


def _detail_of(response: httpx.Response) -> Any:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:400] or "The request failed."
    detail = payload.get("detail") if isinstance(payload, dict) else payload
    return detail or payload


async def gateway_request(
    method: str,
    path: str,
    token: str,
    params: dict | None = None,
    json_body: dict | None = None,
    timeout: float | None = None,
):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = token if token.lower().startswith("bearer ") else f"Bearer {token}"
    url = settings.gateway_url + path
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout or settings.gateway_timeout_seconds, connect=5.0)
        ) as client:
            response = await client.request(method, url, params=params, json=json_body, headers=headers)
    except httpx.HTTPError as exc:
        raise ToolError(f"The booking platform is temporarily unreachable ({type(exc).__name__}).", 503) from exc

    if response.status_code >= 400:
        raise ToolError(_detail_of(response), response.status_code)
    if response.status_code == 204 or not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text[:1000]}


def compact_movie(item: dict) -> dict:
    synopsis = str(item.get("synopsis") or "")
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "release_year": item.get("release_year"),
        "director": item.get("director"),
        "genres": item.get("genres", []),
        "moods": item.get("moods", []),
        "rating": item.get("rating"),
        "duration_min": item.get("duration_minutes"),
        "age_rating": item.get("age_rating"),
        "language": item.get("language"),
        "poster_url": item.get("poster_url"),
        "synopsis": (synopsis[:240] + "…") if len(synopsis) > 240 else synopsis,
    }


def compact_showtime(item: dict) -> dict:
    date, time = local_datetime_parts(item.get("starts_at"))
    hall = item.get("hall") or {}
    cinema = item.get("cinema") or {}
    movie = item.get("movie") or {}
    return {
        "id": item.get("id"),
        "starts_at": item.get("starts_at"),
        "date": date,
        "time": time,
        "movie_id": item.get("movie_id") or movie.get("id"),
        "movie_title": movie.get("title"),
        "cinema": cinema.get("name"),
        "city": cinema.get("city"),
        "hall": hall.get("name"),
        "format": item.get("format"),
        "language": item.get("language"),
        "price": item.get("price"),
        "price_display": money(item.get("price"), item.get("currency") or "MAD"),
        "currency": item.get("currency") or "MAD",
    }


def pending_is_fresh(pending: dict | None) -> bool:
    if not pending:
        return False
    expiry = parse_iso(str(pending.get("proposal_expires_at") or ""))
    return bool(expiry and expiry > utcnow())


def public_pending(pending: dict | None) -> dict | None:
    if not pending_is_fresh(pending):
        return None
    keys = (
        "showtime_id",
        "seat_ids",
        "suggestions",
        "seats",
        "price_per_seat",
        "total_price",
        "currency",
        "movie",
        "cinema",
        "hall",
        "starts_at",
        "date",
        "time",
        "format",
        "proposal_expires_at",
    )
    return {key: pending.get(key) for key in keys}


def public_hold(hold: dict | None) -> dict | None:
    if not hold:
        return None
    keys = (
        "id",
        "showtime_id",
        "seats",
        "total_price",
        "currency",
        "expires_at",
        "seconds_left",
        "movie",
        "cinema",
        "hall",
        "starts_at",
        "date",
        "time",
        "format",
    )
    return {key: hold.get(key) for key in keys}


class AssistantTools:
    """The five tools, bound to one conversation and one guest token."""

    def __init__(self, db: Session, chat_session: AssistantSession, token: str, latest_text: str):
        self.db = db
        self.session = chat_session
        self.token = token
        self.latest_text = latest_text or ""
        self.created_hold: dict | None = None

    async def execute(self, name: str, arguments: dict) -> dict:
        handlers = {
            "search_movies": self.search_movies,
            "get_showtimes": self.get_showtimes,
            "get_seat_availability": self.get_seat_availability,
            "suggest_seats": self.suggest_seats,
            "hold_seats": self.hold_seats,
        }
        handler = handlers.get(name)
        if handler is None:
            return {"error": f"Unknown tool '{name}'."}
        try:
            return await handler(arguments)
        except ToolError as exc:
            return {"error": exc.public_message(), "status_code": exc.status_code}
        except (TypeError, ValueError) as exc:
            return {"error": f"Invalid arguments: {exc}"}
        except Exception as exc:  # never break the conversation on a tool bug
            logger.exception("tool %s failed", name)
            return {"error": f"The tool could not complete: {exc}"}

    # ------------------------------------------------------------------ search
    async def search_movies(self, args: dict) -> dict:
        params: dict[str, Any] = {"limit": 12, "now_showing": "true"}
        if args.get("query"):
            params["q"] = str(args["query"])[:120]
        if args.get("genre"):
            params["genre"] = str(args["genre"])[:60]
        if args.get("mood"):
            params["mood"] = str(args["mood"])[:60]
        if args.get("date"):
            params["date"] = str(args["date"])[:10]
        payload = await gateway_request("GET", "/movies", self.token, params=params)
        items = [compact_movie(item) for item in (payload or {}).get("items", [])]
        return {"movies": items, "count": len(items), "total": (payload or {}).get("total", len(items))}

    # ---------------------------------------------------------------- showtimes
    async def get_showtimes(self, args: dict) -> dict:
        movie_id = int(args.get("movie_id"))
        params: dict[str, Any] = {}
        if args.get("date"):
            params["date"] = str(args["date"])[:10]
        if args.get("cinema_id"):
            params["cinema_id"] = int(args["cinema_id"])
        payload = await gateway_request(
            "GET", f"/movies/{movie_id}/showtimes", self.token, params=params or None
        )
        raw_items = (payload or {}).get("items", [])
        showtimes = [compact_showtime(item) for item in raw_items][:20]
        movie = raw_items[0].get("movie") if raw_items else None
        result = {
            "movie": compact_movie(movie) if movie else {"id": movie_id},
            "showtimes": showtimes,
            "count": len(showtimes),
        }
        if not showtimes:
            result["instruction"] = (
                "No showtime matched those filters. Retry without the date or cinema filter, "
                "then pick from the returned showtimes."
            )
        return result

    # -------------------------------------------------------------- availability
    async def get_seat_availability(self, args: dict) -> dict:
        showtime_id = int(args.get("showtime_id"))
        seat_map = await gateway_request("GET", f"/showtimes/{showtime_id}/seats", self.token)
        showtime = await self._showtime(showtime_id)
        seats = (seat_map or {}).get("seats", [])
        available = sum(1 for seat in seats if seat.get("status") == "available")
        held = sum(1 for seat in seats if seat.get("status") == "held")
        booked = sum(1 for seat in seats if seat.get("status") == "booked")
        return {
            "showtime": compact_showtime(showtime or {}),
            "total_seats": len(seats),
            "available": available,
            "held": held,
            "booked": booked,
            "price": (seat_map or {}).get("price"),
            "price_display": money((seat_map or {}).get("price"), (showtime or {}).get("currency", "MAD")),
        }

    # ---------------------------------------------------------------- suggest
    async def suggest_seats(self, args: dict) -> dict:
        showtime_id = int(args.get("showtime_id"))
        count = max(1, min(settings.max_seats_per_hold, int(args.get("count", 2))))

        seat_map = await gateway_request("GET", f"/showtimes/{showtime_id}/seats", self.token)
        suggestion = await gateway_request(
            "GET", f"/showtimes/{showtime_id}/suggest", self.token, params={"count": count}
        )
        showtime = await self._showtime(showtime_id)

        groups = (suggestion or {}).get("suggestions", [])
        if not groups:
            return {
                "status": "no_seats",
                "message": (
                    f"No {count} adjacent seats are available for this showtime. "
                    "Offer another showtime or a smaller group."
                ),
            }

        price = (seat_map or {}).get("price") or (showtime or {}).get("price")
        currency = (showtime or {}).get("currency") or "MAD"
        date, time = local_datetime_parts((showtime or {}).get("starts_at"))
        movie = (showtime or {}).get("movie") or {}
        hall = (showtime or {}).get("hall") or {}
        cinema = (showtime or {}).get("cinema") or {}

        suggestions = [
            {"row": group.get("row"), "seats": group.get("seats", []), "score": group.get("score")}
            for group in groups
        ]
        primary = suggestions[0]
        try:
            total = round(float(price) * count, 2) if price is not None else None
        except (TypeError, ValueError):
            total = None

        pending = {
            "showtime_id": showtime_id,
            "seat_ids": primary["seats"],
            "suggestions": suggestions,
            "seats": [{"seat_id": label, "category": hall.get("screen_type")} for label in primary["seats"]],
            "price_per_seat": price,
            "total_price": total,
            "currency": currency,
            "movie": {"id": movie.get("id"), "title": movie.get("title"), "poster_url": movie.get("poster_url")},
            "cinema": cinema.get("name"),
            "hall": hall.get("name"),
            "starts_at": (showtime or {}).get("starts_at"),
            "date": date,
            "time": time,
            "format": (showtime or {}).get("format"),
            "proposal_expires_at": iso(
                utcnow() + timedelta(minutes=settings.proposal_ttl_minutes)
            ),
        }
        self.session.pending = pending
        self.db.add(self.session)

        return {
            "status": "seats_suggested",
            "suggestions": suggestions,
            "seats": primary["seats"],
            "count": count,
            "price_per_seat": price,
            "price_per_seat_display": money(price, currency),
            "total_price": total,
            "total_display": money(total, currency),
            "currency": currency,
            "showtime": {
                "id": showtime_id,
                "movie": pending["movie"],
                "cinema": pending["cinema"],
                "hall": pending["hall"],
                "date": date,
                "time": time,
                "format": pending["format"],
            },
            "confirmation_required": True,
            "instruction": (
                "Present the seats (and the alternative groups if useful) and ask the guest to "
                "confirm. Only after an explicit yes may you call hold_seats with confirm=true "
                "for one of these exact groups."
            ),
        }

    # ------------------------------------------------------------------- hold
    async def hold_seats(self, args: dict) -> dict:
        pending = self.session.pending or {}
        if not pending_is_fresh(pending):
            return {
                "status": "no_pending_seats",
                "message": "No fresh seat suggestion exists. Call suggest_seats first and ask the guest.",
            }

        showtime_id = int(args.get("showtime_id") or pending.get("showtime_id"))
        if showtime_id != int(pending.get("showtime_id")):
            return {
                "status": "different_showtime",
                "message": "Those seats belong to another showtime. Call suggest_seats for this showtime.",
            }

        requested = [str(seat).strip().upper() for seat in (args.get("seat_ids") or [])]
        groups = [list(group.get("seats", [])) for group in pending.get("suggestions", [])]
        if not groups:
            groups = [list(pending.get("seat_ids", []))]
        match = next((group for group in groups if set(group) == set(requested)), None)
        if not requested or match is None:
            return {
                "status": "seat_mismatch",
                "message": "Only the exact seat groups returned by suggest_seats can be held.",
                "suggested_groups": groups,
            }

        if not bool(args.get("confirm")) or not explicit_confirmation(self.latest_text):
            return {
                "status": "confirmation_required",
                "message": (
                    "The guest has not explicitly confirmed in this message. Ask a short yes/no "
                    "question and do not hold yet."
                ),
                "seats": match,
                "total_price": pending.get("total_price"),
                "total_display": money(pending.get("total_price"), pending.get("currency", "MAD")),
            }

        hold = await gateway_request(
            "POST",
            "/holds",
            self.token,
            json_body={"showtime_id": showtime_id, "seats": match},
            timeout=30.0,
        )
        compact = compact_hold(hold, pending)
        self.session.pending = {}
        self.session.last_hold = compact
        self.created_hold = compact
        self.db.add(self.session)
        return {
            "status": "held",
            "hold": compact,
            "instruction": (
                "Tell the guest the seats are held and that they must press Confirm and pay before "
                "the countdown ends. You cannot pay for them."
            ),
        }

    # --------------------------------------------------------------- helpers
    async def _showtime(self, showtime_id: int) -> dict:
        return await gateway_request("GET", f"/showtimes/{showtime_id}", self.token) or {}


def compact_hold(hold: dict, pending: dict) -> dict:
    """Normalize a reservation hold, enriched with the movie/showtime context we already know."""
    total = (hold or {}).get("total")
    currency = pending.get("currency", "MAD")
    movie = pending.get("movie") or {}
    date, time = local_datetime_parts(pending.get("starts_at"))
    return {
        "id": (hold or {}).get("id"),
        "showtime_id": (hold or {}).get("showtime_id"),
        "seats": (hold or {}).get("seats", []),
        "total_price": total,
        "currency": currency,
        "expires_at": (hold or {}).get("expires_at"),
        "seconds_left": (hold or {}).get("seconds_left"),
        "movie": movie,
        "cinema": pending.get("cinema"),
        "hall": pending.get("hall"),
        "starts_at": pending.get("starts_at"),
        "date": date,
        "time": time,
        "format": pending.get("format"),
    }
