#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 || "$2" != --yes || ! -f "$1" ]]; then
  echo "usage: $0 <file.sql.gz> --yes (replaces all current data)" >&2
  exit 1
fi
file=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
gzip -t "$file" || { echo "invalid gzip file: $file" >&2; exit 1; }

cd "$(dirname "$0")/.."
docker compose stop app worker
docker compose exec -T db psql -U nflpi -d postgres -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'nflpi' AND pid <> pg_backend_pid();"
docker compose exec -T db psql -U nflpi -d postgres -v ON_ERROR_STOP=1 -c 'DROP DATABASE IF EXISTS nflpi'
docker compose exec -T db psql -U nflpi -d postgres -v ON_ERROR_STOP=1 -c 'CREATE DATABASE nflpi OWNER nflpi'
if ! gzip -dc "$file" | docker compose exec -T db psql -U nflpi -d nflpi -v ON_ERROR_STOP=1 -1; then
  echo "restore failed; database is now empty. Retry with: $file" >&2
  exit 1
fi
docker compose up -d app worker
echo "restored $file"
