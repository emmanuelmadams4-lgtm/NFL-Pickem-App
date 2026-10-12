#!/usr/bin/env bash
# Deploy gate (roadmap step 5). Proves a clean clone of the committed code runs, can be backed up and restored,
# and behaves behind a TLS proxy. It uses its own compose project, ports and volume, so a live stack is never touched.
#   ./scripts/deploy-check.sh          (commit first: it clones HEAD, not your working tree)
# Env: DEPLOYCHECK_APP_PORT (18000), DEPLOYCHECK_DB_PORT (15432), KEEP=1 keeps the clone and stack for inspection.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
APP_PORT=${DEPLOYCHECK_APP_PORT:-18000}
DB_PORT=${DEPLOYCHECK_DB_PORT:-15432}
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
wait_health() { # $1 = python expression over d (health json) that must be truthy, $2 = seconds
  for _ in $(seq 1 "$2"); do
    if curl -fsS "$BASE/api/health" 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if ($1) else 1)" 2>/dev/null; then return 0; fi
    sleep 1
  done
  return 1
}
cleanup() {
  if [ "${KEEP:-0}" = 1 ]; then echo "KEEP=1: clone at $CLONE, project $COMPOSE_PROJECT_NAME"; return; fi
  [ -d "$CLONE" ] && (cd "$CLONE" && docker compose down -v --remove-orphans >/dev/null 2>&1 || true)
  rm -rf "$WORK"
}
trap cleanup EXIT

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
dc config --format json | python3 -c "
import json, sys
c = json.load(sys.stdin)['services']
want = {'app': '$APP_PORT', 'db': '$DB_PORT'}
for name, port in want.items():
    published = [p.get('published') for p in c[name].get('ports', [])]
    assert port in published, f'{name} ports {published} do not follow {port}: a second stack would collide with a live one'
for name in ('app', 'worker', 'db'):
    assert c[name].get('restart') == 'unless-stopped', f'{name} does not restart by itself after a reboot or power cut'
" || fail "D1 compose file: ports must follow APP_PORT/DB_PORT and every service restart: unless-stopped"
for f in scripts/backup.sh scripts/restore.sh; do [ -x "$CLONE/$f" ] || fail "D1 $f is missing or not executable"; done
for f in docs/DEPLOY.md; do [ -s "$CLONE/$f" ] || fail "D1 $f is missing"; done
grep -qi "rotate" "$CLONE/docs/DEPLOY.md" && grep -qi "windows" "$CLONE/docs/DEPLOY.md" && grep -qi "restore" "$CLONE/docs/DEPLOY.md" \
  || fail "D1 docs/DEPLOY.md must cover Windows PC setup, restore and token rotation"
python3 - "$CLONE/docs/IPHONE_PWA.md" <<'PY' || fail "D1 IPHONE_PWA.md must say: add to Home Screen first, then sign in inside the app"
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
pass "D2 up from a clean clone; database ok, worker heartbeat fresh"

# --- D3 bootstrap -> health ok ---------------------------------------------------------------------------------------
dc exec -T app python -m nflpi.jobs bootstrap >"$WORK/bootstrap.log" 2>&1 || { tail -20 "$WORK/bootstrap.log"; fail "D3 bootstrap"; }
wait_health "d['status'] == 'ok'" 120 || { curl -fsS "$BASE/api/health"; fail "D3 health is not ok after bootstrap"; }
pass "D3 bootstrap; health ok ($(curl -fsS "$BASE/api/health" | json "d['status']"))"

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
print(len(logos), file=sys.stderr)
print('\n'.join(logos.values()))
" 2>"$WORK/logo-count")
[ "$(cat "$WORK/logo-count")" = 32 ] || fail "D6 expected 32 teams, found $(cat "$WORK/logo-count")"
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
case "$before" in 0,*|*,0,*) fail "D7 expected picks, predictions and games above zero, got $before" ;; esac
OFFHOST="$WORK/offhost"; mkdir -p "$OFFHOST"
(cd "$CLONE" && BACKUP_COPY_DIR="$OFFHOST" ./scripts/backup.sh) >"$WORK/backup.log" 2>&1 || { cat "$WORK/backup.log"; fail "D7 backup.sh"; }
file=$(ls -1t "$CLONE"/backups/*.sql.gz | head -1)
gzip -t "$file" && [ -s "$file" ] || fail "D7 backup file is empty or corrupt"
[ -s "$OFFHOST/$(basename "$file")" ] || fail "D7 off-host copy was not made (BACKUP_COPY_DIR)"
dc exec -T db psql -U nflpi -d nflpi -qc "delete from user_picks; delete from predictions where id = (select max(id) from predictions);" >/dev/null
[ "$(counts)" != "$before" ] || fail "D7 test could not change the data"
(cd "$CLONE" && ./scripts/restore.sh "$file" --yes) >"$WORK/restore.log" 2>&1 || { tail -20 "$WORK/restore.log"; fail "D7 restore.sh"; }
wait_health "d['database'] is True" 120 || fail "D7 app did not come back after restore"
after=$(counts)
[ "$after" = "$before" ] || fail "D7 counts after restore $after differ from before $before"
dc stop db >/dev/null 2>&1
n_before=$(ls -1 "$CLONE"/backups/*.sql.gz | wc -l)
if (cd "$CLONE" && ./scripts/backup.sh) >/dev/null 2>&1; then fail "D7 backup.sh exited 0 with the database stopped (pipefail missing)"; fi
[ "$(ls -1 "$CLONE"/backups/*.sql.gz | wc -l)" = "$n_before" ] || fail "D7 a failed backup left a file behind"
dc start db >/dev/null 2>&1
wait_health "d['database'] is True" 120 || fail "D7 database did not come back"
pass "D7 backup restored with matching counts ($after); a failed backup fails loudly; off-host copy made"

# --- D8 token rotation -----------------------------------------------------------------------------------------------
NEW=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
sed -i.bak "s/^APP_ACCESS_TOKEN=.*/APP_ACCESS_TOKEN=$NEW/" "$CLONE/.env" && rm -f "$CLONE/.env.bak"
dc up -d --force-recreate app worker >/dev/null 2>&1
wait_health "d['database'] is True" 120 || fail "D8 app did not come back after rotation"
[ "$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $TOKEN" "$BASE/api/meta")" = 401 ] || fail "D8 the old token still works"
[ "$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $NEW" "$BASE/api/meta")" = 200 ] || fail "D8 the new token is refused"
pass "D8 token rotation: old token 401, new token 200"

echo "ALL PASS deploy-check ($(git -C "$CLONE" rev-parse --short HEAD))"
