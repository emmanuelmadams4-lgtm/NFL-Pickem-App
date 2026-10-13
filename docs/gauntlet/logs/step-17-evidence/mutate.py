"""Step 17 mutation sweep: break each frozen clause once; test_ai.py must go red. Restores the files afterwards."""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4] / "backend"
P, C = ROOT / "nflpi/ai/providers.py", ROOT / "nflpi/config.py"
MUTATIONS = [
    ("C1 tools allowed", P, "tools=[],", "tools=None,"),
    ("C1 user settings loaded", P, "setting_sources=[],", "setting_sources=None,"),
    ("C1 key not blanked", P, '"ANTHROPIC_API_KEY": "", ', ""),
    ("C1 auth token not blanked", P, ', "ANTHROPIC_AUTH_TOKEN": ""', ""),
    ("C1 wrong model", P, "model=self.model,\n            max_turns", "model='x',\n            max_turns"),
    ("C2 schema not sent", P, "if json_schema else None,\n            stderr", "if False else None,\n            stderr"),
    ("C2 structured output as str", P, "json.dumps(result.structured_output)", "str(result.structured_output)"),
    ("C3 key-only route starts sdk", P, "sdk = ClaudeSdkProvider(token, s.anthropic_model) if token else None", "sdk = ClaudeSdkProvider('t', s.anthropic_model)"),
    ("C4 available ignores token", P, "s.claude_code_oauth_token.get_secret_value() or s.anthropic_api_key", "s.anthropic_api_key"),
    ("C4 neither configured does not raise", P, "if not token and not s.anthropic_api_key:", "if False:"),
    ("C5 no fallback", P, "if self.api is None:", "if True:"),
    ("C5 narrow except", P, "except Exception as exc:  # noqa: BLE001 - every SDK failure", "except OSError as exc:  # noqa: BLE001 - every SDK failure"),
    ("C5 no timeout", P, "asyncio.wait_for(last_result(), SDK_TIMEOUT_S)", "last_result()"),
    ("C5 route not set to api", P, 'self.route, self.model = "api", self.api.model', "pass"),
    ("C5 schema without output accepted", P, "if result.structured_output is None:", "if False:"),
    ("C5 empty text accepted", P, "if not result.result:", "if False:"),
    ("C5 error result accepted", P, "result is None or result.is_error or result.subtype != \"success\"", "result is None"),
    ("C6 no setup-token advice", P, "run claude setup-token and set ", "set "),
    ("C7 api detail dropped", P, "API key route: {exc}", "API key route"),
    ("C8 error leaks exception text", P, "{type(exc).__name__}\") from None", "{exc}\") from None"),
    ("C8 repr leaks token", P, "return f\"ClaudeSdkProvider(name={self.name!r}, route={self.route!r}, model={self.model!r})\"", "return f\"ClaudeSdkProvider({self.token})\""),
    ("C8 setting not secret", C, "claude_code_oauth_token: SecretStr = SecretStr(\"\")", "claude_code_oauth_token: str = \"\""),
    ("C8 key shown in settings repr", C, "if name != \"anthropic_api_key\"", "if True"),
    ("C9 no thread when loop runs", P, "    with ThreadPoolExecutor(max_workers=1) as pool:\n        return pool.submit(lambda: asyncio.run(make_coro())).result()", "    return asyncio.run(make_coro())"),
]

def run() -> bool:
    r = subprocess.run(["uv", "run", "pytest", "tests/test_ai.py", "-q", "-x", "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0

def main() -> int:
    survivors = []
    for name, path, old, new in MUTATIONS:
        src = path.read_text()
        if old not in src:
            print(f"SKIP (pattern gone) {name}"); survivors.append(name + " [pattern missing]"); continue
        path.write_text(src.replace(old, new, 1))
        try:
            killed = not run()
        finally:
            path.write_text(src)
        print(("KILLED  " if killed else "SURVIVED"), name, flush=True)
        if not killed: survivors.append(name)
    print(f"\n{len(MUTATIONS) - len(survivors)}/{len(MUTATIONS)} killed; survivors: {survivors}")
    return 1 if survivors else 0

if __name__ == "__main__":
    sys.exit(main())
