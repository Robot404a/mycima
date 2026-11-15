"""The agent loop: ask the LLM, run the tools it chooses, persist the exchange."""

from __future__ import annotations

import json
import logging
from uuid import uuid4

from sqlalchemy.orm import Session

from config import settings
from llm import call_llm
from models import AssistantMessage, AssistantSession
from prompts import TOOLS, system_prompt
from tools import AssistantTools, pending_is_fresh, public_pending
from utils import utcnow

logger = logging.getLogger("ai-assistant-service.agent")


def history_to_messages(history: list[AssistantMessage], pending: dict | None) -> list[dict]:
    messages: list[dict] = [{"role": "system", "content": system_prompt()}]
    if pending_is_fresh(pending):
        messages.append(
            {
                "role": "system",
                "content": (
                    "Seat proposal already shown to the guest (expires soon). Do not hold it until "
                    "the guest explicitly confirms: "
                    + json.dumps(public_pending(pending), default=str)[:2500]
                ),
            }
        )

    open_calls: set[str] = set()
    for item in history:
        if item.role == "assistant" and item.tool_calls:
            call_ids = {str(call.get("id")) for call in item.tool_calls if call.get("id")}
            if not call_ids:
                continue
            open_calls = call_ids
            messages.append(
                {"role": "assistant", "content": item.content or None, "tool_calls": item.tool_calls}
            )
        elif item.role == "tool":
            # A tool result is only valid directly after the assistant call it answers.
            if not item.name or str(item.tool_call_id or "") not in open_calls:
                continue
            open_calls.discard(str(item.tool_call_id))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": item.tool_call_id or "",
                    "name": item.name,
                    "content": (item.content or "")[:6000],
                }
            )
        elif item.role in {"user", "assistant"} and (item.content or "").strip():
            messages.append({"role": item.role, "content": item.content or ""})
    return normalize_history(messages)


def normalize_history(messages: list[dict]) -> list[dict]:
    """Keep a window Gemini accepts: starts at a user turn and answers every function call."""
    start = next((i for i, m in enumerate(messages) if m.get("role") == "user"), None)
    if start is None:
        return [messages[0]] if messages and messages[0].get("role") == "system" else []

    system = messages[0] if messages and messages[0].get("role") == "system" else None
    extra_context = [messages[1]] if len(messages) > 1 and messages[1].get("role") == "system" else []
    body = messages[start:]
    cleaned: list[dict] = []
    open_calls: set[str] = set()

    def drop_unanswered() -> None:
        while cleaned and (cleaned[-1].get("role") == "tool" or cleaned[-1].get("tool_calls")):
            cleaned.pop()

    for message in body:
        role = message.get("role")
        if role == "assistant" and message.get("tool_calls"):
            if open_calls:
                drop_unanswered()
            open_calls = {str(call.get("id")) for call in message["tool_calls"] if call.get("id")}
            if not open_calls:
                continue
            cleaned.append(message)
        elif role == "tool":
            call_id = str(message.get("tool_call_id") or "")
            if call_id not in open_calls:
                continue
            open_calls.discard(call_id)
            cleaned.append(message)
        else:
            if open_calls:
                drop_unanswered()
                open_calls = set()
            if role == "assistant":
                text = (message.get("content") or "").strip()
                if not text:
                    continue
                if cleaned and cleaned[-1].get("role") == "assistant" and not cleaned[-1].get("tool_calls"):
                    cleaned[-1] = {
                        "role": "assistant",
                        "content": cleaned[-1]["content"].rstrip() + "\n\n" + text,
                    }
                    continue
                cleaned.append({"role": "assistant", "content": text})
            else:
                cleaned.append(message)

    if open_calls:
        drop_unanswered()
    context = ([system] if system else []) + extra_context
    return context + cleaned


def _content_text(content) -> str:
    if isinstance(content, list):
        return " ".join(
            str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in content
        )
    return content or ""


async def run_agent(
    db: Session,
    chat_session: AssistantSession,
    tools: AssistantTools,
    latest_text: str,
    history: list[AssistantMessage],
) -> str | None:
    """Return the assistant's final text, or None when the LLM is unusable."""
    messages = history_to_messages(history, chat_session.pending)

    for _ in range(settings.llm_max_iterations):
        try:
            message = await call_llm(messages, TOOLS)
        except Exception as exc:
            logger.warning("LLM call failed: %s", exc)
            return None

        content = _content_text(message.get("content"))
        tool_calls = message.get("tool_calls") or []

        if tool_calls:
            db.add(
                AssistantMessage(
                    id=str(uuid4()),
                    session_id=chat_session.id,
                    role="assistant",
                    content=content or None,
                    tool_calls=tool_calls,
                    created_at=utcnow(),
                )
            )
            messages.append({"role": "assistant", "content": content or None, "tool_calls": tool_calls})

            for call in tool_calls:
                function = call.get("function") or {}
                name = function.get("name") or ""
                raw_args = function.get("arguments") or "{}"
                try:
                    arguments = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                except (ValueError, TypeError):
                    arguments = {}

                result = await tools.execute(name, arguments)
                result_text = json.dumps(result, ensure_ascii=False, default=str)[:6000]
                db.add(
                    AssistantMessage(
                        id=str(uuid4()),
                        session_id=chat_session.id,
                        role="tool",
                        content=result_text,
                        tool_call_id=call.get("id"),
                        name=name,
                        created_at=utcnow(),
                    )
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id") or "",
                        "name": name,
                        "content": result_text,
                    }
                )
            db.flush()
            continue

        if content.strip():
            db.add(
                AssistantMessage(
                    id=str(uuid4()),
                    session_id=chat_session.id,
                    role="assistant",
                    content=content.strip(),
                    created_at=utcnow(),
                )
            )
            return content.strip()
        return None

    # The model kept calling tools until the cap: ask once more WITHOUT tools so the
    # information it already gathered is not thrown away to the fallback path.
    logger.warning(
        "agent reached %s iterations without a final answer, requesting a summary",
        settings.llm_max_iterations,
    )
    try:
        message = await call_llm(messages, [])
    except Exception as exc:
        logger.warning("summary call failed: %s", exc)
        return None

    text = _content_text(message.get("content")).strip()
    if not text:
        return None
    db.add(
        AssistantMessage(
            id=str(uuid4()),
            session_id=chat_session.id,
            role="assistant",
            content=text,
            created_at=utcnow(),
        )
    )
    db.flush()
    return text
