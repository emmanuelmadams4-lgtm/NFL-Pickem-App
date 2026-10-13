Changed the two requested files only:

- `match.py`: TEAM and PLAYER patterns no longer use `re.I`; `tie()` searches casefolded text and uses each hit directly as a dictionary key. Tags still check the original text.
- `run.py`: the 304 branch now calls `store.prune(session, now)`.

Proof: `pure.sh` ended with `PURE OK` (114 passed; database-related errors were reported). The import command completed successfully. The existing untracked `wo-2c-codex.log` was left untouched.