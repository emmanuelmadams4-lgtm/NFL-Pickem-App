"""AI providers, with Claude sign-in first and the API key as fallback."""

import asyncio
import json
import logging
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

import anthropic
import anyio
import httpx
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from pydantic import SecretStr

from nflpi.config import get_settings

SDK_TIMEOUT_S = 120.0
_SDK_ENV = {
    "ANTHROPIC_API_KEY": "",
    "ANTHROPIC_AUTH_TOKEN": "",
    "ANTHROPIC_BASE_URL": "",
    "ANTHROPIC_CUSTOM_HEADERS": "",
    "CLAUDE_CODE_USE_BEDROCK": "",
    "CLAUDE_CODE_USE_VERTEX": "",
    "CLAUDE_CODE_USE_FOUNDRY": "",
    "HTTPS_PROXY": "",
    "https_proxy": "",
    "HTTP_PROXY": "",
    "http_proxy": "",
    "DISABLE_AUTOUPDATER": "1",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
}


def _run_sync(make_coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(make_coro())
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(make_coro())).result()


class AIError(RuntimeError):
    pass


class ClaudeDeclined(AIError):
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


class ClaudeSdkProvider:
    name = "claude"
    route = "sdk"

    def __init__(self, token: SecretStr, model: str) -> None:
        self.token, self.model = token, model

    def complete(self, system: str, user: str, json_schema: dict | None = None, max_tokens: int = 16000) -> str:
        token = self.token.get_secret_value()

        async def last_result(options: ClaudeAgentOptions) -> ResultMessage | None:
            last = None
            with anyio.fail_after(SDK_TIMEOUT_S):
                async for message in query(prompt=user, options=options):
                    if isinstance(message, ResultMessage):
                        last = message
            return last

        try:
            with tempfile.TemporaryDirectory(prefix="nflpi-claude-") as cfg:
                options = ClaudeAgentOptions(
                    system_prompt=system,
                    tools=[],
                    setting_sources=[],
                    model=self.model,
                    max_turns=5 if json_schema else 2,
                    effort="medium" if json_schema else "low",
                    output_format={"type": "json_schema", "schema": json_schema} if json_schema else None,
                    stderr=lambda _line: None,
                    cwd=cfg,
                    env={**_SDK_ENV, "CLAUDE_CODE_OAUTH_TOKEN": token, "CLAUDE_CONFIG_DIR": cfg},
                )
                result = _run_sync(lambda: last_result(options))
        except Exception as exc:  # noqa: BLE001 - every SDK failure becomes AIError
            detail = repr(exc).replace(token, "[redacted]")
            api_key = get_settings().anthropic_api_key
            if api_key:
                detail = detail.replace(api_key, "[redacted]")
            logging.getLogger("nflpi.ai").warning("Claude sign-in route error: %s", detail)
            raise AIError(f"Claude sign-in route failed: {type(exc).__name__}") from None

        if result is None or result.is_error or result.subtype != "success":
            raise AIError(f"Claude sign-in route failed: {result.subtype if result else 'no result'}")
        if result.stop_reason == "refusal":
            raise ClaudeDeclined("Claude declined this request")
        if result.stop_reason == "max_tokens":
            raise AIError("Claude response was cut off (max_tokens)")
        if json_schema:
            if result.structured_output is None:
                raise AIError("Claude sign-in route failed: no structured output")
            return json.dumps(result.structured_output)
        if not result.result:
            raise AIError("Claude sign-in route failed: empty result")
        return result.result

    def __repr__(self) -> str:
        return f"ClaudeSdkProvider(name={self.name!r}, route={self.route!r}, model={self.model!r})"


class ClaudeRouter:
    name = "claude"

    def __init__(self, sdk: ClaudeSdkProvider | None, api: ClaudeProvider | None) -> None:
        self.sdk, self.api = sdk, api
        self.route = "sdk" if sdk else "api"
        self.model = sdk.model if sdk else api.model if api else ""

    def complete(self, system: str, user: str, json_schema: dict | None = None, max_tokens: int = 16000) -> str:
        if self.sdk:
            try:
                answer = self.sdk.complete(system, user, json_schema, max_tokens)
            except ClaudeDeclined:
                raise
            except AIError as exc:
                if self.api is None:
                    raise AIError(
                        f"{exc}. The Claude sign-in may have expired; run claude setup-token and set "
                        "CLAUDE_CODE_OAUTH_TOKEN on the server"
                    ) from None
                logging.getLogger("nflpi.ai").warning(
                    "Claude sign-in route failed, falling back to the API key route: %s", str(exc)
                )
            else:
                self.route, self.model = "sdk", self.sdk.model
                return answer

        if self.api:
            try:
                answer = self.api.complete(system, user, json_schema, max_tokens)
            except AIError as exc:
                if self.sdk:
                    raise AIError(f"Claude sign-in and API key routes failed; API key route: {exc}") from None
                raise
            except Exception:
                if self.sdk:
                    raise AIError("Claude sign-in and API key routes failed") from None
                raise
            self.route, self.model = "api", self.api.model
            return answer
        raise AIError("Claude is not configured")

    def __repr__(self) -> str:
        return f"ClaudeRouter(name={self.name!r}, route={self.route!r}, model={self.model!r})"


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
        has_token = bool(s.claude_code_oauth_token.get_secret_value())
        if not has_token and not s.anthropic_api_key:
            raise AIError("Claude is not configured: set CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY on the server")
        sdk = ClaudeSdkProvider(s.claude_code_oauth_token, s.anthropic_model) if has_token else None
        api = ClaudeProvider(s.anthropic_api_key, s.anthropic_model) if s.anthropic_api_key else None
        return ClaudeRouter(sdk, api)
    if name == "jev":
        if not s.openrouter_api_key:
            raise AIError("Jev is not configured: set OPENROUTER_API_KEY on the server")
        return OpenRouterProvider(s.openrouter_api_key, s.openrouter_model, s.openrouter_url)
    raise AIError(f"unknown provider {name}")


def available() -> dict[str, bool]:
    s = get_settings()
    return {
        "claude": bool(s.claude_code_oauth_token.get_secret_value() or s.anthropic_api_key),
        "jev": bool(s.openrouter_api_key),
    }
