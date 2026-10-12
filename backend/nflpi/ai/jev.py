"""Typed Jev decisions API."""

import httpx

from nflpi.ai.providers import AIError
from nflpi.config import get_settings


def configured() -> bool:
    return bool(get_settings().openrouter_api_key)


def decide(state: str, questions: dict) -> dict:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise AIError("Jev is not configured: set OPENROUTER_API_KEY on the server")
    try:
        response = httpx.post(
            settings.openrouter_decisions_url,
            json={"model": settings.openrouter_model, "state": state, "questions": questions},
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            timeout=30,
        )
        response.raise_for_status()
        answers = response.json()["answers"]
        if not isinstance(answers, dict):
            raise ValueError("answers is not an object")
        return answers
    except Exception as exc:  # noqa: BLE001 - every transport or response failure becomes AIError
        raise AIError(f"Jev decisions error: {exc}") from exc
