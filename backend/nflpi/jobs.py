"""Command line jobs and the background refresh loop.

python -m nflpi.jobs bootstrap      # first run: load data, train, predict, backfill
python -m nflpi.jobs ingest         # schedules, lines, teams, injuries, weather
python -m nflpi.jobs train          # fit on seasons before the current one
python -m nflpi.jobs predict        # refresh current + next week
python -m nflpi.jobs loop           # worker: refresh on a game-aware schedule
python -m nflpi.jobs vapid          # print a new Web Push key pair for .env
python -m nflpi.jobs backtest      # 2012-2025 walk-forward on nflverse games
"""

import argparse
import logging
import threading
import time
from datetime import UTC, datetime, timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from nflpi import live_worker, news_worker
from nflpi.analytics.backtest import run_backtest
from nflpi.analytics.metrics import EARLY_WEEK_END, UNCERTAINTY_GAP, UPSET_GAP
from nflpi.db import acquire_refresh_lock, release_refresh_lock, session_factory
from nflpi.ingestion import nflverse, service
from nflpi.models import AppSetting, Game, ModelVersion
from nflpi.notify import push
from nflpi.predictions import engine, sheet

log = logging.getLogger("nflpi.jobs")
TICK_SECONDS = 300
HEARTBEAT_STALE_SECONDS = 2 * TICK_SECONDS
HEARTBEAT_KEY = "worker_heartbeat"


def ingest(session, weather: bool = True) -> dict:
    out = {"schedules": service.ingest_schedules(session).status, "teams": service.ingest_teams(session).status}
    season, week = engine.current_week(session)
    run, changed = service.ingest_injuries(session, season)
    out["injuries"] = run.status
    if weather:
        out["weather"] = service.ingest_weather(session).status
    out["qb_alerts"] = push.alert_injuries(session, changed, season, week)
    return out


def train(session) -> ModelVersion:
    season, _ = engine.current_week(session)
    return engine.train(session, through_season=season - 1)


def predict(session) -> int:
    events = engine.refresh_predictions(session)
    season, week = engine.current_week(session)
    sheet.refresh_tiebreaks(session, season, week)
    return push.alert_prediction_changes(session, events)


def backtest() -> None:
    games = nflverse.parse_games(nflverse.fetch_csv("schedules/games.csv"), 2002)
    frame = (
        pd.DataFrame(games)
        .rename(columns={"_home_ml": "home_ml", "_away_ml": "away_ml"})
        .drop(columns=["_spread", "_total"])
        .sort_values(["kickoff_utc", "game_id"])
        .reset_index(drop=True)
    )
    report = run_backtest(frame, list(range(2012, 2026)))
    print("2012-2025 walk-forward, nflverse closing lines")
    print(f"Upset watch: stats picks market underdog OR stats-market gap >= {UPSET_GAP:.0%}")
    print(f"Uncertainty: week <= {EARLY_WEEK_END} raises two levels; gap >= {UNCERTAINTY_GAP:.0%} "
          "or a starting-QB change raises one level")
    for model in report["models"]:
        if model["model"] in ("market", "logistic", "blend"):
            print(f"{model['model']}: {model['accuracy']:.2%} ({model['n']} games)")
    for period, key in (("2012-2021 train", "signals_2012_2021"),
                        ("2022-2025 untouched check", "signals_2022_2025"),
                        ("2012-2025 overall", "signals")):
        signal = report[key]
        print(f"{period}: {signal['games']} games; upset watch {signal['upset_flag_rate']:.2%} "
              f"({signal['upset_flagged']}); flagged underdogs won "
              f"{signal['flagged_underdog_win_rate']:.2%} "
              f"({signal['flagged_underdog_wins']}/{signal['flagged_underdogs']}); "
              f"unflagged underdogs won {signal['unflagged_underdog_win_rate']:.2%} "
              f"({signal['unflagged_underdog_wins']}/{signal['unflagged_underdogs']})")
        for grade, row in signal["grades"].items():
            print(f"  {grade}: {row['share']:.2%} ({row['games']}); "
                  f"blend accuracy {row['accuracy']:.2%} ({row['correct']}/{row['games']})")
        for band, grades in signal["probability_bands"].items():
            cells = ", ".join(f"{grade} {row['accuracy']:.2%} ({row['games']})" for grade, row in grades.items())
            print(f"  pick probability {band}: {cells}")
        for row in report[key.replace("signals", "labels")]:
            rate = f"{row['hit_rate']:.2%}" if row["hit_rate"] is not None else "n/a"
            print(f"  {row['label']}: {row['share']:.2%} ({row['games']}); blend accuracy {rate}")


def next_interval(session, now: datetime) -> timedelta:
    """Refresh faster as kickoff gets closer."""
    nxt = session.scalar(select(Game.kickoff_utc).where(Game.kickoff_utc > now).order_by(Game.kickoff_utc).limit(1))
    if nxt is None:
        return timedelta(hours=12)
    until = nxt - now
    if until < timedelta(hours=6):
        return timedelta(minutes=20)
    if until < timedelta(days=2):
        return timedelta(hours=1)
    return timedelta(hours=4)


def tick(session: Session, now: datetime) -> None:
    """Send due reminders and record that the worker is alive."""
    row = session.get(AppSetting, HEARTBEAT_KEY)
    if row is None:
        session.add(AppSetting(key=HEARTBEAT_KEY, value={"at": now.isoformat()}))
    else:
        row.value = {"at": now.isoformat()}
    session.commit()
    try:
        log.info("pick sheet entries finalized: %s", sheet.finalize(session, now))
    except Exception:  # noqa: BLE001 - sheet failure must not hide a live worker
        log.exception("pick sheet finalization failed")
        session.rollback()
    try:
        log.info("kickoff reminders sent: %s", push.send_kickoff_reminders(session, now))
    except Exception:  # noqa: BLE001 - reminder failure must not hide a live worker
        log.exception("kickoff reminders failed")
        session.rollback()


def cycle(session) -> None:
    """One refresh: ingest, (re)train once per season, then predict and alert."""
    try:
        log.info("kickoff reminders sent: %s", push.send_kickoff_reminders(session, datetime.now(UTC)))
    except Exception:  # noqa: BLE001 - reminders must not stop the refresh
        log.exception("kickoff reminders failed")
        session.rollback()
    lock_conn = acquire_refresh_lock()
    if lock_conn is None:
        return
    try:
        log.info("ingest %s", ingest(session))
        season, _ = engine.current_week(session)
        mv = engine.active_model(session)
        if mv is None or mv.trained_through_season < season - 1:
            train(session)
            log.info("backfilled %s games", engine.backfill_season(session, season))
        log.info("prediction alerts sent: %s", predict(session))
    finally:
        release_refresh_lock(lock_conn)


def loop() -> None:
    next_refresh = 0.0
    next_tick = time.monotonic()
    refresh_thread: threading.Thread | None = None
    live_worker.start()
    news_worker.start()

    def refresh_cycle() -> None:
        nonlocal next_refresh
        try:
            with session_factory()() as session:
                cycle(session)
                wait = next_interval(session, datetime.now(UTC))
        except Exception:  # noqa: BLE001 - keep the worker alive; errors are logged and in ingestion_runs
            log.exception("refresh cycle failed")
            wait = timedelta(minutes=15)
        next_refresh = time.monotonic() + wait.total_seconds()
        log.info("next refresh in %s", wait)

    while True:
        with session_factory()() as session:
            try:
                tick(session, datetime.now(UTC))
            except Exception:  # noqa: BLE001 - keep the worker alive
                log.exception("worker tick failed")
                session.rollback()
        if time.monotonic() >= next_refresh and (refresh_thread is None or not refresh_thread.is_alive()):
            refresh_thread = threading.Thread(target=refresh_cycle, daemon=True)
            refresh_thread.start()
        next_tick += TICK_SECONDS
        time.sleep(max(0, next_tick - time.monotonic()))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["bootstrap", "ingest", "train", "predict", "backfill", "loop", "vapid", "backtest"]
    )
    parser.add_argument("--no-weather", action="store_true")
    args = parser.parse_args()
    if args.command == "loop":
        return loop()
    if args.command == "vapid":
        public, private = push.generate_vapid_keys()
        print(f"VAPID_PUBLIC_KEY={public}\nVAPID_PRIVATE_KEY={private}")
        return None
    if args.command == "backtest":
        return backtest()
    with session_factory()() as session:
        if args.command == "bootstrap":
            return cycle(session)
        if args.command == "ingest":
            print("ingest:", ingest(session, weather=not args.no_weather))
        if args.command == "train":
            mv = train(session)
            print("trained:", mv.name, {k: round(v["accuracy"], 4) for k, v in mv.metrics.items()})
        if args.command == "backfill":
            season, _ = engine.current_week(session)
            print("backfilled:", engine.backfill_season(session, season))
        if args.command == "predict":
            print("prediction alerts:", predict(session))


if __name__ == "__main__":
    main()
