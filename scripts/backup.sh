#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
keep=${BACKUP_KEEP:-14}
if [[ ! "$keep" =~ ^[1-9][0-9]*$ ]]; then
  echo "BACKUP_KEEP must be a positive number" >&2
  exit 1
fi
mkdir -p backups
file="backups/nflpi-$(date +%Y%m%d-%H%M%S)-$$.sql.gz"
if [[ -e "$file" ]]; then
  echo "backup already exists: $file" >&2
  exit 1
fi
part=$(mktemp backups/.nflpi.XXXXXX)
copy_part=''
finalized=0
cleanup() {
  local status=$?
  rm -f "$part"
  if [[ -n "$copy_part" ]]; then rm -f "$copy_part"; fi
  if (( status != 0 && finalized == 0 )); then rm -f "$file"; fi
}
trap cleanup EXIT
mv "$part" "$part.part"
part="$part.part"

if ! docker compose exec -T db pg_dump -U nflpi nflpi | gzip > "$part"; then
  echo "backup failed: pg_dump or gzip failed" >&2
  exit 1
fi
if ! gzip -t "$part"; then
  echo "backup failed: gzip file is corrupt" >&2
  exit 1
fi
if ! gzip -dc "$part" | tail -n 20 | awk 'index($0, "PostgreSQL database dump complete") { found=1 } END { exit !found }'; then
  echo "backup failed: dump has no completion trailer" >&2
  exit 1
fi
if ! gzip -dc "$part" | awk '/^COPY public[.]games [(]/ { in_games=1; next } in_games && /^\\[.]$/ { in_games=0 } in_games { found=1 } END { exit !found }'; then
  echo "backup failed: dump has no games rows" >&2
  exit 1
fi

mv "$part" "$file"
finalized=1

retain() {
  local dir=$1 newest=$2 old count=0
  while IFS= read -r old; do
    [[ "$old" == "$newest" ]] && continue
    count=$((count + 1))
    if (( count >= keep )); then rm -f "$old"; fi
  done < <(ls -1t "$dir"/nflpi-*.sql.gz)
}

if [[ -n "${BACKUP_COPY_DIR:-}" ]]; then
  copy_file="$BACKUP_COPY_DIR/$(basename "$file")"
  copy_part="$BACKUP_COPY_DIR/.$(basename "$file").part"
  if ! mkdir -p "$BACKUP_COPY_DIR" || ! cp "$file" "$copy_part" || ! cmp -s "$file" "$copy_part" || ! mv "$copy_part" "$copy_file"; then
    echo "backup copy failed: $file to $BACKUP_COPY_DIR" >&2
    exit 1
  fi
  copy_part=''
fi

retain backups "$file"
if [[ -n "${BACKUP_COPY_DIR:-}" ]]; then retain "$BACKUP_COPY_DIR" "$copy_file"; fi

echo "saved $file"
