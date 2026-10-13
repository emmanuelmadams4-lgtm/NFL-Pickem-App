#!/bin/bash
# after the rebase onto main 43dfc46: wait for res:gate-b, gate x2 (labels r1, r2) plus alembic on a scratch database, release.
C(){ /Users/emmanueladams/.claude/plugins/cache/local-mods/coord/0.1.0/bin/coord -C /Users/emmanueladams/Projects/NFL-Pickem-App --session livegrade "$@"; }
E=docs/gauntlet/logs/step-15f-evidence
until ! C lock res:gate-b 2>&1 | grep -q rejected; do C register >/dev/null 2>&1; echo "$(date +%T) waiting" > $E/run2.log; sleep 20; done
( while true; do sleep 45; C register >/dev/null 2>&1; C lock res:gate-b >/dev/null 2>&1; done ) & R=$!
echo "$(date +%T) got lock" > $E/run2.log
./$E/gate.sh r1; echo "$(date +%T) r1 done" >> $E/run2.log
./$E/gate.sh r2; echo "$(date +%T) r2 done" >> $E/run2.log
docker exec nflpi-lane-live-db psql -U nflpi -d postgres -qc "drop database if exists nflpi_alembic" -c "create database nflpi_alembic" >/dev/null 2>&1
( cd backend; export DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15447/nflpi_alembic; uv run alembic upgrade head 2>&1 | tail -1; uv run alembic check 2>&1 | tail -1 ) > ../$E/alembic-r.log 2>&1
docker exec nflpi-lane-live-db psql -U nflpi -d postgres -qc "drop database if exists nflpi_alembic" >/dev/null 2>&1
kill $R; C unlock res:gate-b >> $E/run2.log 2>&1; echo "$(date +%T) released" >> $E/run2.log
