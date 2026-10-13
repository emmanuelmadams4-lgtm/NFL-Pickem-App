"""Step 8i: each wrong change below must make tests/test_star_alerts.py fail. Runs on a copy, never the worktree.
usage: python s8i-mutate.py <worktree/backend> <copy dir> <project dir (backend)>
"""
import os, pathlib, shutil, subprocess, sys

work, copy, project = map(pathlib.Path, sys.argv[1:4])
SA, CFG, JOBS = "nflpi/notify/star_alerts.py", "nflpi/config.py", "nflpi/jobs.py"
M = [  # (label, file, old, new, expected count of old)
    ("A1 same status counts as a change", SA, "return previous is None or previous.report_status != report.report_status", "return True", 1),
    ("A1 first row of the week is ignored", SA, "return previous is None or previous.report_status", "return previous is not None and previous.report_status", 1),
    ("A1 any status counts", SA, "InjuryReport.report_status.in_(stars.ALERT_STATUSES),", "InjuryReport.report_status.is_not(None),", 1),
    ("A1 previous row of another week compared", SA, "InjuryReport.season == report.season, InjuryReport.week == report.week, InjuryReport.team == report.team,", "InjuryReport.season == report.season, InjuryReport.team == report.team,", 1),
    ("A2 baseline always zero", SA, "newest_id = session.scalar(select(func.max(InjuryReport.id))) or 0", "newest_id = 0", 1),
    ("A2 baseline stored without a star list", SA, "if session.scalar(select(TeamStar.team).limit(1)) is None:", "if False:", 1),
    ("A3 sent changes not looked up", SA, 'if _seen(session, f"star:{report.id}", injury_key) or', "if _seen(session, injury_key) or", 1),
    ("A3 step 7 quarterback alert ignored", SA, 'if _seen(session, f"star:{report.id}", injury_key) or', 'if _seen(session, f"star:{report.id}") or', 1),
    ("A3 immediate alert not recorded", SA, 'push._record(session, "star", game.game_id, f"star:{report.id}", {"title": title, "body": body})\n    session.commit()\n    return 1', "return 1", 1),
    ("A4 window opens a second late", SA, "not kickoff - IMMEDIATE_WINDOW <= now < kickoff", "not kickoff - IMMEDIATE_WINDOW < now < kickoff", 1),
    ("A4 window closes after kickoff", SA, "not kickoff - IMMEDIATE_WINDOW <= now < kickoff", "not kickoff - IMMEDIATE_WINDOW <= now <= kickoff", 1),
    ("A4 window is 91 minutes", SA, "IMMEDIATE_WINDOW = timedelta(minutes=90)", "IMMEDIATE_WINDOW = timedelta(minutes=91)", 1),
    ("A4 window is 89 minutes", SA, "IMMEDIATE_WINDOW = timedelta(minutes=90)", "IMMEDIATE_WINDOW = timedelta(minutes=89)", 1),
    ("A4 time to live dropped", SA, "ttl=int((kickoff - now).total_seconds()), ", "", 1),
    ("A4 urgency dropped", SA, 'headers={"Urgency": "high"},', "", 1),
    ("A4b time_tbd game gets its own alert", SA, "if change.game.time_tbd or not kickoff", "if not kickoff", 1),
    ("A4b time_tbd game kept out of the summary", SA, "c.game.time_tbd or c.game.kickoff_utc - IMMEDIATE_WINDOW > now", "c.game.kickoff_utc - IMMEDIATE_WINDOW > now", 1),
    ("A5 games of any status", SA, 'Game.status == "scheduled",', "", 1),
    ("A5 games that kicked off", SA, "Game.kickoff_utc > now,", "", 1),
    ("A6 summary hour excluded", SA, "if not hour <= eastern.hour <", "if not hour < eastern.hour <", 1),
    ("A6 grace 4 hours", SA, "SUMMARY_GRACE_HOURS = 3", "SUMMARY_GRACE_HOURS = 4", 1),
    ("A6 grace 2 hours", SA, "SUMMARY_GRACE_HOURS = 3", "SUMMARY_GRACE_HOURS = 2", 1),
    ("A6 summary clock is UTC", SA, "eastern = now.astimezone(push.EASTERN)", "eastern = now", 1),
    ("A6 summary can repeat the same day", SA, "or _seen(session, key):", ":", 1),
    ("A6 summary day not recorded", SA, 'push._record(session, "starsum", None, key, {"title": title, "body": body})', "pass", 1),
    ("A6 change age 24 hours", SA, "MAX_CHANGE_AGE = timedelta(hours=48)", "MAX_CHANGE_AGE = timedelta(hours=24)", 1),
    ("A6 change age 72 hours", SA, "MAX_CHANGE_AGE = timedelta(hours=48)", "MAX_CHANGE_AGE = timedelta(hours=72)", 1),
    ("A6 oldest status shown", SA, "newest = [max(group, key=lambda c: c.report.id)", "newest = [min(group, key=lambda c: c.report.id)", 1),
    ("A6 only the shown change is used up", SA, "for change in pending:\n        push._record", "for change in [max(g, key=lambda c: c.report.id) for g in groups.values()]:\n        push._record", 1),
    ("A6 summary repeats an immediate alert", SA, "pending = [c for c in changes if c.game.time_tbd or c.game.kickoff_utc - IMMEDIATE_WINDOW > now]", "pending = list(changes)", 1),
    ("A6 summary hour setting ignored", SA, "hour = get_settings().star_summary_hour", "hour = 8", 1),
    ("A6 setting default 9", CFG, "star_summary_hour: int = Field(default=8, ge=0, le=20)", "star_summary_hour: int = Field(default=9, ge=0, le=20)", 1),
    ("A6 setting allows 23", CFG, "ge=0, le=20)", "ge=0, le=23)", 1),
    ("A7 empty summary sent", SA, "    if not groups:\n        return 0\n", "", 1),
    ("A8 summary shows five", SA, "SUMMARY_LINES = 4", "SUMMARY_LINES = 5", 1),
    ("A8 more-count wrong", SA, 'f"+{len(lines) - SUMMARY_LINES} more"', 'f"+{len(lines)} more"', 1),
    ("A8 plural wrong", SA, "'s' if len(lines) != 1 else ''", "'s'", 1),
    ("A8 name cut 50", SA, "NAME_LIMIT = 40", "NAME_LIMIT = 50", 1),
    ("A8 injury cut 70", SA, "INJURY_LIMIT = 60", "INJURY_LIMIT = 70", 1),
    ("A8 format characters kept", SA, 'if not unicodedata.category(ch).startswith("C")', "if unicodedata.category(ch) != 'Cc'", 1),
    ("A8 control characters kept", SA, 'if not unicodedata.category(ch).startswith("C")', "if True", 1),
    ("A8 whitespace not collapsed", SA, 'return " ".join(kept.split())[:limit].strip()', "return kept[:limit].strip()", 1),
    ("A9 failed send recorded", SA, "    if not delivered:\n        return 0\n", "", 1),
    ("A9 failed summary recorded", SA, 'if not push._send(session, title, body, "/"):\n        return 0', 'push._send(session, title, body, "/")', 1),
    ("A9 error text logged in the module", SA, 'log.warning("star alert failed: %s", type(exc).__name__)', 'log.warning("star alert failed: %s", exc)', 2),
    ("A9 an error stops the round", SA, "        except Exception as exc:  # noqa: BLE001 - one bad alert must not stop the others\n            log.warning(\"star alert failed: %s\", type(exc).__name__)\n            session.rollback()", "        except ZeroDivisionError:\n            pass", 1),
    ("A11 name taken from the feed", SA, "name = _plain(star.player, NAME_LIMIT)", "name = _plain(report.player, NAME_LIMIT)", 1),
    ("A12 tick does not call the module", JOBS, "        star_alerts.run(session, now)", "        pass", 1),
    ("A12 tick logs the error text", JOBS, 'log.warning("star alerts failed: %s", type(exc).__name__)', 'log.warning("star alerts failed: %s", exc)', 1),
    ("A12 tick stops on an error", JOBS, "    except Exception as exc:  # noqa: BLE001 - star alert failure must not hide a live worker", "    except ZeroDivisionError as exc:", 1),
    ("A13 status not lower-cased", SA, "report.report_status.lower()", "report.report_status", 1),
    ("A13 injury sentence dropped", SA, '        body += f" {injury}."', "        pass", 1),
    ("A13 link wrong", SA, "push.game_url(game.game_id)", '"/"', 1),
]
DB = os.environ["DATABASE_URL"]
survived = 0
for label, rel, old, new, n in [("no mutation (control)", "", "", "", 0)] + M:
    shutil.rmtree(copy, ignore_errors=True)
    copy.mkdir(parents=True)
    for d in ("nflpi", "tests"):
        shutil.copytree(work / d, copy / d, ignore=shutil.ignore_patterns("__pycache__"))
    if rel:
        text = (copy / rel).read_text()
        assert text.count(old) == n, (label, text.count(old))
        (copy / rel).write_text(text.replace(old, new))
    run = subprocess.run(
        ["uv", "run", "--project", str(project), "pytest", "-q", "-x", "-p", "no:cacheprovider", "tests/test_star_alerts.py"],
        cwd=copy, env={**os.environ, "PYTHONPATH": str(copy), "DATABASE_URL": DB}, capture_output=True, text=True,
    )
    tail = run.stdout.strip().splitlines()[-1][-110:] if run.stdout.strip() else run.stderr.strip()[-200:]
    killed = run.returncode != 0
    if rel and not killed:
        survived += 1
    print(f"{'control' if not rel else 'KILLED' if killed else 'SURVIVED'}: {label}: {tail}", flush=True)
print(f"{len(M)} mutations, {survived} survived")
sys.exit(1 if survived else 0)
