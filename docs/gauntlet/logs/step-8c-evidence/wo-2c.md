CODEX WORK ORDER 2c (narrow fixes, lane news; two red tests in backend/tests/test_news.py)

GOAL: fix two defects found by the coordinator's new tests.
FAILING EVIDENCE (you cannot reach the database; read the tests):
 1. test_odd_unicode_case_in_a_headline_never_raises_and_never_matches_by_accident: `match.tie` raises KeyError: 'miami dolphi̇ns'. The regexes use re.I, so "MIAMI DOLPHİNS" (U+0130) matches, but the dict lookup `hit.group().casefold()` has no such key.
 2. test_a_not_modified_poll_still_prunes: in run.py the HTTP 304 branch skips `store.prune`, so old rows stay.
ALLOWED SCOPE: backend/nflpi/ingestion/news/match.py and run.py only.
REQUIREMENT:
 1. In match.py compile the TEAM and PLAYER patterns WITHOUT re.I from the casefolded phrases (they are already casefold keys), and run them on `f"{title} {extract}".casefold()`; keep the (?<!\w) / (?!\w) boundaries; a hit's text is then always a dict key. The tag regexes (which only test presence) keep re.I on the original text. A headline must never be able to raise inside tie().
 2. In run.py call store.prune(session, now) in the 304 branch as well (a successful poll of any kind prunes).
PROOF: `bash docs/gauntlet/logs/step-8c-evidence/pure.sh` ends "PURE OK"; `cd backend && .venv/bin/python -c "import nflpi.ingestion.news.run"`. The coordinator runs the database tests.
CONSTRAINTS: smallest diff, nothing else touched. DO NOT commit, push, install, use the network.
RETURN: the changed lines.
