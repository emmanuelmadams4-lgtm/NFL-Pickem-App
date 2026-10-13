#!/bin/bash
# Final gate x2 on the rebased HEAD, under coord lock res:gate (renewed every 40 s).
R=/Users/emmanueladams/Projects/NFL-Pickem-App
C=/Users/emmanueladams/.claude/local-mods/coord/bin/coord
S=4a626b21-dc62-42fd-85dc-cc9b4e6279d1
L=$R/.claude/worktrees/lane-sdk
E=$L/docs/gauntlet/logs/step-17-evidence
cd $R
until $C --session $S lock res:gate 2>&1 | grep -q '"locked"'; do echo "$(date +%T) waiting for res:gate"; sleep 20; done
echo "$(date +%T) got res:gate; HEAD $(git -C $L rev-parse --short HEAD)"
( while true; do sleep 40; (cd $R; $C --session $S lock res:gate >/dev/null 2>&1); done ) & RENEW=$!
trap 'kill $RENEW 2>/dev/null; (cd $R; $C --session $S unlock res:gate >/dev/null 2>&1); echo "$(date +%T) released"' EXIT
export DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15444/nflpi_test
for n in 1 2; do
  cd $L/backend
  uv run pytest -q > $E/rebased$n-pytest.log 2>&1; echo "run$n pytest: $(grep -aE 'passed|failed' $E/rebased$n-pytest.log | tail -1 | sed 's/\x1b\[[0-9;]*m//g')"
  uvx ruff check nflpi tests migrations > $E/rebased$n-ruff.log 2>&1; echo "run$n ruff: $(tail -1 $E/rebased$n-ruff.log)"
  DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15444/nflpi uv run alembic upgrade head >/dev/null 2>&1
  DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15444/nflpi uv run alembic check > $E/rebased$n-alembic.log 2>&1; echo "run$n alembic: $(tail -1 $E/rebased$n-alembic.log)"
  cd $L; npm run gen:api > $E/rebased$n-genapi.log 2>&1; echo "run$n genapi drift: [$(git status --short packages | tr '\n' ' ')]"
done
echo GATE-DONE
