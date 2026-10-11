#!/usr/bin/env sh
# Nightly-friendly database backup: ./scripts/backup.sh  (keeps the last 14)
set -eu
mkdir -p backups
file="backups/nflpi-$(date +%Y%m%d-%H%M%S).sql.gz"
docker compose exec -T db pg_dump -U nflpi nflpi | gzip > "$file"
ls -1t backups/*.sql.gz | tail -n +15 | xargs -r rm --
echo "saved $file"
