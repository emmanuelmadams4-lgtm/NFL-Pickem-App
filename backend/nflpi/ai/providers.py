"""AI providers behind one small interface. Keys never leave the server."""

import json
from typing import Protocol

import anthropic
import httpx

from nflpi.config import get_settings


class AIError(RuntimeError):
    pass


class AIProvider(Protocol):
    name: str
    model: str

    def complete(self, system: str, user: str, json_schema: dict | None = None, max_tokens: int = 16000) -> str:
        """Return the model's text. With json_schema, the text must be a JSON object."""
        ...


class ClaudeProvider:
    name = "claude"

    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key, timeout=120.0, max_retries=2)

    def complete(self, system: str, user: str, json_schema: dict | None = None, max_tokens: int = 16000) -> str:
        output_config: dict = {"effort": "medium" if json_schema else "low"}
        if json_schema:
            output_config["format"] = {"type": "json_schema", "schema": json_schema}
        try:
            resp = self.client.beta.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config=output_config,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIStatusError as exc:
            raise AIError(f"Claude API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise AIError(f"Claude connection error: {exc}") from exc
        if resp.stop_reason == "refusal":
            raise AIError("Claude declined this request")
        if resp.stop_reason == "max_tokens":
            raise AIError("Claude response was cut off (max_tokens)")
        return "".join(b.text for b in resp.content if b.type == "text")


class OpenRouterProvider:
    """OpenRouter's documented chat completions API. Model id comes from config (Jev by default)."""

    name = "jev"

    def __init__(self, api_key: str, model: str, url: str) -> None:
        self.api_key, self.model, self.url = api_key, model, url

    def complete(self, system: str, user: str, json_schema: dict | None = None, max_tokens: int = 16000) -> str:
        if json_schema:
            system += "\n\nReply with one JSON object only, matching this JSON Schema:\n" + json.dumps(json_schema)
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        try:
            resp = httpx.post(self.url, json=body, timeout=120, headers={"Authorization": f"Bearer {self.api_key}"})
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"] or ""
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise AIError(f"OpenRouter error: {exc}") from exc


def get_provider(name: str) -> AIProvider:
    s = get_settings()
    if name == "claude":
        if not s.anthropic_api_key:
            raise AIError("Claude is not configured: set ANTHROPIC_API_KEY on the server")
        return ClaudeProvider(s.anthropic_api_key, s.anthropic_model)
    if name == "jev":
        if not s.openrouter_api_key:
            raise AIError("Jev is not configured: set OPENROUTER_API_KEY on the server")
        return OpenRouterProvider(s.openrouter_api_key, s.openrouter_model, s.openrouter_url)
    raise AIError(f"unknown provider {name}")


def available() -> dict[str, bool]:
    s = get_settings()
    return {"claude": bool(s.anthropic_api_key), "jev": bool(s.openrouter_api_key)}
