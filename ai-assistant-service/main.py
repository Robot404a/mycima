"""MyCima AI Assistant Service.

The chatbot backend. It keeps conversation history per session, asks an
OpenAI-compatible LLM which tool to call, executes those tools against the real
Movie and Reservation services through the API gateway, and returns a reply plus
the structured seat proposal/hold the frontend can highlight.

The LLM never touches the database and never pays: it can only hold seats, and
only after the guest explicitly confirms.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

import tools as tools_module
from agent import run_agent
from config import settings
from db import check_db, engine, get_db, init_models
from fallback import local_fallback
from guard import OFF_TOPIC_REPLY, check_topic
from llm import PREFERRED_MODEL, is_configured
from models import AssistantMessage, AssistantSession
from security import current_user
from shared.logging_config import RequestLogMiddleware, configure_logging
from tools import AssistantTools, ToolError, compact_hold, pending_is_fresh, public_hold, public_pending
from utils import iso, utcnow

SERVICE = settings.service_name
logger = configure_logging(SERVICE)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=36)


class ConfirmHoldRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=36)


def get_session_for_user(db: Session, session_id: str, user_id: str) -> AssistantSession:
    chat_session = db.get(AssistantSession, session_id)
    if not chat_session or str(chat_session.user_id) != str(user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return chat_session


def message_dict(message: AssistantMessage) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "name": message.name,
        "created_at": iso(message.created_at) if message.created_at else None,
    }


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("starting", extra={"event": "service.start"})
    init_models()
    yield
    engine.dispose()
    logger.info("stopped", extra={"event": "service.stop"})


app = FastAPI(
    title="MyCima AI Assistant Service",
    description=(
        "Conversational booking assistant: discovers films and showtimes through the Movie "
        "service, suggests and holds seats through the Reservation service, and never pays."
    ),
    version="2.0.0",
    lifespan=lifespan,
)
app.add_middleware(RequestLogMiddleware, service=SERVICE, logger=logger)


@app.get("/health", tags=["meta"])
def health() -> dict:
    db_ok = check_db()
    return {
        "status": "ok" if db_ok else "degraded",
        "service": SERVICE,
        "database": "up" if db_ok else "down",
        "llm_configured": is_configured(),
        "llm_model": PREFERRED_MODEL,
        "llm_models": settings.models,
        "gateway": settings.gateway_url,
        "timestamp": time.time(),
    }


@app.post("/assistant/chat", tags=["assistant"], summary="Send a message to the booking assistant")
async def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(current_user),
    authorization: str | None = Header(default=None),
) -> dict:
    token = authorization or ""
    text = payload.message.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Write a message first.")

    user_id = str(user["id"])
    if payload.session_id:
        chat_session = get_session_for_user(db, payload.session_id, user_id)
    else:
        chat_session = AssistantSession(id=str(uuid4()), user_id=user_id, title=text[:80])
        db.add(chat_session)
        db.flush()

    if not chat_session.title:
        chat_session.title = text[:80]
    chat_session.updated_at = utcnow()
    db.add(
        AssistantMessage(
            id=str(uuid4()),
            session_id=chat_session.id,
            role="user",
            content=text,
            created_at=utcnow(),
        )
    )
    db.flush()

    history = list(
        reversed(
            db.scalars(
                select(AssistantMessage)
                .where(AssistantMessage.session_id == chat_session.id)
                .order_by(AssistantMessage.created_at.desc())
                .limit(settings.history_limit)
            ).all()
        )
    )
    if not pending_is_fresh(chat_session.pending):
        chat_session.pending = {}

    # Topic guard: refused messages never reach the answering agent.
    previous = [item for item in history[:-1] if item.role in {"user", "assistant"}]
    recent_context = "\n".join(
        f"{item.role}: {(item.content or '').strip()[:300]}" for item in previous[-4:]
    )
    if not await check_topic(text, recent_context, bool(chat_session.pending)):
        logger.info("off-topic message refused", extra={"event": "assistant.refused"})
        chat_session.updated_at = utcnow()
        db.add(
            AssistantMessage(
                id=str(uuid4()),
                session_id=chat_session.id,
                role="assistant",
                content=OFF_TOPIC_REPLY,
                created_at=utcnow(),
            )
        )
        db.add(chat_session)
        db.commit()
        db.refresh(chat_session)
        return {
            "session_id": chat_session.id,
            "reply": OFF_TOPIC_REPLY,
            "pending_confirmation": public_pending(chat_session.pending),
            "hold": None,
            "status": "ok",
            "refused": True,
            "llm": "not_used",
        }

    tools = AssistantTools(db, chat_session, token, text)
    reply = await run_agent(db, chat_session, tools, text, history)
    if reply is None:
        reply = await local_fallback(tools, db, chat_session, text)

    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)

    return {
        "session_id": chat_session.id,
        "reply": reply,
        "pending_confirmation": public_pending(chat_session.pending),
        "hold": public_hold(tools.created_hold),
        "status": "ok",
        "refused": False,
        "llm": "unavailable" if reply and "language model is unavailable" in reply else "used",
    }


@app.post(
    "/assistant/confirm-hold",
    tags=["assistant"],
    summary="Hold the seats of the current proposal (used by the seat map's confirm button)",
)
async def confirm_hold(
    payload: ConfirmHoldRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(current_user),
    authorization: str | None = Header(default=None),
) -> dict:
    token = authorization or ""
    chat_session = get_session_for_user(db, payload.session_id, str(user["id"]))
    pending = chat_session.pending or {}

    if not pending_is_fresh(pending):
        if pending:
            chat_session.pending = {}
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "code": "PROPOSAL_EXPIRED",
                "message": "This seat suggestion has expired. Ask the assistant for new seats.",
            },
        )

    try:
        hold = await tools_module.gateway_request(
            "POST",
            "/holds",
            token,
            json_body={
                "showtime_id": int(pending["showtime_id"]),
                "seats": pending.get("seat_ids", []),
            },
            timeout=30.0,
        )
    except ToolError as exc:
        if exc.status_code == 409:
            chat_session.pending = {}
            db.commit()
        raise HTTPException(
            status_code=exc.status_code if exc.status_code >= 400 else 502, detail=exc.detail
        )

    compact = compact_hold(hold, pending)
    chat_session.pending = {}
    chat_session.last_hold = compact
    chat_session.updated_at = utcnow()

    seats = ", ".join(compact.get("seats", []))
    movie = (compact.get("movie") or {}).get("title") or "your film"
    message = (
        f"Held {seats} for {movie} · {compact.get('date', '')} {compact.get('time', '')}. "
        "Press Confirm and pay before the countdown ends. I cannot take payment."
    )
    db.add(
        AssistantMessage(
            id=str(uuid4()),
            session_id=chat_session.id,
            role="assistant",
            content=message,
            created_at=utcnow(),
        )
    )
    db.commit()
    return {"hold": public_hold(compact), "message": message}


@app.get("/assistant/sessions", tags=["assistant"])
def list_sessions(
    db: Session = Depends(get_db),
    user: dict = Depends(current_user),
    limit: int = Query(default=20, ge=1, le=50),
) -> dict:
    sessions = db.scalars(
        select(AssistantSession)
        .where(AssistantSession.user_id == str(user["id"]))
        .order_by(AssistantSession.updated_at.desc())
        .limit(limit)
    ).all()
    return {
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "updated_at": iso(item.updated_at),
                "created_at": iso(item.created_at),
            }
            for item in sessions
        ]
    }


@app.get("/assistant/sessions/{session_id}", tags=["assistant"])
def get_session_messages(
    session_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(current_user),
) -> dict:
    chat_session = get_session_for_user(db, session_id, str(user["id"]))
    messages = db.scalars(
        select(AssistantMessage)
        .where(AssistantMessage.session_id == session_id, AssistantMessage.role.in_(["user", "assistant"]))
        .order_by(AssistantMessage.created_at)
    ).all()
    return {
        "id": chat_session.id,
        "title": chat_session.title,
        "messages": [message_dict(item) for item in messages],
        "pending_confirmation": public_pending(chat_session.pending),
        "last_hold": public_hold(chat_session.last_hold),
    }


@app.delete("/assistant/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["assistant"])
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(current_user),
) -> Response:
    chat_session = get_session_for_user(db, session_id, str(user["id"]))
    db.delete(chat_session)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
