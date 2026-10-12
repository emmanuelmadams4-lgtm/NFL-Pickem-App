#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 || "$2" != --yes ]]; then
  echo "usage: $0 <file.sql.gz> --yes" >&2
  exit 1
fi
if [[ ! -f "$1" || ! -r "$1" ]]; then
  echo "restore refused: file is not readable: $1" >&2
  exit 1
fi
file=$(cd "$(dirname "$1")" && pwd -P)/$(basename "$1")
if ! gzip -t "$file"; then
  echo "restore refused: invalid gzip file: $file" >&2
  exit 1
fi
if ! gzip -dc "$file" | tail -n 20 | awk 'index($0, "PostgreSQL database dump complete") { found=1 } END { exit !found }'; then
  echo "restore refused: dump has no completion trailer" >&2
  exit 1
fi
if ! gzip -dc "$file" | awk '/^CREATE TABLE public[.]games [(]/ { found=1 } END { exit !found }'; then
  echo "restore refused: dump does not create public.games" >&2
  exit 1
fi

cd "$(dirname "$0")/.."
mkdir -p backups
scratch_exists=0
restart_needed=0
swap_done=0
swap_uncertain=0
current_exists=0
safety_part=''
safety_file=''
safety_note='no safety copy (database nflpi did not exist)'
failure='restore failed'

# ShellCheck does not see functions called by EXIT traps.
# shellcheck disable=SC2329
on_exit() {
  local status=$? cleanup_ok=1
  local names
  trap - EXIT
  if [[ -n "$safety_part" ]]; then rm -f "$safety_part" || cleanup_ok=0; fi
  if (( status != 0 && swap_uncertain )); then
    if names=$(docker compose exec -T db psql -U nflpi -d postgres -v ON_ERROR_STOP=1 -At -c "SELECT dbname || '=' || CASE WHEN EXISTS (SELECT 1 FROM pg_database WHERE datname = dbname) THEN 'exists' ELSE 'missing' END FROM (VALUES ('nflpi'), ('nflpi_old'), ('nflpi_restore')) AS dbs(dbname)"); then
      echo "database names after interrupted swap:" >&2
      echo "$names" >&2
    else
      echo "could not check database names after interrupted swap" >&2
    fi
    echo "$failure; swap state is uncertain; $safety_note" >&2
    echo "run: docker compose exec db psql -U nflpi -d postgres -c '\l' and see docs/DEPLOY.md (If a restore stops with a message about nflpi_old)" >&2
  elif (( status != 0 && swap_done )); then
    if (( current_exists )); then
      echo "restore was interrupted after the swap; the restored data is live; old data is kept in nflpi_old; $safety_note; run docker compose up -d and check health" >&2
    else
      echo "restore was interrupted after the swap; the restored data is live; no old database existed; $safety_note; run docker compose up -d and check health" >&2
    fi
  elif (( status != 0 )); then
    if (( scratch_exists )); then
      if ! docker compose exec -T db psql -U nflpi -d postgres -v ON_ERROR_STOP=1 -c 'DROP DATABASE IF EXISTS nflpi_restore WITH (FORCE)' >/dev/null; then
        echo "could not remove scratch database nflpi_restore" >&2
        cleanup_ok=0
      fi
    fi
    if (( restart_needed )); then
      if ! docker compose up -d app worker; then
        echo "could not restart app and worker" >&2
        cleanup_ok=0
      fi
    fi
    if (( cleanup_ok )); then
      if (( restart_needed )); then
        echo "$failure; live data was not replaced; restart requested for app and worker" >&2
      else
        echo "$failure; nothing was changed, the app was not touched" >&2
      fi
    else
      echo "$failure; check scratch database and app state" >&2
    fi
  fi
  exit "$status"
}
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
trap on_exit EXIT

failure='could not check for an older restore database'
old_exists=$(docker compose exec -T db psql -U nflpi -d postgres -v ON_ERROR_STOP=1 -At -c "SELECT count(*) FROM pg_database WHERE datname = 'nflpi_old'")
if [[ "$old_exists" != 0 ]]; then
  failure="nflpi_old already exists; look at the names with docker compose exec db psql -U nflpi -d postgres -c '\l'; if nflpi is missing, rename nflpi_old back (ALTER DATABASE nflpi_old RENAME TO nflpi); otherwise drop nflpi_old only after checking the safety copy"
  exit 1
fi

scratch_exists=1
failure='could not prepare scratch database'
docker compose exec -T db psql -U nflpi -d postgres -v ON_ERROR_STOP=1 -c 'DROP DATABASE IF EXISTS nflpi_restore WITH (FORCE)' >/dev/null
docker compose exec -T db psql -U nflpi -d postgres -v ON_ERROR_STOP=1 -c 'CREATE DATABASE nflpi_restore OWNER nflpi' >/dev/null

failure='scratch restore load failed'
gzip -dc "$file" | docker compose exec -T db psql -U nflpi -d nflpi_restore -v ON_ERROR_STOP=1 -1 >/dev/null

failure='could not count games in scratch database'
scratch_games=$(docker compose exec -T db psql -U nflpi -d nflpi_restore -v ON_ERROR_STOP=1 -At -c 'SELECT count(*) FROM games')
if [[ ! "$scratch_games" =~ ^[0-9]+$ ]]; then
  echo "invalid games count in scratch database: $scratch_games" >&2
  exit 1
fi
if (( scratch_games == 0 )); then
  failure='this backup has no games'
  exit 1
fi

failure='could not check whether database nflpi exists'
current_exists=$(docker compose exec -T db psql -U nflpi -d postgres -v ON_ERROR_STOP=1 -At -c "SELECT count(*) FROM pg_database WHERE datname = 'nflpi'")
if [[ "$current_exists" != 0 && "$current_exists" != 1 ]]; then
  echo "invalid current database count: $current_exists" >&2
  exit 1
fi

restart_needed=1
failure='could not stop app and worker'
docker compose stop app worker

if (( current_exists )); then
  safety_file="backups/pre-restore-$(date +%Y%m%d-%H%M%S)-$$.sql.gz"
  failure='safety copy failed'
  if [[ -e "$safety_file" ]]; then
    echo "safety copy already exists: $safety_file" >&2
    exit 1
  fi
  safety_part=$(mktemp backups/.nflpi.XXXXXX)
  mv "$safety_part" "$safety_part.part"
  safety_part="$safety_part.part"
  docker compose exec -T db pg_dump -U nflpi nflpi | gzip > "$safety_part"
  gzip -t "$safety_part"
  if ! gzip -dc "$safety_part" | tail -n 20 | awk 'index($0, "PostgreSQL database dump complete") { found=1 } END { exit !found }'; then
    echo "safety copy has no completion trailer" >&2
    exit 1
  fi
  mv "$safety_part" "$safety_file"
  safety_part=''
  safety_note="safety copy: $safety_file"
fi

failure='database swap failed'
swap_uncertain=1
if (( current_exists )); then
  docker compose exec -T db psql -U nflpi -d postgres -v ON_ERROR_STOP=1 >/dev/null <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('nflpi', 'nflpi_restore') AND pid <> pg_backend_pid();
ALTER DATABASE nflpi RENAME TO nflpi_old;
ALTER DATABASE nflpi_restore RENAME TO nflpi;
SQL
else
  docker compose exec -T db psql -U nflpi -d postgres -v ON_ERROR_STOP=1 >/dev/null <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'nflpi_restore' AND pid <> pg_backend_pid();
ALTER DATABASE nflpi_restore RENAME TO nflpi;
SQL
fi

failure='could not confirm database swap'
swap_state=$(docker compose exec -T db psql -U nflpi -d postgres -v ON_ERROR_STOP=1 -At -F ',' -c "SELECT (SELECT count(*) FROM pg_database WHERE datname = 'nflpi'), (SELECT count(*) FROM pg_database WHERE datname = 'nflpi_old'), (SELECT count(*) FROM pg_database WHERE datname = 'nflpi_restore')")
if (( current_exists )); then
  expected_state='1,1,0'
else
  expected_state='1,0,0'
fi
if [[ "$swap_state" != "$expected_state" ]]; then
  echo "unexpected database names after swap: $swap_state" >&2
  exit 1
fi
swap_done=1
scratch_exists=0
swap_uncertain=0

if ! docker compose up -d app worker; then
  failure='restore swapped databases, but app or worker did not start'
  exit 1
fi

deadline=$((SECONDS + 180))
while (( SECONDS < deadline )); do
  if docker compose exec -T app python -c 'import json, sys, urllib.request; sys.exit(0 if json.load(urllib.request.urlopen("http://localhost:8000/api/health", timeout=5)).get("database") is True else 1)' >/dev/null 2>&1; then
    if (( current_exists )); then
      failure='restore is healthy, but could not remove nflpi_old'
      docker compose exec -T db psql -U nflpi -d postgres -v ON_ERROR_STOP=1 -c 'DROP DATABASE nflpi_old WITH (FORCE)' >/dev/null
    fi
    echo "restored $file"
    exit 0
  fi
  sleep 2
done
failure='restore timed out waiting for database health'
exit 1
