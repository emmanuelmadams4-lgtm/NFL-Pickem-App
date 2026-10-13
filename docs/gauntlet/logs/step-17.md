# Step 17: Claude through the Agent SDK sign-in, API key as backup

Lane sdk, ONE_SHOT, tier T3. Base main `8b1034e`, branch `lane/sdk`. Coordinator: Stanley (hive `worker-sdk`).
Decisions relied on: D32 (SDK sign-in, not an API key), D31/D34 (OpenRouter stays for Jev; model `claude-sonnet-5-5`), D57 (SDK first, API key as backup; owner sets keys on the server himself), D36 (one chat; Jev not touched here).

## 1. PLANNING

* Goal: `get_provider("claude")` calls Claude through the Claude Agent SDK using `CLAUDE_CODE_OAUTH_TOKEN`; if that route is not configured or fails, it uses the `ANTHROPIC_API_KEY` route. The token never appears in logs, errors or API output. The Docker image can run the SDK.
* Done-when: every clause in section 2 has a test that fails when the clause is broken; gate green twice; hand check of the image (bundled CLI runs inside the built image); Dwight (security) signs off on token handling; fresh critic PASS.
* Not in this step: Jev, the chat screen, new AI features, `api/`, `jobs.py`, `config.py` beyond one new setting, a real call (needs the owner's yes through god).
* Tier T3 answers (pre-flight):
  * Problem: the owner has a Claude subscription but no API key (D31, D32); the AI features cannot run without a route that uses the sign-in.
  * Why now: step 11 (go-live) and the chat need a working Claude route; HAG-25 (D57).
  * Scope: one new provider class and a router in `ai/providers.py`, one setting, the dependency. Cut: SDK sessions, tools, streaming, a route picker in the UI, per-route cost tracking.
  * Success signal: with only the token set, a report or an answer is produced; with the token broken and a key set, the same call succeeds through the key. Measured at go-live by the owner's first real call (PENDING, needs his yes).
  * Reversibility: two-way. Unsetting the token returns to the API-key-only behavior.
* Assumptions: validated: the wheel bundles the CLI (`claude_agent_sdk/_bundled/claude`, CLI 2.1.294, runs here); a non-empty `ANTHROPIC_API_KEY` beats `CLAUDE_CODE_OAUTH_TOKEN` and an empty one does not (checked with `claude auth status` in a throwaway HOME, no model call); `ClaudeAgentOptions.env` is merged over `os.environ` (read in `subprocess_cli.py`). Assumed, checked at go-live: `claude-sonnet-5-5` is accepted by the CLI's `--model`; structured output needs `max_turns` above 1; no tools means `tools=[]` is enough. Unknown, not design-changing: whether the plan's terms allow a private single-user app (D32 reading: allowed, inferred; enforcement may come without notice).
* Doc sources read: code.claude.com/docs/en/agent-sdk/python, /agent-sdk/structured-outputs, /authentication (fetched 2026-10-13).
* Skills: `/graft` N/A (one known file, read directly); `/jevgrep` not used (same reason, recorded); `harness-engineering`: locked = `tests/test_ai.py` clauses, editable = `ai/providers.py` + one setting, human-controlled = the token, the first real call, push/merge; `/tdd` (red test first, commit 663889e); `/ponytail` in the work order.
* Direction check: this step builds nothing the owner sees. It changes which door the existing "Ask / report" calls use. It is not a new chat, not Jev, not a login screen.

## 2. SPECIFICATION (frozen clauses, all in `backend/tests/test_ai.py`)

| # | Clause | Test |
|---|---|---|
| C1 | Token set, no key: Claude calls go through the SDK, no tools, no user settings, model from `ANTHROPIC_MODEL`, token passed only via env, `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` blanked for that call | `test_sign_in_token_alone_uses_the_sdk_route_with_no_tools` |
| C2 | A schema request returns the SDK's structured output as JSON text | `test_schema_request_returns_the_structured_output_as_json_text` |
| C3 | Key set, no token: API route only, SDK never started | `test_key_alone_uses_the_api_route_and_never_starts_the_sdk` |
| C4 | Neither set: "not configured"; `available()["claude"]` is true if either is set | `test_neither_route_configured_says_so`, `test_claude_is_available_when_either_route_is_configured` |
| C5 | SDK failure (process error, error result, schema without output, empty text, no result, timeout) with a key set: falls back to the API route; the provider reports route `api` and the API model | `test_sdk_failure_falls_back_to_the_api_key_route` (6 cases) |
| C6 | SDK failure with no key: a plain error that names the sign-in and `claude setup-token` | `test_sdk_failure_without_a_key_names_the_sign_in` |
| C7 | Both fail: one error naming both routes | `test_both_routes_failing_reports_both` |
| C8 | Token and key never appear in errors, log records, provider repr, settings repr/str, or the setting's own repr | `test_the_token_never_appears_in_errors_logs_or_reprs`, `test_the_token_setting_is_read_from_the_environment_and_masked` |
| C9 | The sync `complete()` works from inside a running event loop | `test_sync_complete_works_inside_a_running_event_loop` |
| C10 | The report and Q&A code works through the SDK route unchanged (`provider="claude"`, model recorded) | `test_research_answers_through_the_sdk_route` |
| C11 | The image gets the CLI from the Python wheel; no Node or npm install in the Dockerfile | `test_the_image_gets_the_cli_from_the_python_package` + hand check below |

Operational layer: a fallback writes one warning to the `nflpi.ai` logger (route and error class only). User-facing layer: the owner sees no screen change; a dead sign-in shows as a plain error that tells him to run `claude setup-token` (the daily-cap and report-failure paths in `research.py` carry it unchanged).
Hand check (VERIFICATION): build the image and run the bundled CLI inside it (`claude --version`), under `res:gate`.

Red: `pytest tests/test_ai.py` fails at fixture setup with `AttributeError: module 'nflpi.ai.providers' has no attribute 'query'` (the seam does not exist yet), not at a syntax, fixture or environment fault. Commit `663889e`.

Cap note: `research._count_attempt` counts one provider attempt per `complete()`; a fallback inside one `complete()` is one counted attempt, two real calls. At most 2x of 60 a day; accepted, recorded.

## Seam asks for the integrator

* `.env.example`: add `CLAUDE_CODE_OAUTH_TOKEN=` (empty) next to `ANTHROPIC_API_KEY=` (not in lane sdk's OWNS).
* `docker-compose.yml`: no change needed; both services use `env_file: .env`.
* `Dockerfile`: no change needed if the hand check passes.

## 3. IMPLEMENTATION
(pending)

## 4. CLEANUP
(pending)

## 5. VERIFICATION
(pending)

## 6. LANDING
Not mine: god lands it.
