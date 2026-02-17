#!/usr/bin/env python3
"""Main entry point for the Royal Caribbean price tracker."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from modules import database as db
from modules.notify import Notifier


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Royal Caribbean Price Tracker")
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run checks once and exit.",
    )
    parser.add_argument(
        "--module",
        choices=["cruise", "addons", "casino"],
        help="Run only one module.",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config YAML file.",
    )
    parser.add_argument(
        "--test-notify",
        action="store_true",
        help="Send a test notification and exit.",
    )
    parser.add_argument(
        "--settings",
        action="store_true",
        help="Open settings UI for editing config.yaml and exit.",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Run the web dashboard.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for web dashboard (used with --web).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port for web dashboard (used with --web).",
    )
    parser.add_argument(
        "--enable-web-scheduler",
        action="store_true",
        help="Enable scheduled checks inside web mode.",
    )
    return parser.parse_args()


def load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        sample_path = path.with_name("config_sample.yaml")
        raise FileNotFoundError(
            f"Config file not found: {path}. "
            f"Create it from {sample_path}."
        )

    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("pyyaml is required. Run: pip install -r requirements.txt") from exc

    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    required_keys = [
        "accounts",
        "cruise_watchlist",
        "addon_tracking",
        "casino_tracking",
        "schedule",
        "notifications",
        "settings",
    ]
    missing = [key for key in required_keys if key not in data]
    if missing:
        raise ValueError(f"Config missing required keys: {', '.join(missing)}")

    return data


def _build_notification_urls(config: dict) -> list[str]:
    urls: list[str] = []
    for item in config.get("notifications", []):
        if isinstance(item, dict) and item.get("url"):
            urls.append(item["url"])
        elif isinstance(item, str):
            urls.append(item)
    return urls


def _build_runtime_settings(config: dict) -> dict:
    runtime_settings = dict(config.get("settings", {}))
    runtime_settings["addon_categories"] = (
        config.get("addon_tracking", {}).get("categories") or []
    )
    runtime_settings["casino_notify_new"] = bool(
        config.get("casino_tracking", {}).get("notify_new_offers", True)
    )
    return runtime_settings


def run_all_checks(config: dict, notifier: Notifier, selected_module: str | None = None) -> None:
    from modules import addons, auth, casino, cruise_prices

    settings = _build_runtime_settings(config)
    addon_enabled = bool(config.get("addon_tracking", {}).get("enabled", True))
    casino_enabled = bool(config.get("casino_tracking", {}).get("enabled", True))

    print(f"\n=== RC Price Tracker Run: {datetime.now().isoformat(timespec='seconds')} ===")

    if selected_module in (None, "addons", "casino"):
        for account in config.get("accounts", []):
            username = account.get("username", "<unknown>")
            cruise_line = str(account.get("cruise_line", "royal")).lower()
            brand_code = "C" if cruise_line == "celebrity" else "R"

            try:
                access_token, account_id, session = auth.login(
                    username,
                    account.get("password", ""),
                    cruise_line=cruise_line,
                )
                db.log_run("auth", "success", f"Authenticated account {username}")
            except Exception as exc:
                db.log_run("auth", "error", f"Authentication failed for {username}: {exc}")
                print(f"[ERROR] Authentication failed for {username}: {exc}")
                continue

            auth_context = {
                "access_token": access_token,
                "account_id": account_id,
                "session": session,
                "brand_code": brand_code,
            }

            if selected_module in (None, "addons") and addon_enabled:
                try:
                    addons.check_all_addons(account, db, notifier, settings, auth_context)
                    db.log_run("addons", "success", f"Add-on check complete for {username}")
                except Exception as exc:
                    db.log_run("addons", "error", f"Add-on check failed for {username}: {exc}")
                    print(f"[ERROR] Add-on check failed for {username}: {exc}")

            if selected_module in (None, "casino") and casino_enabled:
                try:
                    casino.check_casino_offers(account, db, notifier, settings, auth_context)
                    db.log_run("casino", "success", f"Casino check complete for {username}")
                except Exception as exc:
                    db.log_run("casino", "error", f"Casino check failed for {username}: {exc}")
                    print(f"[ERROR] Casino check failed for {username}: {exc}")

    if selected_module in (None, "cruise"):
        for cruise_item in config.get("cruise_watchlist", []):
            try:
                cruise_prices.check_cruise_price(cruise_item, db, notifier, settings)
                db.log_run(
                    "cruise",
                    "success",
                    f"Cruise check complete for {cruise_item.get('label', 'watchlist entry')}",
                )
            except Exception as exc:
                db.log_run(
                    "cruise",
                    "error",
                    f"Cruise check failed for {cruise_item.get('label', 'watchlist entry')}: {exc}",
                )
                print(
                    f"[ERROR] Cruise check failed for "
                    f"{cruise_item.get('label', 'watchlist entry')}: {exc}"
                )


def start_scheduler(config: dict, notifier: Notifier, selected_module: str | None = None) -> None:
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError as exc:
        raise RuntimeError(
            "apscheduler is required to run scheduled checks. "
            "Run: pip install -r requirements.txt"
        ) from exc

    schedule_cfg = config.get("schedule", {})
    timezone_name = schedule_cfg.get("timezone", "America/New_York")
    run_times = schedule_cfg.get("times", ["07:00", "19:00"])

    timezone = ZoneInfo(timezone_name)
    scheduler = BlockingScheduler(timezone=timezone)

    for time_str in run_times:
        hour, minute = str(time_str).split(":", 1)
        scheduler.add_job(
            lambda: run_all_checks(config, notifier, selected_module=selected_module),
            CronTrigger(hour=int(hour), minute=int(minute), timezone=timezone),
            max_instances=1,
            coalesce=True,
        )

    print(f"[INFO] Scheduler started for {timezone_name} at times: {', '.join(map(str, run_times))}")
    scheduler.start()


def main() -> int:
    args = parse_args()

    if args.web:
        try:
            os.environ["RC_CONFIG_PATH"] = args.config
            os.environ["RC_ENABLE_SCHEDULER"] = "1" if args.enable_web_scheduler else "0"
            os.environ.setdefault("RC_RUN_ON_STARTUP", "1")

            from webapp import run_webapp

            run_webapp(
                config_path=args.config,
                host=args.host,
                port=args.port,
                enable_scheduler=args.enable_web_scheduler,
                run_on_startup=True,
            )
            return 0
        except Exception as exc:
            print(f"[ERROR] Unable to start web app: {exc}")
            return 1

    if args.settings:
        try:
            from settings_page import launch_settings_ui

            launch_settings_ui(args.config)
            return 0
        except Exception as exc:
            print(f"[ERROR] Unable to open settings UI: {exc}")
            return 1

    try:
        config = load_config(args.config)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1

    db_path = str(Path(args.config).with_name("price_tracker.db"))
    db.init_db(db_path)
    db.purge_old_records(int(config.get("settings", {}).get("price_history_days", 90)))

    notifier = Notifier(_build_notification_urls(config))

    if args.test_notify or bool(config.get("settings", {}).get("apprise_test", False)):
        notifier.test()
        print("[INFO] Test notification sent.")
        return 0

    if args.run_once:
        run_all_checks(config, notifier, selected_module=args.module)
        return 0

    try:
        start_scheduler(config, notifier, selected_module=args.module)
        return 0
    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")
        return 0
    except Exception as exc:
        print(f"[ERROR] Scheduler failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
