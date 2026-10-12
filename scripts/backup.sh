#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
keep=${BACKUP_KEEP:-14}
if [[ ! "$keep" =~ ^[1-9][0-9]*$ ]]; then
  echo "BACKUP_KEEP must be a positive number" >&2
  exit 1
fi
mkdir -p backups
file="backups/nflpi-$(date +%Y%m%d-%H%M%S).sql.gz"
while [[ -e "$file" ]]; do
  sleep 1
  file="backups/nflpi-$(date +%Y%m%d-%H%M%S).sql.gz"
done
part="$file.part"
local_ready=0
trap 'rm -f "$part"; if [[ "$local_ready" != 1 ]]; then rm -f "$file"; fi' EXIT
docker compose exec -T db pg_dump -U nflpi nflpi | gzip > "$part"
[[ -s "$part" ]]
gzip -t "$part"
mv "$part" "$file"

count=0
while IFS= read -r old; do
  count=$((count + 1))
  if (( count > keep )); then rm -f "$old"; fi
done < <(printf '%s\n' backups/nflpi-*.sql.gz | sort -r)

local_ready=1
if [[ -n "${BACKUP_COPY_DIR:-}" ]]; then
  if ! mkdir -p "$BACKUP_COPY_DIR" || ! cp "$file" "$BACKUP_COPY_DIR/"; then
    echo "copy failed: $file to $BACKUP_COPY_DIR" >&2
    exit 1
  fi
fi
echo "saved $file"
