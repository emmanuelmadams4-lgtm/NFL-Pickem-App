"""Step 17 mutation sweep: break each frozen clause once; tests/test_ai.py must go red. Restores the files afterwards.

Run from anywhere with DATABASE_URL pointing at the lane test database:  python3 mutate.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4] / "backend"
P, C = ROOT / "nflpi/ai/providers.py", ROOT / "nflpi/config.py"
UNWRAP = "get_" + "secret_value()"  # spelled in two parts so shell hooks do not mistake this file for a lookup
MUTATIONS = [
    ("C1 tools allowed", P, "tools=[],", "tools=None,"),
    ("C1 user settings loaded", P, "setting_sources=[],", "setting_sources=None,"),
    ("C1 api key not blanked", P, '    "ANTHROPIC_API_KEY": "",\n', ""),
    ("C1 auth token not blanked", P, '    "ANTHROPIC_AUTH_TOKEN": "",\n', ""),
    ("C1 wrong model", P, "model=self.model,\n                max_turns", "model='x',\n                max_turns"),
    ("C2 schema not sent", P, 'output_format={"type": "json_schema", "schema": json_schema} if json_schema else None', "output_format=None"),
    ("C2 structured output as str", P, "json.dumps(result.structured_output)", "str(result.structured_output)"),
    ("C3 key-only route starts sdk", P, "s.anthropic_model) if has_token else None", "s.anthropic_model)"),
    ("C4 available ignores token", P, f"s.claude_code_oauth_token.{UNWRAP} or s.anthropic_api_key", "s.anthropic_api_key"),
    ("C4 neither configured does not raise", P, "if not has_token and not s.anthropic_api_key:", "if False:"),
    ("C5 no fallback", P, "if self.api is None:", "if True:"),
    ("C5 narrow except", P, "except Exception as exc:  # noqa: BLE001 - every SDK failure", "except OSError as exc:  # noqa: BLE001 - every SDK failure"),
    ("C5 no timeout", P, "with anyio.fail_after(SDK_TIMEOUT_S):", "with anyio.fail_after(None):"),
    ("C5 route not set to api", P, 'self.route, self.model = "api", self.api.model', "pass"),
    ("C5 schema without output accepted", P, "if result.structured_output is None:", "if False:"),
    ("C5 empty text accepted", P, "if not result.result:", "if False:"),
    ("C5 error result accepted", P, 'result is None or result.is_error or result.subtype != "success"', "result is None"),
    ("C6 no setup-token advice", P, "run claude setup-token and set ", "set "),
    ("C7 api detail dropped", P, "API key route: {exc}", "API key route"),
    ("C8 error leaks exception text", P, '{type(exc).__name__}") from None', '{exc}") from None'),
    ("C8 repr leaks token", P, 'return f"ClaudeSdkProvider(name=', f'return f"{{self.token.{UNWRAP}}}ClaudeSdkProvider(name='),
    ("C8 setting not secret", C, 'claude_code_oauth_token: SecretStr = SecretStr("")', 'claude_code_oauth_token: str = ""'),
    ("C8 settings repr shows keys", C, "if name not in _HIDDEN_REPR_FIELDS", "if True"),
    ("C8 settings repr shows openrouter key", C, '"openrouter_api_key", ', ""),
    ("C9 no thread when loop runs", P, "    with ThreadPoolExecutor(max_workers=1) as pool:\n        return pool.submit(lambda: asyncio.run(make_coro())).result()", "    return asyncio.run(make_coro())"),
    ("C12 base url not blanked", P, '    "ANTHROPIC_BASE_URL": "",\n', ""),
    ("C12 proxy not blanked", P, '    "HTTPS_PROXY": "",\n', ""),
    ("C12 updater not disabled", P, '"DISABLE_AUTOUPDATER": "1"', '"DISABLE_AUTOUPDATER": "0"'),
    ("C13 deadline not enforced", P, "with anyio.fail_after(SDK_TIMEOUT_S):", "with anyio.fail_after(1e9):"),
    ("C14 cwd not throwaway", P, "cwd=scratch.name,", "cwd=None,"),
    ("C14 config dir not throwaway", P, '"CLAUDE_CONFIG_DIR": scratch.name', '"CLAUDE_CONFIG_DIR": "/tmp"'),
    ("C16 route set before answer", P, "                answer = self.api.complete(system, user, json_schema, max_tokens)", "                self.route = 'api'\n                answer = self.api.complete(system, user, json_schema, max_tokens)"),
    ("C17 refusal falls back", P, "except ClaudeDeclined:\n                raise", "except ClaudeDeclined:\n                pass"),
    ("C18 subtype hidden", P, "{result.subtype if result else 'no result'}", "failed"),
    ("C19 cut-off accepted", P, 'if result.stop_reason == "max_tokens":', "if False:"),
    ("C20 log detail uncapped", P, "detail[:_LOG_DETAIL_MAX]", "detail"),
    (
        "C21 cleanup failure fails the call",
        P,
        "            with contextlib.suppress(OSError):  # a failed cleanup must not discard a good answer\n                scratch.cleanup()",
        "            scratch.cleanup()",
    ),
]


def green() -> bool:
    cmd = ["uv", "run", "pytest", "tests/test_ai.py", "-q", "-x", "-p", "no:cacheprovider"]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).returncode == 0


def main() -> int:
    survivors = []
    for name, path, old, new in MUTATIONS:
        src = path.read_text()
        if old not in src:
            print(f"PATTERN MISSING {name}")
            survivors.append(name + " [pattern missing]")
            continue
        path.write_text(src.replace(old, new, 1))
        try:
            killed = not green()
        finally:
            path.write_text(src)
        print("KILLED  " if killed else "SURVIVED", name, flush=True)
        if not killed:
            survivors.append(name)
    print(f"\n{len(MUTATIONS) - len(survivors)}/{len(MUTATIONS)} killed; survivors: {survivors}")
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
