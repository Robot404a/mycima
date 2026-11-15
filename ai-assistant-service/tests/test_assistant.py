"""Functional tests for the AI assistant service.

The Movie and Reservation services are replaced by a fake backend that returns
exactly the payloads the real services produce (see movie-service and
reservation-service), so the tool contracts are verified end to end.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

import agent as agent_module
import tools as tools_module
from db import SessionLocal
from models import AssistantSession
from utils import local_datetime_parts

MOVIE = {
    "id": 1,
    "slug": "inception",
    "title": "Inception",
    "release_year": 2010,
    "director": "Christopher Nolan",
    "cast": ["Leonardo DiCaprio"],
    "genres": ["Sci-Fi", "Thriller"],
    "moods": ["cerebral", "mind-bending"],
    "synopsis": "A thief steals secrets through dream-sharing technology.",
    "duration_minutes": 148,
    "rating": 8.4,
    "age_rating": "12+",
    "language": "English",
    "country": "United States",
    "poster_url": "/media/posters/inception.jpg",
    "is_now_showing": True,
}

SHOWTIME = {
    "id": 7,
    "movie_id": 1,
    "hall_id": 1,
    "starts_at": "2026-11-15T19:30:00Z",
    "price": 50.0,
    "price_cents": 5000,
    "currency": "MAD",
    "language": "VO",
    "format": "IMAX",
    "movie": {
        "id": 1,
        "slug": "inception",
        "title": "Inception",
        "release_year": 2010,
        "duration_minutes": 148,
        "genres": ["Sci-Fi"],
        "poster_url": "/media/posters/inception.jpg",
    },
    "hall": {
        "id": 1,
        "name": "Salle 1 - IMAX",
        "screen_type": "imax",
        "rows": 2,
        "seats_per_row": 10,
        "aisle_after": [4, 8],
        "total_seats": 20,
    },
    "cinema": {"id": 1, "name": "Megarama Casablanca", "city": "Casablanca"},
}


def seat_map() -> dict:
    seats = [
        {"label": f"{row}{number}", "row": row, "number": number, "status": "available", "mine": False}
        for row in ("A", "B")
        for number in range(1, 11)
    ]
    return {"showtime_id": 7, "price": 50.0, "rows": ["A", "B"], "seats_per_row": 10, "seats": seats}


class FakeBackend:
    """Stands in for the gateway -> movie/reservation hop."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.hold_calls: list[dict] = []
        self.hold_status = 201

    async def __call__(self, method, path, token, params=None, json_body=None, timeout=None):
        self.calls.append({"method": method, "path": path, "params": params, "json": json_body})

        if path == "/movies":
            return {"items": [MOVIE], "total": 1, "limit": 12, "offset": 0}
        if path == "/movies/1/showtimes":
            return {"items": [SHOWTIME], "total": 1}
        if path == "/showtimes/7":
            return SHOWTIME
        if path == "/showtimes/7/seats":
            return seat_map()
        if path == "/showtimes/7/suggest":
            count = int((params or {}).get("count", 2))
            return {
                "showtime_id": 7,
                "count": count,
                "suggestions": [
                    {"row": "A", "seats": [f"A{n}" for n in range(1, count + 1)], "score": 0.4},
                    {"row": "B", "seats": [f"B{n}" for n in range(1, count + 1)], "score": 1.9},
                ],
            }
        if path == "/holds" and method == "POST":
            if self.hold_status >= 400:
                from tools import ToolError

                raise ToolError({"message": "Some seats are no longer available."}, self.hold_status)
            self.hold_calls.append(json_body or {})
            return {
                "id": "11111111-2222-3333-4444-555555555555",
                "user_id": 1,
                "showtime_id": (json_body or {}).get("showtime_id"),
                "status": "active",
                "seats": (json_body or {}).get("seats"),
                "total": 50.0 * len((json_body or {}).get("seats") or []),
                "expires_at": "2026-11-15T20:00:00Z",
                "seconds_left": 600,
            }
        raise AssertionError(f"unexpected upstream call: {method} {path}")


def llm_script(*steps):
    """Build a fake LLM: each step is ("tool", name, args) or ("text", reply)."""
    remaining = list(steps)

    async def fake(messages, tools):
        step = remaining.pop(0) if remaining else ("text", "Anything else?")
        if step[0] == "tool":
            _, name, args = step
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": f"call_{uuid4().hex[:8]}",
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args)},
                    }
                ],
            }
        return {"role": "assistant", "content": step[1], "tool_calls": []}

    return fake


def llm_down():
    async def fake(messages, tools):
        raise RuntimeError("LLM unavailable (test-model: HTTP 503)")

    return fake


@pytest.fixture
def backend(monkeypatch):
    fake = FakeBackend()
    monkeypatch.setattr(tools_module, "gateway_request", fake)
    return fake


def chat(client, auth, message, session_id=None, user_id="1"):
    body = {"message": message}
    if session_id:
        body["session_id"] = session_id
    response = client.post("/assistant/chat", json=body, headers=auth(user_id))
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------------------ infrastructure


def test_health_reports_llm_and_database(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert body["llm_configured"] is True
    assert body["service"] == "ai-assistant-service"


def test_chat_requires_authentication(client):
    assert client.post("/assistant/chat", json={"message": "hello"}).status_code == 401


def test_chat_rejects_empty_message(client, auth):
    response = client.post("/assistant/chat", json={"message": "   "}, headers=auth())
    assert response.status_code == 422


# ------------------------------------------------------------------------- tools


def test_agent_searches_catalogue_through_gateway(client, auth, backend, monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "call_llm",
        llm_script(
            ("tool", "search_movies", {"query": "inception", "genre": "Sci-Fi"}),
            ("text", "Inception is playing tonight."),
        ),
    )
    body = chat(client, auth, "something sci-fi please")

    movie_call = backend.calls[0]
    assert movie_call["path"] == "/movies"
    assert movie_call["params"]["genre"] == "Sci-Fi"
    assert movie_call["params"]["q"] == "inception"
    assert movie_call["params"]["now_showing"] == "true"
    assert body["reply"] == "Inception is playing tonight."
    assert body["session_id"]


def test_showtime_tool_uses_movie_service_payload(backend):
    import asyncio

    from models import AssistantSession
    from tools import AssistantTools
    from utils import local_datetime_parts

    with SessionLocal() as db:
        session = AssistantSession(id=str(uuid4()), user_id="1", title="showtimes")
        db.add(session)
        db.commit()
        toolset = AssistantTools(db, session, "Bearer test-token", "")
        result = asyncio.run(toolset.get_showtimes({"movie_id": 1}))

    assert result["count"] == 1
    showtime = result["showtimes"][0]
    expected_date, expected_time = local_datetime_parts(SHOWTIME["starts_at"])
    assert showtime["date"] == expected_date
    assert showtime["time"] == expected_time
    assert showtime["cinema"] == "Megarama Casablanca"
    assert showtime["hall"] == "Salle 1 - IMAX"
    assert showtime["price_display"] == "50.00 MAD"
    assert showtime["movie_title"] == "Inception"


def test_suggest_seats_builds_pending_confirmation(client, auth, backend, monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "call_llm",
        llm_script(
            ("tool", "suggest_seats", {"showtime_id": 7, "count": 2}),
            ("text", "I suggest A1 and A2 for 100.00 MAD."),
        ),
    )
    body = chat(client, auth, "2 seats for inception tonight")

    assert body["pending_confirmation"] is not None
    pending = body["pending_confirmation"]
    assert pending["seat_ids"] == ["A1", "A2"]
    assert pending["total_price"] == 100.0
    assert pending["currency"] == "MAD"
    assert pending["cinema"] == "Megarama Casablanca"
    expected_date, expected_time = local_datetime_parts(SHOWTIME["starts_at"])
    assert pending["date"] == expected_date
    assert pending["time"] == expected_time
    assert len(pending["suggestions"]) == 2


def test_hold_requires_explicit_confirmation(client, auth, backend, monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "call_llm",
        llm_script(
            ("tool", "suggest_seats", {"showtime_id": 7, "count": 2}),
            ("text", "Shall I hold A1 and A2?"),
        ),
    )
    first = chat(client, auth, "2 seats for inception")

    # Second turn: the model tries to hold although the guest only said "maybe later".
    monkeypatch.setattr(
        agent_module,
        "call_llm",
        llm_script(
            ("tool", "hold_seats", {"showtime_id": 7, "seat_ids": ["A1", "A2"], "confirm": True}),
            ("text", "Tell me when you are ready."),
        ),
    )
    second = chat(client, auth, "maybe later", session_id=first["session_id"])

    assert backend.hold_calls == []
    assert second["hold"] is None
    assert second["pending_confirmation"]["seat_ids"] == ["A1", "A2"]


def test_hold_succeeds_after_confirmation(client, auth, backend, monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "call_llm",
        llm_script(
            ("tool", "suggest_seats", {"showtime_id": 7, "count": 2}),
            ("text", "Shall I hold A1 and A2?"),
        ),
    )
    first = chat(client, auth, "2 seats for inception")

    monkeypatch.setattr(
        agent_module,
        "call_llm",
        llm_script(
            ("tool", "hold_seats", {"showtime_id": 7, "seat_ids": ["A1", "A2"], "confirm": True}),
            ("text", "Held. Please press Confirm and pay."),
        ),
    )
    second = chat(client, auth, "yes, hold them", session_id=first["session_id"])

    assert backend.hold_calls == [{"showtime_id": 7, "seats": ["A1", "A2"]}]
    assert second["hold"]["seats"] == ["A1", "A2"]
    assert second["hold"]["total_price"] == 100.0
    assert second["pending_confirmation"] is None


def test_hold_rejects_seats_not_offered(client, auth, backend, monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "call_llm",
        llm_script(
            ("tool", "suggest_seats", {"showtime_id": 7, "count": 2}),
            ("text", "I suggest A1 and A2."),
        ),
    )
    first = chat(client, auth, "2 seats for inception")

    monkeypatch.setattr(
        agent_module,
        "call_llm",
        llm_script(
            ("tool", "hold_seats", {"showtime_id": 7, "seat_ids": ["A9"], "confirm": True}),
            ("text", "Those seats are not available."),
        ),
    )
    second = chat(client, auth, "yes", session_id=first["session_id"])

    assert backend.hold_calls == []
    assert second["hold"] is None


def test_confirm_hold_endpoint_holds_pending_seats(client, auth, backend, monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "call_llm",
        llm_script(
            ("tool", "suggest_seats", {"showtime_id": 7, "count": 3}),
            ("text", "Shall I hold A1, A2 and A3?"),
        ),
    )
    first = chat(client, auth, "3 seats for inception")

    response = client.post(
        "/assistant/confirm-hold",
        json={"session_id": first["session_id"]},
        headers=auth(),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["hold"]["seats"] == ["A1", "A2", "A3"]
    assert backend.hold_calls[-1]["seats"] == ["A1", "A2", "A3"]

    # the proposal is consumed
    detail = client.get(f"/assistant/sessions/{first['session_id']}", headers=auth()).json()
    assert detail["pending_confirmation"] is None
    assert detail["last_hold"]["seats"] == ["A1", "A2", "A3"]


def test_confirm_hold_reports_conflict(client, auth, backend, monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "call_llm",
        llm_script(
            ("tool", "suggest_seats", {"showtime_id": 7, "count": 2}),
            ("text", "Shall I hold these?"),
        ),
    )
    first = chat(client, auth, "2 seats")

    backend.hold_status = 409
    response = client.post(
        "/assistant/confirm-hold",
        json={"session_id": first["session_id"]},
        headers=auth(),
    )
    assert response.status_code == 409
    detail = client.get(f"/assistant/sessions/{first['session_id']}", headers=auth()).json()
    assert detail["pending_confirmation"] is None


def test_expired_proposal_returns_410(client, auth, backend, monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "call_llm",
        llm_script(
            ("tool", "suggest_seats", {"showtime_id": 7, "count": 2}),
            ("text", "Shall I hold these?"),
        ),
    )
    first = chat(client, auth, "2 seats")

    with SessionLocal() as session:
        stored = session.get(AssistantSession, first["session_id"])
        pending = dict(stored.pending)
        pending["proposal_expires_at"] = "2020-01-01T00:00:00+00:00"
        stored.pending = pending
        session.add(stored)
        session.commit()

    response = client.post(
        "/assistant/confirm-hold",
        json={"session_id": first["session_id"]},
        headers=auth(),
    )
    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "PROPOSAL_EXPIRED"


# ---------------------------------------------------------------- topic guard


def test_off_topic_message_is_refused_without_calling_the_agent(client, auth, backend, monkeypatch):
    import guard

    async def refuse(messages, tools=None, temperature=None, max_tokens=None):
        return {"role": "assistant", "content": "REFUSE"}

    monkeypatch.setattr(guard, "complete", refuse)

    async def forbidden(messages, tools):
        raise AssertionError("the booking agent must not answer off-topic messages")

    monkeypatch.setattr(agent_module, "call_llm", forbidden)

    body = chat(client, auth, "What was the result of World War 2?", user_id="601")

    assert body["refused"] is True
    assert "cinema" in body["reply"].lower()
    assert "1945" not in body["reply"]
    assert body["pending_confirmation"] is None
    assert backend.calls == []


def test_off_topic_refusal_is_topic_independent(client, auth, backend, monkeypatch):
    import guard

    async def refuse(messages, tools=None, temperature=None, max_tokens=None):
        return {"content": "REFUSE"}

    monkeypatch.setattr(guard, "complete", refuse)

    async def forbidden(messages, tools):
        raise AssertionError("agent must not be called")

    monkeypatch.setattr(agent_module, "call_llm", forbidden)

    for index, question in enumerate(
        ["Can you write me a Python quicksort?", "Who won the 2018 World Cup?", "Give me a recipe for tagine"]
    ):
        body = chat(client, auth, question, user_id=f"61{index}")
        assert body["refused"] is True, question
        assert "cinema" in body["reply"].lower()


def test_booking_message_skips_the_guard(client, auth, backend, monkeypatch):
    import guard

    async def boom(*args, **kwargs):
        raise AssertionError("the guard must not classify obvious booking talk")

    monkeypatch.setattr(guard, "complete", boom)
    monkeypatch.setattr(agent_module, "call_llm", llm_script(("text", "Inception is showing tonight.")))

    body = chat(client, auth, "2 seats for inception tonight", user_id="602")

    assert body["refused"] is False
    assert body["reply"] == "Inception is showing tonight."


def test_guard_failure_fails_open(client, auth, backend, monkeypatch):
    import guard

    async def boom(*args, **kwargs):
        raise RuntimeError("guard down")

    monkeypatch.setattr(guard, "complete", boom)
    monkeypatch.setattr(agent_module, "call_llm", llm_script(("text", "Happy to help with your booking.")))

    body = chat(client, auth, "Explain the history of ancient Rome", user_id="603")

    assert body["refused"] is False
    assert "booking" in body["reply"].lower()


def test_guard_parses_classifier_answers(monkeypatch):
    """An empty or odd classifier answer must never block a guest (fail open)."""
    import asyncio

    import guard

    async def refuse(messages, tools=None, temperature=None, max_tokens=None):
        return {"content": " REFUSE.\n"}

    async def allow(messages, tools=None, temperature=None, max_tokens=None):
        return {"content": "ALLOW"}

    async def empty(messages, tools=None, temperature=None, max_tokens=None):
        return {"content": ""}

    monkeypatch.setattr(guard, "complete", refuse)
    assert asyncio.run(guard.classify("What was the result of World War 2?")) is False

    monkeypatch.setattr(guard, "complete", allow)
    assert asyncio.run(guard.classify("Who won the 2018 World Cup?")) is True

    monkeypatch.setattr(guard, "complete", empty)
    assert asyncio.run(guard.classify("Who won the 2018 World Cup?")) is None
    assert asyncio.run(guard.check_topic("Who won the 2018 World Cup?")) is True


def test_guard_fast_allow_rules():
    from guard import looks_on_topic

    assert looks_on_topic("2 seats for Inception tonight")
    assert looks_on_topic("yes, hold them", has_pending=True)
    assert looks_on_topic("hello")
    assert not looks_on_topic("What was the result of World War 2?")
    assert not looks_on_topic("Can you write me a Python quicksort?")


def test_agent_summarizes_when_iteration_cap_is_reached(client, auth, backend, monkeypatch):
    """Tool-happy models must still end with an answer instead of the fallback."""
    steps = [("tool", "search_movies", {"query": "inception"}) for _ in range(5)]
    steps.append(("text", "Here is what I found for Inception."))
    monkeypatch.setattr(agent_module, "call_llm", llm_script(*steps))

    body = chat(client, auth, "find inception", user_id="604")

    assert body["reply"] == "Here is what I found for Inception."
    assert "language model is unavailable" not in body["reply"]


def test_showtimes_empty_result_carries_a_retry_hint(backend):
    import asyncio

    from models import AssistantSession
    from tools import AssistantTools

    async def empty_showtimes(method, path, token, params=None, json_body=None, timeout=None):
        return {"items": [], "total": 0}

    import tools as tools_module

    original = tools_module.gateway_request
    tools_module.gateway_request = empty_showtimes
    try:
        with SessionLocal() as db:
            session = AssistantSession(id=str(uuid4()), user_id="1", title="empty")
            db.add(session)
            db.commit()
            toolset = AssistantTools(db, session, "Bearer token", "")
            result = asyncio.run(toolset.get_showtimes({"movie_id": 1, "cinema_id": 99}))
    finally:
        tools_module.gateway_request = original

    assert result["count"] == 0
    assert "Retry without" in result["instruction"]


# --------------------------------------------------------------------- fallback


def test_local_fallback_when_llm_is_down(client, auth, backend, monkeypatch):
    monkeypatch.setattr(agent_module, "call_llm", llm_down())
    body = chat(client, auth, "2 seats for a sci-fi film tomorrow")

    assert "language model is unavailable" in body["reply"]
    assert "Inception" in body["reply"]
    assert "A1, A2" in body["reply"]
    assert body["pending_confirmation"]["seat_ids"] == ["A1", "A2"]
    # the fallback used the real catalogue + suggestion endpoints, never a fabricated movie
    paths = [call["path"] for call in backend.calls]
    assert "/movies" in paths and "/showtimes/7/suggest" in paths


# --------------------------------------------------------------------- sessions


def test_sessions_are_private(client, auth, backend, monkeypatch):
    monkeypatch.setattr(agent_module, "call_llm", llm_script(("text", "Hello, how can I help?")))
    body = chat(client, auth, "hello", user_id="501")

    assert client.get(f"/assistant/sessions/{body['session_id']}", headers=auth("502")).status_code == 404
    assert client.get(f"/assistant/sessions/{body['session_id']}", headers=auth("501")).status_code == 200


def test_session_history_and_delete(client, auth, backend, monkeypatch):
    monkeypatch.setattr(agent_module, "call_llm", llm_script(("text", "First answer.")))
    body = chat(client, auth, "first question", user_id="503")

    detail = client.get(f"/assistant/sessions/{body['session_id']}", headers=auth("503")).json()
    roles = [message["role"] for message in detail["messages"]]
    assert roles == ["user", "assistant"]
    assert detail["messages"][0]["content"] == "first question"

    listing = client.get("/assistant/sessions", headers=auth("503")).json()
    assert any(item["id"] == body["session_id"] for item in listing["items"])

    assert client.delete(f"/assistant/sessions/{body['session_id']}", headers=auth("503")).status_code == 204
    assert client.get(f"/assistant/sessions/{body['session_id']}", headers=auth("503")).status_code == 404


def test_history_normalization_keeps_valid_tool_window():
    from agent import normalize_history

    messages = [
        {"role": "system", "content": "system"},
        {"role": "tool", "tool_call_id": "orphan", "name": "x", "content": "{}"},
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "x", "arguments": "{}"}}],
        },
        {"role": "tool", "tool_call_id": "call_1", "name": "x", "content": "{}"},
        {"role": "assistant", "content": "answer"},
    ]
    cleaned = normalize_history(messages)
    assert [message["role"] for message in cleaned] == ["system", "user", "assistant", "tool", "assistant"]
