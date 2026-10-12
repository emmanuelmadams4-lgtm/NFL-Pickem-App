#!/usr/bin/env bash
# Deploy gate (roadmap step 5). Proves a clean clone of the committed code runs, can be backed up and restored,
# and behaves behind a TLS proxy. It uses its own compose project, ports and volume, so a live stack is never touched.
#   ./scripts/deploy-check.sh          (commit first: it clones HEAD, not your working tree)
# Env: DEPLOYCHECK_APP_PORT (18000), DEPLOYCHECK_DB_PORT (15432), KEEP=1 keeps the clone and stack for inspection.
set -eEuo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
APP_PORT=${DEPLOYCHECK_APP_PORT:-18000}
DB_PORT=${DEPLOYCHECK_DB_PORT:-15432}
unset BACKUP_COPY_DIR BACKUP_KEEP
export COMPOSE_PROJECT_NAME=nflpi-deploycheck APP_PORT DB_PORT
BASE="http://127.0.0.1:$APP_PORT"
WORK=$(mktemp -d)
CLONE="$WORK/clone"

pass() { echo "PASS $*"; }
fail() { echo "FAIL $*"; exit 1; }
dc() { (cd "$CLONE" && docker compose "$@"); }
api() { curl -fsS -H "Authorization: Bearer $TOKEN" "$BASE/api/$1"; }
json() { python3 -c "import json,sys; d=json.load(sys.stdin); print($1)"; }
counts() { dc exec -T db psql -U nflpi -d nflpi -Atc "select (select count(*) from user_picks)||','||(select count(*) from predictions)||','||(select count(*) from games)"; }
running() { # fails loudly if docker itself errors, so an error never reads as "not running"
  local out; out=$(dc ps --status running -q "$1") || fail "docker compose ps failed while checking $1"
  [ -n "$out" ]
}
leftovers() { dc exec -T db psql -U nflpi -d postgres -Atc "select count(*) from pg_database where datname in ('nflpi_restore','nflpi_old')" | tr -d ' '; }
wait_health() { # $1 = python expression over d (health json) that must be truthy, $2 = seconds
  for _ in $(seq 1 "$2"); do
    if curl -fsS "$BASE/api/health" 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if ($1) else 1)" 2>/dev/null; then return 0; fi
    sleep 1
  done
  return 1
}
cleanup() {
  if [ "${KEEP:-0}" = 1 ]; then echo "KEEP=1: clone at $CLONE, project $COMPOSE_PROJECT_NAME"; return; fi
  [ -d "$CLONE" ] && (cd "$CLONE" && docker compose down -v --remove-orphans --rmi local >/dev/null 2>&1 || true)
  rm -rf "$WORK"
}
trap cleanup EXIT
trap 'fail "unexpected error at line $LINENO"' ERR

stale=$(docker ps -aq --filter label=com.docker.compose.project=nflpi-deploycheck 2>/dev/null || true)
[ -z "$stale" ] || docker rm -f $stale >/dev/null 2>&1 || true
docker volume rm -f nflpi-deploycheck_pgdata >/dev/null 2>&1 || true

# --- D0 inputs -------------------------------------------------------------------------------------------------
for tool in docker git curl python3 node; do command -v "$tool" >/dev/null || fail "D0 $tool is not installed"; done
[ -z "$(git -C "$ROOT" status --porcelain)" ] || fail "D0 working tree is dirty: commit first, the gate tests a clean clone of HEAD"
git clone -q --no-hardlinks -b "$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)" "$ROOT" "$CLONE"
pass "D0 clean clone of $(git -C "$CLONE" rev-parse --short HEAD)"

# --- D1 static checks on the clone (cheap, run before any build) -------------------------------------------------
TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
PGPASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
python3 - "$CLONE" "$TOKEN" "$PGPASS" <<'PY'
import pathlib, sys
clone, token, pg = sys.argv[1:4]
text = (pathlib.Path(clone) / ".env.example").read_text()
out = []
for line in text.splitlines():
    if line.startswith("POSTGRES_PASSWORD="): line = f"POSTGRES_PASSWORD={pg}"
    elif line.startswith("DATABASE_URL="): line = f"DATABASE_URL=postgresql+psycopg://nflpi:{pg}@db:5432/nflpi"
    elif line.startswith("APP_ACCESS_TOKEN="): line = f"APP_ACCESS_TOKEN={token}"
    out.append(line)
(pathlib.Path(clone) / ".env").write_text("\n".join(out) + "\n")
PY
git -C "$CLONE" check-ignore -q .env || fail "D1 .env is not git-ignored"
dc config --format json | python3 -E -c "
import json, sys
c = json.load(sys.stdin)['services']
want = {'app': '$APP_PORT', 'db': '$DB_PORT'}
for name, port in want.items():
    published = [p.get('published') for p in c[name].get('ports', [])]
    assert port in published, f'{name} ports {published} do not follow {port}: a second stack would collide with a live one'
    hosts = [p.get('host_ip') for p in c[name].get('ports', [])]
    assert hosts and all(h == '127.0.0.1' for h in hosts), f'{name} is published on {hosts}, not only 127.0.0.1'
for name in ('app', 'worker', 'db'):
    assert c[name].get('restart') == 'unless-stopped', f'{name} does not restart by itself after a reboot or power cut'
" || fail "D1 compose file: ports must follow APP_PORT/DB_PORT and every service restart: unless-stopped"
for f in scripts/backup.sh scripts/restore.sh; do [ -x "$CLONE/$f" ] || fail "D1 $f is missing or not executable"; done
[ -s "$CLONE/docs/DEPLOY.md" ] || fail "D1 docs/DEPLOY.md is missing"
grep -qi "rotate" "$CLONE/docs/DEPLOY.md" && grep -qi "windows" "$CLONE/docs/DEPLOY.md" && grep -qi "restore" "$CLONE/docs/DEPLOY.md" \
  || fail "D1 docs/DEPLOY.md must cover Windows PC setup, restore and token rotation"
python3 -E - "$CLONE/docs/IPHONE_PWA.md" <<'PY' || fail "D1 IPHONE_PWA.md must say: add to Home Screen first, then sign in inside the app"
import re, sys
t = open(sys.argv[1]).read().lower()
home = t.find("add to home screen")
signin = t.find("sign in", home + 1) if home >= 0 else -1
assert home >= 0 and signin > home, "sign-in step must come after Add to Home Screen"
assert "separate" in t or "does not share" in t or "not shared" in t, "explain that Safari and the Home Screen app keep separate storage"
PY
pass "D1 compose ports/restart, scripts, runbook and iPhone order"

# --- D2 clean clone -> running app -----------------------------------------------------------------------------------
dc up -d --build >/dev/null 2>&1 || { dc logs --tail 30 2>&1 | tail -30; fail "D2 docker compose up -d --build"; }
wait_health "d['database'] is True and d.get('worker_heartbeat')" 180 \
  || { dc logs --tail 20 2>&1 | tail -20; fail "D2 health never showed database up and a worker heartbeat"; }
pass "D2 up from a clean clone; database ok, worker heartbeat present"

# --- D3 bootstrap -> health ok ---------------------------------------------------------------------------------------
dc exec -T app python -m nflpi.jobs bootstrap >"$WORK/bootstrap.log" 2>&1 || { tail -20 "$WORK/bootstrap.log"; fail "D3 bootstrap"; }
# Only the outside weather feed may be stale (it is a third-party service, not part of the deploy); anything else must be ok.
HEALTH_OK="d['database'] is True and d['active_model'] is True and d.get('worker_heartbeat') and (d['status'] == 'ok' or d.get('stale_datasets') == ['weather'])"
wait_health "$HEALTH_OK" 120 || { curl -fsS "$BASE/api/health"; fail "D3 health is not ok after bootstrap"; }
pass "D3 bootstrap; health $(curl -fsS "$BASE/api/health" | json "d['status'] + (' (weather feed stale, outside service)' if d['status'] != 'ok' else '')")"

# --- D4 web files and headers ----------------------------------------------------------------------------------------
[ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/")" = 200 ] || fail "D4 / is not 200"
curl -fsS "$BASE/manifest.webmanifest" | json "d['start_url'], d.get('scope')" >/dev/null || fail "D4 manifest missing"
sw_headers=$(curl -fsSI "$BASE/sw.js")
echo "$sw_headers" | grep -qi "javascript" || fail "D4 sw.js is not served as JavaScript"
echo "$sw_headers" | grep -qiE "cache-control:.*(no-cache|no-store|max-age=0)" || fail "D4 sw.js can be cached, so updates would not reach the phone"
pass "D4 page, manifest, and a non-cacheable sw.js"

# --- D5 behind a TLS-terminating proxy: no http:// redirects ----------------------------------------------------------
bad=0
for path in / /settings /settings/ /results /results/ /backtest /backtest/ /api/health; do
  loc=$(curl -s -o /dev/null -D- -H "Host: pickem.example.ts.net" -H "X-Forwarded-Proto: https" -H "X-Forwarded-Host: pickem.example.ts.net" \
        "$BASE$path" | tr -d '\r' | awk 'tolower($1)=="location:"{print $2}')
  case "$loc" in http://*) echo "  $path -> $loc"; bad=1 ;; esac
done
[ "$bad" = 0 ] || fail "D5 a redirect sends the browser back to http:// when the proxy is https"
(cd "$ROOT" && [ -d node_modules/playwright-core ]) || fail "D5 run 'npm ci' in $ROOT first (playwright-core is needed for the service-worker check)"
(cd "$ROOT" && node scripts/deploy-check-sw.mjs "$BASE" "$TOKEN") || fail "D5 service worker did not register inside the manifest scope"
pass "D5 no http:// redirects behind an https proxy; service worker registers"

# --- D6 all 32 team logos load from the server's own network ---------------------------------------------------------
season=$(api meta | json "d['current_season']")
urls=$(for w in $(api meta | json "' '.join(map(str, d['weeks']))"); do api "weeks/$season/$w"; echo; done | python3 -c "
import json, sys
logos = {}
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    for g in json.loads(line)['games']:
        for side in ('home', 'away'):
            t = g[side]
            logos[t['abbr']] = t['logo_url']
print(len([u for u in logos.values() if u]), file=sys.stderr)
print('\n'.join(logos.values()))
" 2>"$WORK/logo-count")
[ "$(cat "$WORK/logo-count")" = 32 ] || fail "D6 expected 32 teams with a logo url, found $(cat "$WORK/logo-count")"
echo "$urls" | dc exec -T app python -c "
import sys, urllib.request
bad = []
for url in sys.stdin.read().split():
    try: ok = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=15).status == 200
    except Exception: ok = False
    if not ok: bad.append(url)
print('bad logos:', bad) if bad else None
sys.exit(1 if bad else 0)
" || fail "D6 some team logos do not load"
pass "D6 32 of 32 team logos return 200 from the server"

# --- D7 backup -> restore, counts match; failure and off-host copy -----------------------------------------------------
picked=0
while read -r gid home; do
  if curl -fsS -X PUT -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{\"team\":\"$home\"}" "$BASE/api/picks/$gid" >/dev/null 2>&1; then picked=1; break; fi
done < <(api "weeks/$season/$(api meta | json "d['current_week']")" | json "'\n'.join(g['game_id'] + ' ' + g['home']['abbr'] for g in d['games'])")
[ "$picked" = 1 ] || fail "D7 could not save a test pick (no open game this week)"
before=$(counts)
case "$before" in 0,*|*,0,*|*,0) fail "D7 expected picks, predictions and games above zero, got $before" ;; esac
OFFHOST="$WORK/offhost"; mkdir -p "$OFFHOST"
mkdir -p "$WORK/offhost-no-marker"
if (cd "$CLONE" && BACKUP_COPY_DIR="$WORK/offhost-no-marker" ./scripts/backup.sh) >/dev/null 2>&1; then fail "D7 backup.sh copied into a folder with no .pickem-backups marker (an empty mount point of an unplugged drive would look fine)"; fi
[ -z "$(ls -A "$WORK/offhost-no-marker")" ] || fail "D7 backup.sh wrote into a folder with no .pickem-backups marker"
touch "$OFFHOST/.pickem-backups"
if (cd "$CLONE" && BACKUP_COPY_DIR="$WORK/not-plugged-in" ./scripts/backup.sh) >/dev/null 2>&1; then fail "D7 backup.sh treated a missing BACKUP_COPY_DIR as success (an unplugged drive would go unnoticed)"; fi
[ ! -e "$WORK/not-plugged-in" ] || fail "D7 backup.sh created a missing BACKUP_COPY_DIR"
(cd "$CLONE" && BACKUP_COPY_DIR="$OFFHOST" ./scripts/backup.sh) >"$WORK/backup.log" 2>&1 || { cat "$WORK/backup.log"; fail "D7 backup.sh"; }
file=$(ls -1t "$CLONE"/backups/*.sql.gz | head -1)
gzip -t "$file" && [ -s "$file" ] || fail "D7 backup file is empty or corrupt"
cmp -s "$file" "$OFFHOST/$(basename "$file")" || fail "D7 off-host copy is missing or differs (BACKUP_COPY_DIR)"
dc exec -T db psql -U nflpi -d nflpi -qc "delete from user_picks; delete from predictions where id = (select max(id) from predictions);" >/dev/null
[ "$(counts)" != "$before" ] || fail "D7 test could not change the data"
(cd "$CLONE" && ./scripts/restore.sh "$file" --yes) >"$WORK/restore.log" 2>&1 || { tail -20 "$WORK/restore.log"; fail "D7 restore.sh"; }
wait_health "d['database'] is True" 120 || fail "D7 app did not come back after restore"
running worker && running app || fail "D7 app or worker is not running after restore"
[ "$(leftovers)" = 0 ] || fail "D7 scratch or old database left behind after restore"
after=$(counts)
[ "$after" = "$before" ] || fail "D7 counts after restore $after differ from before $before"
ls "$CLONE"/backups/pre-restore-*.sql.gz >/dev/null 2>&1 || fail "D7 restore.sh did not keep a safety copy of the data it replaced"
for safety in "$CLONE"/backups/pre-restore-*.sql.gz; do gzip -t "$safety" || fail "D7 safety copy is corrupt"; done

# A bad file must be refused, or fail, with the live data intact and the app running.
printf 'not a dump' | gzip > "$WORK/notdump.sql.gz"
gzip -c < /dev/null > "$WORK/empty.sql.gz"
gzip -dc "$file" | sed 's/^COPY public\.games /COPY public.no_such_table /' | gzip > "$WORK/broken.sql.gz"
cmp -s <(gzip -dc "$file") <(gzip -dc "$WORK/broken.sql.gz") && fail "D7 test could not corrupt the dump"
for bad in notdump empty broken; do
  if (cd "$CLONE" && ./scripts/restore.sh "$WORK/$bad.sql.gz" --yes) >"$WORK/restore-$bad.log" 2>&1; then fail "D7 restore.sh accepted a $bad file"; fi
  wait_health "d['database'] is True and d.get('worker_heartbeat')" 120 || fail "D7 app is not running after a refused $bad restore"
  running worker || fail "D7 worker is not running after a refused $bad restore"
  [ "$(counts)" = "$before" ] || fail "D7 a refused $bad restore changed the data: $(counts) vs $before"
  [ "$(leftovers)" = 0 ] || fail "D7 a refused $bad restore left a scratch database behind"
done
# Two backups started together must both succeed and both be good, with no half files left anywhere.
n0=$(( $(ls -1 "$CLONE"/backups/nflpi-*.sql.gz | wc -l) ))
(cd "$CLONE" && ./scripts/backup.sh >/dev/null 2>&1) & p1=$!
(cd "$CLONE" && BACKUP_COPY_DIR="$OFFHOST" ./scripts/backup.sh >/dev/null 2>&1) & p2=$!
wait "$p1" || fail "D7 first of two simultaneous backups failed"
wait "$p2" || fail "D7 second of two simultaneous backups failed"
[ "$(( $(ls -1 "$CLONE"/backups/nflpi-*.sql.gz | wc -l) ))" = "$((n0 + 2))" ] || fail "D7 two simultaneous backups did not leave two files"
for f in "$CLONE"/backups/nflpi-*.sql.gz "$OFFHOST"/*.sql.gz; do gzip -t "$f" || fail "D7 corrupt backup $f"; done
[ -z "$(find "$CLONE/backups" "$OFFHOST" -name '*.part*' 2>/dev/null)" ] || fail "D7 a half-written backup file was left behind"
# A dump that stops early (no pg_dump trailer) is not a complete backup.
gzip -dc "$file" | sed '/^-- PostgreSQL database dump complete/,$d' | gzip > "$WORK/truncated.sql.gz"
if (cd "$CLONE" && ./scripts/restore.sh "$WORK/truncated.sql.gz" --yes) >/dev/null 2>&1; then fail "D7 restore.sh accepted a dump with no completion trailer"; fi
wait_health "d['database'] is True and d.get('worker_heartbeat')" 120 && [ "$(counts)" = "$before" ] || fail "D7 a truncated dump changed the data or stopped the app"
dc stop db >/dev/null 2>&1
n_before_all=$(ls -1A "$CLONE"/backups | wc -l)
if (cd "$CLONE" && ./scripts/backup.sh) >/dev/null 2>&1; then fail "D7 backup.sh exited 0 with the database stopped (pipefail missing)"; fi
[ "$(ls -1A "$CLONE"/backups | wc -l)" = "$n_before_all" ] || fail "D7 a failed backup left a file behind"
dc start db >/dev/null 2>&1
wait_health "d['database'] is True" 120 || fail "D7 database did not come back"
# An empty-looking database must not become a "good" backup that pushes real ones out of the rotation.
dc exec -T db psql -U nflpi -d nflpi -qc "truncate games cascade" >/dev/null
all_before=$(ls -1A "$CLONE"/backups | wc -l)
if (cd "$CLONE" && ./scripts/backup.sh) >/dev/null 2>&1; then fail "D7 backup.sh saved a database with no games"; fi
[ "$(ls -1A "$CLONE"/backups | wc -l)" = "$all_before" ] || fail "D7 backing up an empty database changed the backup folder"
safeties=$(ls -1 "$CLONE"/backups/pre-restore-*.sql.gz | wc -l | tr -d ' ')
(cd "$CLONE" && ./scripts/restore.sh "$file" --yes) >"$WORK/restore2.log" 2>&1 || { tail -20 "$WORK/restore2.log"; fail "D7 restore.sh could not recover from an emptied database"; }
wait_health "d['database'] is True" 120 && [ "$(counts)" = "$before" ] || fail "D7 recovery from an emptied database did not return the data"
[ "$(ls -1 "$CLONE"/backups/pre-restore-*.sql.gz | wc -l | tr -d ' ')" = "$((safeties + 1))" ] || fail "D7 no safety copy was kept when the database had no games (other tables can still hold data)"
# The database itself is gone: restore must still work.
dc stop app worker >/dev/null 2>&1
dc exec -T db psql -U nflpi -d postgres -qc "DROP DATABASE nflpi WITH (FORCE)" >/dev/null
(cd "$CLONE" && ./scripts/restore.sh "$file" --yes) >"$WORK/restore3.log" 2>&1 || { tail -20 "$WORK/restore3.log"; fail "D7 restore.sh could not recover when the database was missing"; }
wait_health "d['database'] is True" 120 && [ "$(counts)" = "$before" ] && running worker || fail "D7 recovery from a missing database did not return the data and the worker"
[ "$(leftovers)" = 0 ] || fail "D7 scratch or old database left behind after recovery"
# A restore killed after the app was stopped (SIGTERM) must restart the app by itself and leave the live data alone.
dc exec -T db psql -U nflpi -d nflpi -qc "delete from user_picks" >/dev/null
mutated=$(counts)
[ "$mutated" != "$before" ] || fail "D7 test could not change the live data before the kill test"
(cd "$CLONE" && exec ./scripts/restore.sh "$file" --yes) >"$WORK/restore4.log" 2>&1 & rpid=$!
killed=0
for _ in $(seq 1 300); do
  kill -0 "$rpid" 2>/dev/null || break
  running app || { kill -TERM "$rpid" 2>/dev/null && killed=1; break; }
  sleep 0.2
done
[ "$killed" = 1 ] || fail "D7 test could not catch the restore after the app stopped, so it did not test a killed restore"
rc=0; wait "$rpid" 2>/dev/null || rc=$?
[ "$rc" -ne 0 ] || fail "D7 a restore that was sent SIGTERM exited 0"
grep -q "^restored " "$WORK/restore4.log" && fail "D7 the killed restore still printed 'restored'"
for _ in $(seq 1 150); do running app && running worker && break; sleep 2; done  # up to 300 s: the restart waits for the app health check, and a busy machine is slow
running app && running worker || fail "D7 a killed restore did not start the app and worker again by itself (exit handler)"
[ -s "$WORK/restore4.log" ] && grep -qiE "restart requested|live data" "$WORK/restore4.log" || fail "D7 a killed restore printed no explanation"
wait_health "d['database'] is True" 300 && running worker || { tail -20 "$WORK/restore4.log"; fail "D7 a restore killed mid-way left the app unrecoverable"; }
[ "$(counts)" = "$mutated" ] || fail "D7 a restore killed before the swap changed the live data: $(counts) vs $mutated"
[ -z "$(find "$CLONE/backups" -name '.nflpi.*' 2>/dev/null)" ] || fail "D7 a killed restore left a half-written file in backups/"
(cd "$CLONE" && ./scripts/restore.sh "$file" --yes) >"$WORK/restore5.log" 2>&1 || { tail -20 "$WORK/restore5.log"; fail "D7 a normal restore after a killed one failed"; }
wait_health "d['database'] is True" 120 && [ "$(counts)" = "$before" ] || fail "D7 a normal restore after a killed one did not return the data"
[ "$(leftovers)" = 0 ] || fail "D7 a killed restore left a scratch or old database behind"
pass "D7 backup restored with matching counts ($after); safety copy kept; 4 bad files refused with data intact; killed restore recovers; failed backup fails loudly; off-host copy made"

# --- D8 token rotation -----------------------------------------------------------------------------------------------
NEW=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
sed -i.bak "s/^APP_ACCESS_TOKEN=.*/APP_ACCESS_TOKEN=$NEW/" "$CLONE/.env" && rm -f "$CLONE/.env.bak"
dc up -d --force-recreate app worker >/dev/null 2>&1
wait_health "d['database'] is True" 120 || fail "D8 app did not come back after rotation"
[ "$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $TOKEN" "$BASE/api/meta")" = 401 ] || fail "D8 the old token still works"
[ "$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $NEW" "$BASE/api/meta")" = 200 ] || fail "D8 the new token is refused"
pass "D8 token rotation: old token 401, new token 200"

echo "ALL PASS deploy-check ($(git -C "$CLONE" rev-parse --short HEAD))"
