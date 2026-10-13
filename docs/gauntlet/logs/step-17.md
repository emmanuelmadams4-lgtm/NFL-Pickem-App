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

Provider: Codex on the Build Ladder, coordinator inspected every diff and reran every proof (Codex could not reach the test database from its sandbox, so none of its proof counts).
`JEV: model:sdk-wo-1 -> sol (0.94), effort -> xhigh (0.91)` (secret handling). `JEV: model:sdk-wo-3 -> luna (1.00), effort unsure (medium 0.65 / low 0.35, confidence 0.53) -> coordinator chose medium` (low-stakes cleanup, no advisor call spent).
`EFFORT: PLANNING/SPEC high; build dispatch low; VERIFICATION high`. `CLIMBS: none`. `BUILD_RUNG: sol try 1 (wo-1), sol try 2 = narrow correction (wo-2), luna (wo-3, wo-5), sol (wo-4)`. No astra, no Fable.

| Commit | Work order | Model | Result |
|---|---|---|---|
| `663889e` | spec: 13 red tests + `claude-agent-sdk` 0.2.165 | coordinator | red at `providers.query` missing |
| `551cef3` | wo-1 SDK provider, router, setting | gpt-6-sol xhigh | 20 pass; 2 added spec tests red |
| `1b9c4b3` | wo-2 narrow correction: any SDK failure falls back, API status kept, config tidy | gpt-6-sol xhigh | 22 pass |
| `290072a` | wo-3 CLEANUP 1 | gpt-6-luna medium | 22 pass |
| `a5df2b7` | security clauses C12-C19 red (from Dwight's review of 290072a) + mutation script | coordinator | 9 red |
| `d99ecf2` | wo-4 security fixes | gpt-6-sol xhigh | 31 pass |
| `012e526` | wo-5 CLEANUP 2 | gpt-6-luna medium | 31 pass |

Review of 290072a (Dwight, hive `dwight-mv5mkpow`, with `ecc:security-reviewer` and `ecc:silent-failure-hunter` under him): PASS on token handling, no CRITICAL or HIGH security finding, 4 MEDIUM + 4 data-integrity notes. Handling:

| Finding | Decision |
|---|---|
| S1 child inherits server env, could be pointed elsewhere | fixed (C12): base URL, headers, Bedrock/Vertex/Foundry, proxies blanked; updater and extra traffic off. The other server secrets (DB URL, access token, VAPID, OpenRouter key) still sit in the child's inherited environment: the SDK has no clean-env switch; accepted, the child is the bundled Claude CLI with no tools |
| S2 timeout leaves child running | fixed (C13): `anyio.fail_after` inside the coroutine. Child termination is the SDK's own behavior; not observed with a real CLI |
| S3 prompts written under `~/.claude` | fixed (C14): throwaway `cwd` + `CLAUDE_CONFIG_DIR` per call, deleted after. Cost: a fresh config directory each call; first-run time unknown until the live call |
| S4 daily cap passed by ~2x | recorded, not changed: SDK calls are flat-rate; the paid route is one counted attempt per `complete()` exactly as before this step, so the paid-call ceiling is unchanged (`ai_daily_call_limit` bounds paid calls, plus the API client's own 2 retries as before) |
| F1 dead SDK route hidden by quiet fallback | partly: fallback logs a redacted `repr(exc)` (C15, tested by the log test, which my mutation script does not cover; test is `test_a_fallback_leaves_a_traceable_log_line_without_the_token`). Not done: a counter or a stored route |
| F2 stored report cannot say which route answered | carried to the web lane (needs a column or a field in `AIReport` / `AskOut`, outside lane sdk's files). `route` is set to `api` only after the API answered (C16) |
| F3 refusal retried on the paid route | fixed (C17) with `ClaudeDeclined`; failed results show their `subtype` (C18) |
| F4 `max_tokens` ignored on the SDK route | fixed (C19): a cut-off answer is an error like the API route |
| LOW token as plain attribute / settings repr | fixed (`SecretStr` kept; four secret settings hidden from `repr(Settings)`; `database_url` still shown) |
| LOW `.env.example` | seam ask to god |
| For god: no recorded owner yes for running the subscription sign-in on the server (HAG-25 open) | passed on in the done message |

## 4. CLEANUP

`/refactor` pass, scope-locked to the code this step added in `ai/providers.py`:
1. After wo-1/2 (`290072a`): extracted `_run_sync`; moved `output_format` into the options constructor; flattened `ClaudeRouter.complete`; fallback log prints our own message instead of a constant class name. 22 tests green.
2. After the security fixes (`012e526`): `complete` had grown to ~55 lines. Extracted `_result_text` (result checks) and `_log_sdk_failure` (redacted warning). 31 tests green, ruff clean.
Left alone on purpose: `ClaudeRouter.complete` still has two exception shapes for the paid route (a deliberate fork between "sign-in also failed" and "API-only"); `config.py` keeps one small frozenset.
No change needed in `research.py` (no edits there).

## 5. VERIFICATION

Evidence directory: `docs/gauntlet/logs/step-17-evidence/` (gate logs, mutation sweep, image check, build log).

* Mutation sweep `mutate.py`, 35 mutations over clauses C1 to C19 (not C10/C11/C15, which are integration, file and log tests): `mutate-2.log` 35/35 killed. First sweep (`mutate-1` deleted) found 9 stale patterns after the cleanup and one equivalent mutant (repr of a `SecretStr`), both fixed in the script, not in the code.
* Gate on HEAD `94ae938` (code unchanged since `012e526`), run twice with the lock `res:gate` held:
  * `gate1-*.log`, `gate2-*.log`: `uv run pytest -q` 460 passed (75 s, 65 s); `ruff check nflpi tests migrations` All checks passed; `alembic check` No new upgrade operations detected (own database `nflpi` in container `nflpi-lane-sdk-db`, after `alembic upgrade head`); `npm run gen:api` no drift (`git status` clean after).
  * Test database: container `nflpi-lane-sdk-db`, 127.0.0.1:15444, no volume. I started it before the `res:gate` lock was mine (a bare `postgres:17`, no build); noted here for the record.
* Hand check, the image: `docker build` ok (`image-build.log`); inside the image the bundled CLI runs (`claude 2.1.294`, aarch64), `claude auth status` with `CLAUDE_CODE_OAUTH_TOKEN` set and `ANTHROPIC_API_KEY` empty reports `authMethod: oauth_token`, and `from nflpi.ai.providers import ClaudeSdkProvider` imports (`image-check.log`). The lock holds a `manylinux_2_17_x86_64` wheel too (for the Windows PC's Docker). No Dockerfile change. Image deleted after.
* Real call: none made, none needed for the gate. PENDING (owner's yes through god): one live report or question with only the token set, then one with a broken token and the key set.
* Security: Dwight PASS on 290072a; delta to HEAD sent, verdict below.
* Fresh critic: below.

## 6. LANDING
Not mine: god lands it.
