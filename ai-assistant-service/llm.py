"""LLM client.

The provider only needs to speak the OpenAI chat-completions protocol with tool
calling. Gemini's compatible endpoint is the default; the model can be swapped
with LLM_BASE_URL / LLM_MODEL / LLM_API_KEY without touching the code.
"""

from __future__ import annotations

import logging

import httpx

from config import settings

logger = logging.getLogger("ai-assistant-service.llm")

# Remember the model that answered last, so a broken model is not retried first every time.
PREFERRED_MODEL: str = settings.llm_model


def is_configured() -> bool:
    return bool(settings.llm_api_key and settings.llm_base_url)


async def complete(
    messages: list[dict],
    tools: list[dict] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict:
    """Return the assistant message of the first model that answers."""
    global PREFERRED_MODEL

    if not is_configured():
        raise RuntimeError("LLM is not configured")

    url = f"{settings.llm_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    chain = list(settings.models)
    if PREFERRED_MODEL in chain:
        chain.remove(PREFERRED_MODEL)
        chain.insert(0, PREFERRED_MODEL)

    failures: list[str] = []
    for model in chain:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": settings.llm_temperature if temperature is None else temperature,
            "max_tokens": settings.llm_max_tokens if max_tokens is None else max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.llm_timeout_seconds, connect=10.0)
            ) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            failures.append(f"{model}: {type(exc).__name__}")
            logger.warning("LLM transport error on %s: %s", model, exc)
            continue

        if response.status_code >= 400:
            failures.append(f"{model}: HTTP {response.status_code}")
            logger.warning("LLM error on %s: %s %s", model, response.status_code, response.text[:300])
            continue

        try:
            data = response.json()
        except ValueError:
            failures.append(f"{model}: invalid JSON")
            continue

        choices = data.get("choices") or []
        if not choices:
            failures.append(f"{model}: no choices")
            logger.warning("LLM returned no choices on %s: %s", model, str(data)[:300])
            continue

        PREFERRED_MODEL = model
        return choices[0].get("message") or {}

    raise RuntimeError("LLM unavailable (" + "; ".join(failures) + ")")


async def call_llm(messages: list[dict], tools: list[dict]) -> dict:
    """Chat completion with the booking tools enabled."""
    return await complete(messages, tools=tools)
