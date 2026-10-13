"""Step 17: Claude through the Agent SDK sign-in token, with the API key as the fallback route.

Both routes are mocked. No test makes a real call, and no test needs a real token or key.
"""

import asyncio
import json
import logging
import math
import os
from pathlib import Path
from types import SimpleNamespace

import anyio
import claude_agent_sdk
import pytest
from claude_agent_sdk import ProcessError, ResultMessage

from nflpi.ai import providers, research
from nflpi.ai.providers import AIError
from nflpi.config import get_settings

TOKEN = "sk-ant-oat01-SECRET-sign-in-token"
KEY = "sk-ant-api03-SECRET-api-key"
SCHEMA = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]}


def result(**kw) -> ResultMessage:
    base = dict(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1, session_id="s")
    return ResultMessage(**{**base, **kw})


class FakeSdk:
    """Stands in for claude_agent_sdk.query: records calls, then yields or raises what the test set."""

    def __init__(self, messages=(), error: Exception | None = None, delay: float = 0.0) -> None:
        self.messages, self.error, self.delay, self.calls, self.seen = list(messages), error, delay, [], {}

    def __call__(self, *, prompt, options=None, **kwargs):
        self.calls.append({"prompt": prompt, "options": options})
        return self._stream(options)

    async def _stream(self, options):
        self.seen = {"deadline": anyio.current_effective_deadline(), "cwd_is_dir": os.path.isdir(str(options.cwd))}
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        for m in self.messages:
            yield m


class FakeAnthropic:
    def __init__(self, reply: str = "api reply", error: Exception | None = None) -> None:
        self.reply, self.error, self.calls = reply, error, []

    def __getattr__(self, name):
        return self

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=self.reply)])


@pytest.fixture
def setup(monkeypatch):
    """Configure the routes the test names, and swap both clients for fakes."""

    def make(token: str = "", key: str = "", sdk: FakeSdk | None = None, api: FakeAnthropic | None = None):
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", token)
        monkeypatch.setenv("ANTHROPIC_API_KEY", key)
        get_settings.cache_clear()
        sdk, api = sdk or FakeSdk([result(result="sdk reply")]), api or FakeAnthropic()
        monkeypatch.setattr(providers, "query", sdk)
        monkeypatch.setattr(providers.anthropic, "Anthropic", lambda **kw: api)
        return sdk, api

    yield make
    get_settings.cache_clear()


def test_sign_in_token_alone_uses_the_sdk_route_with_no_tools(setup):
    sdk, api = setup(token=TOKEN)
    provider = providers.get_provider("claude")
    assert provider.complete("sys", "question") == "sdk reply"
    opts = sdk.calls[0]["options"]
    assert sdk.calls[0]["prompt"] == "question" and opts.system_prompt == "sys"
    assert opts.tools == [] and opts.setting_sources == [] and opts.model == get_settings().anthropic_model
    assert opts.env["CLAUDE_CODE_OAUTH_TOKEN"] == TOKEN
    # a non-empty key in the server's environment would beat the sign-in; it must be blanked for the SDK call
    assert opts.env["ANTHROPIC_API_KEY"] == "" and opts.env["ANTHROPIC_AUTH_TOKEN"] == ""
    assert provider.name == "claude" and provider.route == "sdk" and api.calls == []


def test_schema_request_returns_the_structured_output_as_json_text(setup):
    sdk, _ = setup(token=TOKEN, sdk=FakeSdk([result(structured_output={"x": 3})]))
    out = providers.get_provider("claude").complete("sys", "q", SCHEMA)
    assert json.loads(out) == {"x": 3}
    assert sdk.calls[0]["options"].output_format == {"type": "json_schema", "schema": SCHEMA}


def test_key_alone_uses_the_api_route_and_never_starts_the_sdk(setup):
    sdk, api = setup(key=KEY)
    provider = providers.get_provider("claude")
    assert provider.complete("sys", "q") == "api reply"
    assert sdk.calls == [] and len(api.calls) == 1 and provider.route == "api"


def test_neither_route_configured_says_so(setup):
    setup()
    assert providers.available()["claude"] is False
    with pytest.raises(AIError, match="not configured"):
        providers.get_provider("claude")


@pytest.mark.parametrize("token,key", [(TOKEN, ""), ("", KEY), (TOKEN, KEY)])
def test_claude_is_available_when_either_route_is_configured(setup, token, key):
    setup(token=token, key=key)
    assert providers.available()["claude"] is True


FAILURES = {
    "process_error": lambda: FakeSdk(error=ProcessError("exit 1", exit_code=1)),
    "error_result": lambda: FakeSdk([result(is_error=True, subtype="error_during_execution", result="x")]),
    "schema_without_output": lambda: FakeSdk([result(result="text only")]),
    "empty_text": lambda: FakeSdk([result(result="")]),
    "no_result_at_all": lambda: FakeSdk([]),
    "unexpected_exception": lambda: FakeSdk(error=ValueError(f"surprise {TOKEN}")),
    "timeout": lambda: FakeSdk([result(result="late")], delay=1.0),
}


@pytest.mark.parametrize("failure", FAILURES)
def test_sdk_failure_falls_back_to_the_api_key_route(setup, monkeypatch, failure):
    monkeypatch.setattr(providers, "SDK_TIMEOUT_S", 0.05)
    _, api = setup(token=TOKEN, key=KEY, sdk=FAILURES[failure]())
    provider = providers.get_provider("claude")
    assert provider.complete("sys", "q", SCHEMA if failure == "schema_without_output" else None) == "api reply"
    assert len(api.calls) == 1 and provider.route == "api" and provider.model == get_settings().anthropic_model


def test_sdk_failure_without_a_key_names_the_sign_in(setup):
    setup(token=TOKEN, sdk=FakeSdk(error=ProcessError("exit 1", exit_code=1)))
    with pytest.raises(AIError, match="sign-in") as exc:
        providers.get_provider("claude").complete("sys", "q")
    assert "setup-token" in str(exc.value)


def test_both_routes_failing_reports_both(setup):
    sdk = FakeSdk(error=ProcessError("exit 1", exit_code=1))
    setup(token=TOKEN, key=KEY, sdk=sdk, api=FakeAnthropic(error=RuntimeError("down")))
    with pytest.raises(AIError) as exc:
        providers.get_provider("claude").complete("sys", "q")
    assert "sign-in" in str(exc.value) and "API key" in str(exc.value)


def test_both_routes_failing_keeps_the_api_status_for_the_owner(setup):
    api = FakeAnthropic(error=AIError("Claude API error 401: invalid x-api-key"))
    setup(token=TOKEN, key=KEY, sdk=FakeSdk(error=ProcessError("exit 1", exit_code=1)), api=api)
    with pytest.raises(AIError, match="401"):
        providers.get_provider("claude").complete("sys", "q")


def test_the_token_never_appears_in_errors_logs_or_reprs(setup, caplog):
    leaky = ProcessError(f"cli said token={TOKEN} key={KEY}", exit_code=1, stderr=f"env OAUTH={TOKEN}")
    api = FakeAnthropic(error=RuntimeError(f"bad {KEY} {TOKEN}"))
    setup(token=TOKEN, key=KEY, sdk=FakeSdk(error=leaky), api=api)
    provider = providers.get_provider("claude")
    with caplog.at_level(logging.DEBUG), pytest.raises(AIError) as exc:
        provider.complete("sys", "q")
    seen = [str(exc.value), repr(exc.value), caplog.text, repr(provider), repr(get_settings()), str(get_settings())]
    for text in seen:
        assert TOKEN not in text and KEY not in text
    assert exc.value.__cause__ is None or TOKEN not in str(exc.value.__cause__)


def test_the_token_setting_is_read_from_the_environment_and_masked(setup):
    setup(token=TOKEN)
    value = get_settings().claude_code_oauth_token
    assert value.get_secret_value() == TOKEN and TOKEN not in repr(value) and TOKEN not in str(value)


def test_sync_complete_works_inside_a_running_event_loop(setup):
    setup(token=TOKEN)
    provider = providers.get_provider("claude")

    async def inside_loop():
        return provider.complete("sys", "q")

    assert asyncio.run(inside_loop()) == "sdk reply"


def test_research_answers_through_the_sdk_route(setup, loaded):
    from tests.test_hardening import week_rows

    setup(token=TOKEN)
    gid = week_rows(4)[0]["game_id"]
    out = research.answer_question(loaded, gid, "Who wins?")
    assert out.answer == "sdk reply" and out.provider == "claude" and out.model == get_settings().anthropic_model


def test_the_image_gets_the_cli_from_the_python_package():
    bundled = Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude"
    assert bundled.is_file(), "the wheel no longer bundles the Claude Code CLI: the Dockerfile must install it"


# Dwight's security review (S1 to S3, F1 to F4 and the LOW notes), frozen as clauses C12 to C19 --------------------


def test_child_process_cannot_be_pointed_elsewhere_by_the_server_environment(setup):
    sdk, _ = setup(token=TOKEN)
    providers.get_provider("claude").complete("sys", "q")
    env = sdk.calls[0]["options"].env
    for name in ("ANTHROPIC_BASE_URL", "ANTHROPIC_CUSTOM_HEADERS", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
                 "CLAUDE_CODE_USE_FOUNDRY", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        assert env[name] == "", name
    assert env["DISABLE_AUTOUPDATER"] == "1" and env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"


def test_the_sdk_call_runs_under_a_deadline_that_also_stops_the_child(setup):
    sdk, _ = setup(token=TOKEN)
    providers.get_provider("claude").complete("sys", "q")
    assert math.isfinite(sdk.seen["deadline"])  # an anyio deadline, so the SDK can terminate its CLI process


def test_each_call_gets_a_throwaway_working_and_config_directory(setup):
    sdk, _ = setup(token=TOKEN)
    providers.get_provider("claude").complete("sys", "q")
    options = sdk.calls[0]["options"]
    assert sdk.seen["cwd_is_dir"] is True and str(options.cwd) == options.env["CLAUDE_CONFIG_DIR"]
    assert not os.path.exists(str(options.cwd))  # removed after the call: no transcripts left behind


def test_a_fallback_leaves_a_traceable_log_line_without_the_token(setup, caplog):
    setup(token=TOKEN, key=KEY, sdk=FakeSdk(error=ProcessError(f"x {TOKEN}", exit_code=1)))
    with caplog.at_level(logging.WARNING, logger="nflpi.ai"):
        providers.get_provider("claude").complete("sys", "q")
    assert "ProcessError" in caplog.text and TOKEN not in caplog.text


def test_the_route_says_api_only_after_the_api_answered(setup):
    sdk = FakeSdk(error=ProcessError("exit 1", exit_code=1))
    setup(token=TOKEN, key=KEY, sdk=sdk, api=FakeAnthropic(error=AIError("401")))
    provider = providers.get_provider("claude")
    with pytest.raises(AIError):
        provider.complete("sys", "q")
    assert provider.route == "sdk"


def test_a_refusal_is_not_retried_on_the_paid_route(setup):
    sdk, api = setup(token=TOKEN, key=KEY, sdk=FakeSdk([result(result="no", stop_reason="refusal")]))
    with pytest.raises(AIError, match="declined"):
        providers.get_provider("claude").complete("sys", "q")
    assert api.calls == []


def test_a_failed_result_reports_why(setup):
    setup(token=TOKEN, sdk=FakeSdk([result(is_error=True, subtype="error_max_turns")]))
    with pytest.raises(AIError, match="error_max_turns"):
        providers.get_provider("claude").complete("sys", "q")


def test_a_cut_off_sdk_answer_is_an_error_like_the_api_route(setup):
    setup(token=TOKEN, sdk=FakeSdk([result(result="half an ans", stop_reason="max_tokens")]))
    with pytest.raises(AIError, match="cut off"):
        providers.get_provider("claude").complete("sys", "q")


def test_no_secret_sits_in_plain_attributes_or_settings_repr(setup, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-SECRET-key")
    setup(token=TOKEN)
    provider = providers.get_provider("claude")
    assert TOKEN not in repr(vars(provider.sdk)) and TOKEN not in repr(vars(provider))
    shown = repr(get_settings())
    assert "or-SECRET-key" not in shown and "test-token" not in shown
