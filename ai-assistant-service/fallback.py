"""Deterministic fallback used when the LLM is unreachable or out of quota.

It picks a film from the real catalogue, finds a showtime and asks the reservation
engine for seats, so the conversation still ends with a useful, holdable proposal.
No language model is involved.
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

import tools as tools_module
from models import AssistantMessage, AssistantSession
from tools import AssistantTools, compact_movie
from utils import CINEMA_TZ, money, utcnow
from datetime import datetime

logger = logging.getLogger("ai-assistant-service.fallback")


def pick_count(text: str) -> int:
    match = re.search(
        r"(\d+)\s*(?:seats?|places?|people|persons?|tickets?|personnes?|billets?|رجال|مقاعد)",
        text,
        re.IGNORECASE,
    )
    if match:
        return max(1, min(8, int(match.group(1))))
    digits = re.findall(r"\b(\d+)\b", text)
    if digits:
        return max(1, min(8, int(digits[0])))
    return 2


def pick_date(text: str) -> str | None:
    today = datetime.now(CINEMA_TZ).date()
    lowered = text.lower()
    if any(word in lowered for word in ("tomorrow", "demain", "غدا")):
        return (today + timedelta(days=1)).isoformat()
    if any(word in lowered for word in ("today", "tonight", "ce soir", "aujourd'hui", "اليوم")):
        return today.isoformat()
    return None


def pick_category(text: str) -> str | None:
    """Seat class the guest asked for, so the fallback never proposes VIP for standard seats."""
    lowered = text.lower()
    if re.search(r"\b(?:no|not|don'?t|do not|without|sans)\b[^.]{0,20}\bvip\b", lowered):
        return "regular"
    if re.search(r"\bvvip\b", lowered):
        return "vvip"
    if re.search(r"\bvip\b", lowered):
        return "vip"
    if any(word in lowered for word in ("standard", "regular", "normal", "normale", "basique")):
        return "regular"
    return None


def pick_row(text: str) -> str | None:
    """Row the guest asked for ("row A", "line A", "rangée A", "A seats"), if any."""
    match = re.search(
        r"\b(?:row|line|rang[ée]e|rangee|صف|الصف)\s*([A-Za-z]{1,2})\b",
        text,
        re.IGNORECASE,
    )
    return match.group(1).upper() if match else None


def pick_movie(movies: list[dict], text: str) -> dict | None:
    if not movies:
        return None
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    best, best_score = None, 0
    for movie in movies:
        title_words = set(re.findall(r"[a-z0-9]+", str(movie.get("title", "")).lower()))
        score = len(title_words & words) * 4
        for genre in movie.get("genres") or []:
            if str(genre).lower() in text.lower():
                score += 3
        for mood in movie.get("moods") or []:
            if str(mood).lower() in text.lower():
                score += 3
        if score > best_score:
            best, best_score = movie, score
    return best or movies[0]


def preferred_showtime(showtimes: list[dict], text: str) -> dict | None:
    if not showtimes:
        return None
    lowered = text.lower()
    evening = any(word in lowered for word in ("evening", "tonight", "soir", "night", "nuit", "ليل"))
    afternoon = any(word in lowered for word in ("afternoon", "après-midi", "apres-midi", "بعد الزوال"))

    def hour(showtime: dict) -> int:
        try:
            return int(str(showtime.get("time", "00:00")).split(":")[0])
        except ValueError:
            return 0

    if evening:
        return next((s for s in showtimes if hour(s) >= 17), showtimes[0])
    if afternoon:
        return next((s for s in showtimes if 12 <= hour(s) < 17), showtimes[0])
    return showtimes[0]


def seats_reply(pending: dict) -> str:
    seats = ", ".join(seat.get("seat_id", "") for seat in pending.get("seats", []))
    movie = (pending.get("movie") or {}).get("title", "this film")
    when = " ".join(part for part in (pending.get("date"), pending.get("time")) if part)
    venue = " · ".join(part for part in (pending.get("cinema"), pending.get("hall")) if part)
    total = money(pending.get("total_price"), pending.get("currency", "MAD"))
    return (
        "The language model is unavailable right now, so I searched the booking engine directly. "
        f"I found {len(pending.get('seat_ids', []))} seat(s) for **{movie}**"
        + (f" on {when}" if when else "")
        + (f" at {venue}" if venue else "")
        + f": **{seats}** for {total}. "
        "Would you like me to hold them? Press **Hold these seats** to confirm — I never take payment myself."
    )


async def local_fallback(
    agent: AssistantTools, db: Session, chat_session: AssistantSession, text: str
) -> str:
    try:
        payload = await tools_module.gateway_request(
            "GET", "/movies", agent.token, params={"limit": 50, "now_showing": "true"}
        )
        movies = [compact_movie(item) for item in (payload or {}).get("items", [])]
        movie = pick_movie(movies, text)
        if movie is None:
            raise RuntimeError("The catalogue is empty.")

        params = {"date": pick_date(text)} if pick_date(text) else None
        showtime_payload = await tools_module.gateway_request(
            "GET", f"/movies/{movie['id']}/showtimes", agent.token, params=params
        )
        showtimes = (showtime_payload or {}).get("items", [])
        if not showtimes and params:
            showtime_payload = await tools_module.gateway_request(
                "GET", f"/movies/{movie['id']}/showtimes", agent.token
            )
            showtimes = (showtime_payload or {}).get("items", [])
        chosen = preferred_showtime(showtimes, text)
        if chosen is None:
            reply = (
                f"**{movie.get('title')}** has no upcoming showtime right now. "
                "Please pick another film or open the showtimes page."
            )
        else:
            result = await agent.suggest_seats(
                {
                    "showtime_id": chosen["id"],
                    "count": pick_count(text),
                    "category": pick_category(text) or "any",
                    "row": pick_row(text),
                }
            )
            pending = agent.session.pending
            if result.get("error") or not pending:
                reply = (
                    "I couldn't find available seats for that showtime: "
                    f"{result.get('error') or result.get('message') or 'no seats left'}. "
                    "Please try another showtime."
                )
            else:
                reply = seats_reply(pending)
    except Exception as exc:
        logger.warning("local fallback failed: %s", exc)
        reply = (
            "The assistant is unavailable at the moment. Manual booking still works: open a film, "
            "pick a date and showtime, then choose your seats on the map. Sorry for the inconvenience."
        )

    db.add(
        AssistantMessage(
            id=str(uuid4()),
            session_id=chat_session.id,
            role="assistant",
            content=reply,
            created_at=utcnow(),
        )
    )
    return reply
