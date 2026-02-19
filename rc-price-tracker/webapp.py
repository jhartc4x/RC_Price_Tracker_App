#!/usr/bin/env python3
"""Deployable web dashboard for RC Price Tracker."""

from __future__ import annotations

import json
import argparse
import os
import sqlite3
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import yaml
import requests
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from modules import database as db
from modules.notify import Notifier
from tracker import _build_notification_urls, load_config, run_all_checks

DRINK_TYPES = [
    {"key": "beer_wine", "label": "Beer & Wine", "avg_price": 10, "icon": "🍺"},
    {"key": "mixed_cocktails", "label": "Mixed & Cocktails", "avg_price": 14, "icon": "🍹"},
    {"key": "non_alc", "label": "Coffee & Soda", "avg_price": 4, "icon": "☕"},
    {"key": "energy", "label": "Energy & Specialty", "avg_price": 6, "icon": "⚡"},
    {"key": "premium_spirit", "label": "Premium Spirits", "avg_price": 18, "icon": "🥃"},
]
PACKAGES = [
    {"name": "Classic", "description": "House beer, wine, and select spirits with moderate pour limits", "threshold": 4},
    {"name": "Deluxe", "description": "Adds premium cocktails, frozen drinks, and expanded mocktails", "threshold": 6},
    {"name": "Premium", "description": "Unlimited top-shelf cocktails, sparkling wine, and specialty pours", "threshold": 8},
    {"name": "Ultimate", "description": "Craft cocktails, champagne, and upscale energy shots for frequent sippers", "threshold": 10},
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _fallback_config() -> dict[str, Any]:
    return {
        "accounts": [
            {
                "username": "",
                "password": "",
                "cruise_line": "royal",
                "cna_number": "",
                "last_name": "",
            }
        ],
        "cruise_watchlist": [
            {"url": "", "paid_price": 0.0, "label": ""},
        ],
        "addon_tracking": {"enabled": True},
        "casino_tracking": {"enabled": True, "notify_new_offers": True},
        "schedule": {"times": ["07:00", "19:00"], "timezone": "America/New_York"},
        "notifications": [{"url": ""}],
        "settings": {
            "currency": "USD",
            "min_savings_threshold": 5.0,
            "price_history_days": 90,
            "apprise_test": False,
        },
    }


def _load_config_loose(config_path: Path) -> dict[str, Any]:
    data = _fallback_config()
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh) or {}
            if isinstance(loaded, dict):
                data.update(loaded)

    data.setdefault("accounts", [])
    data.setdefault("cruise_watchlist", [])
    data.setdefault("addon_tracking", {"enabled": True})
    data.setdefault("casino_tracking", {"enabled": True, "notify_new_offers": True})
    data.setdefault("schedule", {"times": ["07:00", "19:00"], "timezone": "America/New_York"})
    data.setdefault("notifications", [])
    data.setdefault("settings", {})
    return data


def _save_config(config_path: Path, payload: dict[str, Any]) -> None:
    if config_path.exists():
        backup_path = config_path.with_suffix(config_path.suffix + ".bak")
        shutil.copy2(config_path, backup_path)

    with config_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False, default_flow_style=False)


def _db_path_for_config(config_path: Path) -> Path:
    return config_path.with_name("price_tracker.db")


def _fetch_metrics(
    db_path: Path,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    metrics = {
        "price_records": 0,
        "alerts_sent": 0,
        "casino_offers": 0,
        "last_run": "N/A",
    }
    recent_prices: list[dict[str, Any]] = []
    recent_addons: list[dict[str, Any]] = []
    recent_offers: list[dict[str, Any]] = []
    account_summary: list[dict[str, Any]] = []

    if not db_path.exists():
        return metrics, recent_prices, recent_addons, recent_offers, account_summary

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        try:
            row = conn.execute(
                """
                SELECT
                  COUNT(*) AS total_records,
                  COALESCE(SUM(CASE WHEN notified = 1 THEN 1 ELSE 0 END), 0) AS alerts
                FROM price_history
                """
            ).fetchone()
            if row:
                metrics["price_records"] = int(row["total_records"] or 0)
                metrics["alerts_sent"] = int(row["alerts"] or 0)
        except sqlite3.OperationalError:
            pass

        try:
            row = conn.execute("SELECT COUNT(*) AS total_offers FROM casino_offers").fetchone()
            if row:
                metrics["casino_offers"] = int(row["total_offers"] or 0)
        except sqlite3.OperationalError:
            pass

        try:
            row = conn.execute("SELECT run_date FROM run_log ORDER BY id DESC LIMIT 1").fetchone()
            if row and row["run_date"]:
                metrics["last_run"] = row["run_date"]
        except sqlite3.OperationalError:
            pass

        try:
            price_rows = conn.execute(
                """
                SELECT check_date, record_type, product_name, current_price, paid_price,
                       currency, notified, COALESCE(account_username, label, '-') AS account_username
                FROM price_history
                ORDER BY id DESC
                LIMIT 12
                """
            ).fetchall()
            recent_prices = [dict(item) for item in price_rows]
        except sqlite3.OperationalError:
            recent_prices = []

        try:
            addon_rows = conn.execute(
                """
                SELECT check_date, COALESCE(account_username, label, '-') AS account_username,
                       product_name, passenger_name, current_price, paid_price, currency, notified
                FROM price_history
                WHERE record_type = 'addon'
                ORDER BY id DESC
                LIMIT 16
                """
            ).fetchall()
            recent_addons = [dict(item) for item in addon_rows]
        except sqlite3.OperationalError:
            recent_addons = []

        try:
            # Deduplicate by offer_code, keeping the most recent one
            offer_rows = conn.execute(
                """
                SELECT check_date, COALESCE(account_username, '-') AS account_username,
                       offer_code, offer_type, expiry_date, is_new, offer_details
                FROM (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY offer_code ORDER BY id DESC) as rn
                    FROM casino_offers
                )
                WHERE rn = 1
                ORDER BY expiry_date ASC, id DESC
                LIMIT 50
                """
            ).fetchall()

            recent_offers = []
            for row in offer_rows:
                item = dict(row)
                details = {}
                try:
                    raw = item.get("offer_details")
                    if raw:
                        details = json.loads(raw)
                except (TypeError, ValueError):
                    pass

                campaign = details.get("campaignOffer") or {}

                # Enrich item with parsed fields
                # Use specific offer type name if available
                offer_type_obj = campaign.get("offerType") or {}
                item["offer_type_name"] = offer_type_obj.get("name") or item.get("offer_type")

                item["offer_name"] = campaign.get("name") or item.get("offer_type")
                item["description"] = campaign.get("description")
                item["room_type"] = details.get("campaignType") or "Casino Offer"

                # API dates are often ISO; fallback to text scrape if needed
                api_res_date = campaign.get("reserveByDate")
                if api_res_date:
                    item["expiry_date"] = api_res_date[:10]

                formatted_sailings = []
                # Handle sailings list (could be strings or objects)
                raw_sailings = campaign.get("sailings") or []
                for s in raw_sailings:
                    if isinstance(s, dict):
                        # Extract what we can
                        formatted_sailings.append(f"{s.get('shipCode', '')} {s.get('sailDate', '')}")
                    else:
                        formatted_sailings.append(str(s))

                item["sailings"] = formatted_sailings
                item["sailing_count"] = len(formatted_sailings)
                item["promo_code"] = campaign.get("offerType", {}).get("code")

                recent_offers.append(item)
        except sqlite3.OperationalError:
            recent_offers = []

        try:
            addon_summary = conn.execute(
                """
                SELECT
                  COALESCE(account_username, label, 'Unassigned') AS account_username,
                  COUNT(*) AS addon_checks,
                  COALESCE(SUM(CASE WHEN notified = 1 THEN 1 ELSE 0 END), 0) AS addon_alerts,
                  MAX(check_date) AS last_activity
                FROM price_history
                WHERE record_type = 'addon'
                GROUP BY COALESCE(account_username, label, 'Unassigned')
                """
            ).fetchall()
        except sqlite3.OperationalError:
            addon_summary = []

        try:
            offer_summary = conn.execute(
                """
                SELECT
                  COALESCE(account_username, 'Unassigned') AS account_username,
                  COUNT(*) AS offer_count,
                  COALESCE(SUM(CASE WHEN is_new = 1 THEN 1 ELSE 0 END), 0) AS new_offers,
                  MAX(check_date) AS last_offer_activity
                FROM casino_offers
                GROUP BY COALESCE(account_username, 'Unassigned')
                """
            ).fetchall()
        except sqlite3.OperationalError:
            offer_summary = []

        summary_map: dict[str, dict[str, Any]] = {}
        for row in addon_summary:
            account = row["account_username"]
            summary_map[account] = {
                "account_username": account,
                "addon_checks": int(row["addon_checks"] or 0),
                "addon_alerts": int(row["addon_alerts"] or 0),
                "offer_count": 0,
                "new_offers": 0,
                "last_activity": row["last_activity"],
            }

        for row in offer_summary:
            account = row["account_username"]
            current = summary_map.setdefault(
                account,
                {
                    "account_username": account,
                    "addon_checks": 0,
                    "addon_alerts": 0,
                    "offer_count": 0,
                    "new_offers": 0,
                    "last_activity": row["last_offer_activity"],
                },
            )
            current["offer_count"] = int(row["offer_count"] or 0)
            current["new_offers"] = int(row["new_offers"] or 0)
            if not current.get("last_activity"):
                current["last_activity"] = row["last_offer_activity"]

        account_summary = sorted(summary_map.values(), key=lambda item: item["account_username"])

    return metrics, recent_prices, recent_addons, recent_offers, account_summary


def _fetch_run_logs(db_path: Path, limit: int = 100) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT run_date, module, status, message
                FROM run_log
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(item) for item in rows]
        except sqlite3.OperationalError:
            return []


def _parse_watchlist_entry(entry: dict[str, Any]) -> dict[str, Any]:
    url = str(entry.get("url") or "")
    label = str(entry.get("label") or "Watchlist Cruise")
    try:
        paid_price = float(entry.get("paid_price") or 0.0)
    except (TypeError, ValueError):
        paid_price = 0.0

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    sail_date = (query.get("sailDate") or [None])[0]
    ship_code = (query.get("shipCode") or [None])[0]

    return {
        "label": label,
        "url": url,
        "paid_price": paid_price,
        "sail_date": sail_date,
        "ship_code": ship_code,
    }


def _fetch_cruise_views(
    db_path: Path,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    watchlist = [
        _parse_watchlist_entry(item)
        for item in (config.get("cruise_watchlist") or [])
        if isinstance(item, dict)
    ]
    if not db_path.exists():
        return [], watchlist

    booked_cards: list[dict[str, Any]] = []
    watchlist_cards = [dict(item) for item in watchlist]

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        try:
            booked_rows = conn.execute(
                """
                SELECT bc.*
                FROM booked_cruises bc
                JOIN (
                    SELECT COALESCE(account_username, '-') AS account_key,
                           reservation_id,
                           MAX(id) AS max_id
                    FROM booked_cruises
                    GROUP BY COALESCE(account_username, '-'), reservation_id
                ) latest ON bc.id = latest.max_id
                ORDER BY bc.sail_date, bc.ship_code
                """
            ).fetchall()
        except sqlite3.OperationalError:
            booked_rows = []

        try:
            addon_rows = conn.execute(
                """
                SELECT ph.*
                FROM price_history ph
                JOIN (
                    SELECT COALESCE(account_username, '-') AS account_key,
                           reservation_id,
                           product_code,
                           COALESCE(passenger_name, '-') AS passenger_key,
                           MAX(id) AS max_id
                    FROM price_history
                    WHERE record_type = 'addon'
                    GROUP BY COALESCE(account_username, '-'), reservation_id, product_code, COALESCE(passenger_name, '-')
                ) latest ON ph.id = latest.max_id
                WHERE ph.record_type = 'addon'
                ORDER BY ph.sail_date, ph.ship_code, ph.product_name
                """
            ).fetchall()
        except sqlite3.OperationalError:
            addon_rows = []

        try:
            cruise_rows = conn.execute(
                """
                SELECT id, check_date, label, ship_code, sail_date, current_price, paid_price, currency
                FROM price_history
                WHERE record_type = 'cruise'
                ORDER BY id DESC
                """
            ).fetchall()
        except sqlite3.OperationalError:
            cruise_rows = []

    addons_by_reservation: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in addon_rows:
        item = dict(row)
        account = str(item.get("account_username") or item.get("label") or "-")
        reservation = str(item.get("reservation_id") or "")
        key = (account, reservation)
        addons_by_reservation.setdefault(key, []).append(item)

    cruise_price_by_key: dict[tuple[str | None, str | None], dict[str, Any]] = {}
    for row in cruise_rows:
        item = dict(row)
        key = (item.get("ship_code"), item.get("sail_date"))
        if key not in cruise_price_by_key:
            cruise_price_by_key[key] = item

    booked_by_ship_sail: dict[tuple[str | None, str | None], list[dict[str, Any]]] = {}
    for row in booked_rows:
        item = dict(row)
        account = str(item.get("account_username") or "-")
        reservation = str(item.get("reservation_id") or "")
        key = (account, reservation)
        addons = addons_by_reservation.get(key, [])
        addon_alerts = sum(1 for addon in addons if int(addon.get("notified") or 0) == 1)

        card = {
            "account_username": account,
            "cruise_line": item.get("cruise_line") or "royal",
            "reservation_id": reservation,
            "sail_date": item.get("sail_date"),
            "ship_code": item.get("ship_code"),
            "ship_name": item.get("ship_name") or item.get("ship_code"),
            "stateroom_number": item.get("stateroom_number"),
            "guest_count": item.get("guest_count"),
            "last_seen": item.get("check_date"),
            "addons": addons,
            "addon_count": len(addons),
            "addon_alert_count": addon_alerts,
        }
        booked_cards.append(card)
        ship_sail_key = (item.get("ship_code"), item.get("sail_date"))
        booked_by_ship_sail.setdefault(ship_sail_key, []).append(card)

    for card in watchlist_cards:
        ship_sail_key = (card.get("ship_code"), card.get("sail_date"))
        matched_bookings = booked_by_ship_sail.get(ship_sail_key, [])
        matched_addons: list[dict[str, Any]] = []
        for booking in matched_bookings:
            matched_addons.extend(booking["addons"])

        cruise_price = cruise_price_by_key.get(ship_sail_key)
        card["matched_bookings"] = matched_bookings
        card["matched_addons"] = matched_addons
        card["matched_addon_count"] = len(matched_addons)
        card["matched_booking_count"] = len(matched_bookings)
        card["latest_cruise_price"] = cruise_price.get("current_price") if cruise_price else None
        card["latest_cruise_currency"] = cruise_price.get("currency") if cruise_price else None
        card["latest_checked_at"] = cruise_price.get("check_date") if cruise_price else None

    return booked_cards, watchlist_cards


def create_app(
    config_path: str = "config.yaml",
    enable_scheduler: bool = False,
    run_on_startup: bool = True,
) -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("RC_WEBAPP_SECRET", "rc-price-tracker-local-secret")
    _register_drink_tool_routes(app)

    config_file = Path(config_path).resolve()
    db_path = _db_path_for_config(config_file)
    db.init_db(str(db_path))

    run_state: dict[str, Any] = {
        "status": "idle",
        "module": "all",
        "started_at": None,
        "ended_at": None,
        "message": "Waiting for first run.",
    }
    run_lock = threading.Lock()
    state_lock = threading.Lock()

    def get_run_state() -> dict[str, Any]:
        with state_lock:
            return dict(run_state)

    def set_run_state(**updates: Any) -> None:
        with state_lock:
            run_state.update(updates)

    def execute_run(selected_module: str | None) -> None:
        if not run_lock.acquire(blocking=False):
            set_run_state(
                status="busy",
                message="A run is already in progress.",
                ended_at=_utc_now_iso(),
            )
            return

        module_name = selected_module or "all"
        set_run_state(
            status="running",
            module=module_name,
            started_at=_utc_now_iso(),
            ended_at=None,
            message="Checks are running.",
        )

        try:
            config = load_config(str(config_file))
            db.init_db(str(db_path))
            days = int(config.get("settings", {}).get("price_history_days", 90))
            db.purge_old_records(days)
            notifier = Notifier(_build_notification_urls(config))
            run_all_checks(config, notifier, selected_module=selected_module)

            set_run_state(
                status="success",
                ended_at=_utc_now_iso(),
                message="Run completed successfully.",
            )
        except Exception as exc:
            set_run_state(
                status="error",
                ended_at=_utc_now_iso(),
                message=str(exc),
            )
        finally:
            run_lock.release()

    def queue_run(selected_module: str | None) -> tuple[bool, str]:
        if run_lock.locked():
            return False, "A run is already in progress."
        thread = threading.Thread(target=execute_run, args=(selected_module,), daemon=True)
        thread.start()
        return True, "Run queued."

    def start_background_scheduler() -> tuple[bool, str]:
        if not enable_scheduler:
            return False, "Scheduler disabled."

        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
        except ImportError:
            return False, "apscheduler unavailable. Install requirements.txt."

        config = _load_config_loose(config_file)
        schedule = config.get("schedule", {})
        timezone_name = schedule.get("timezone", "America/New_York")
        run_times = schedule.get("times", ["07:00", "19:00"])

        scheduler = BackgroundScheduler(timezone=ZoneInfo(timezone_name))
        for time_str in run_times:
            hour, minute = str(time_str).split(":", 1)
            scheduler.add_job(
                queue_run,
                args=[None],
                trigger=CronTrigger(hour=int(hour), minute=int(minute), timezone=ZoneInfo(timezone_name)),
                max_instances=1,
                coalesce=True,
            )
        scheduler.start()
        app.extensions["web_scheduler"] = scheduler
        return True, f"Scheduler active for {timezone_name} at {', '.join(run_times)}"

    @app.get("/")
    def dashboard() -> str:
        config = _load_config_loose(config_file)
        booked_cruises, watchlist_cruises = _fetch_cruise_views(db_path, config)
        metrics, recent_prices, recent_addons, recent_offers, account_summary = _fetch_metrics(db_path)
        return render_template(
            "dashboard.html",
            config=config,
            metrics=metrics,
            run_state=get_run_state(),
            recent_prices=recent_prices,
            recent_addons=recent_addons,
            recent_offers=recent_offers,
            account_summary=account_summary,
            booked_cruises=booked_cruises,
            watchlist_cruises=watchlist_cruises,
            config_path=str(config_file),
            scheduler_enabled=bool(app.extensions.get("web_scheduler")),
        )

    @app.post("/run")
    def run_now() -> Any:
        module = (request.form.get("module") or "").strip().lower()
        if module in {"", "all"}:
            selected_module = None
        elif module in {"cruise", "addons", "casino"}:
            selected_module = module
        else:
            flash("Invalid module selected.", "error")
            return redirect(url_for("dashboard"))

        ok, message = queue_run(selected_module)
        flash(message, "success" if ok else "warning")
        return redirect(url_for("dashboard"))

    @app.get("/api/run-status")
    def run_status() -> Any:
        return jsonify(get_run_state())

    @app.get("/api/run-log")
    def run_log() -> Any:
        return jsonify({"logs": _fetch_run_logs(db_path, limit=200)})

    @app.get("/health")
    def health() -> Any:
        return jsonify(
            {
                "status": "ok",
                "scheduler": bool(app.extensions.get("web_scheduler")),
                "config_path": str(config_file),
                "db_path": str(db_path),
            }
        )

    @app.get("/settings")
    def settings_page() -> str:
        config = _load_config_loose(config_file)
        return render_template(
            "settings.html",
            config=config,
            config_path=str(config_file),
            scheduler_enabled=bool(app.extensions.get("web_scheduler")),
        )

    @app.post("/settings")
    def save_settings() -> Any:
        try:
            account_usernames = request.form.getlist("account_username[]")
            account_passwords = request.form.getlist("account_password[]")
            account_lines = request.form.getlist("account_cruise_line[]")
            account_cna = request.form.getlist("account_cna_number[]")
            account_last_name = request.form.getlist("account_last_name[]")

            accounts: list[dict[str, Any]] = []
            count = max(
                len(account_usernames),
                len(account_passwords),
                len(account_lines),
                len(account_cna),
                len(account_last_name),
            )
            for i in range(count):
                username = (account_usernames[i] if i < len(account_usernames) else "").strip()
                password = (account_passwords[i] if i < len(account_passwords) else "").strip()
                cruise_line = (account_lines[i] if i < len(account_lines) else "royal").strip().lower()
                cna_number = (account_cna[i] if i < len(account_cna) else "").strip()
                last_name = (account_last_name[i] if i < len(account_last_name) else "").strip()

                if not any([username, password, cna_number, last_name]):
                    continue
                if cruise_line not in {"royal", "celebrity"}:
                    cruise_line = "royal"

                accounts.append(
                    {
                        "username": username,
                        "password": password,
                        "cruise_line": cruise_line,
                        "cna_number": cna_number,
                        "last_name": last_name,
                    }
                )

            if not accounts:
                raise ValueError("At least one account is required.")

            cruise_urls = request.form.getlist("cruise_url[]")
            cruise_prices = request.form.getlist("cruise_paid_price[]")
            cruise_labels = request.form.getlist("cruise_label[]")
            cruise_watchlist: list[dict[str, Any]] = []
            cruise_count = max(len(cruise_urls), len(cruise_prices), len(cruise_labels))
            for i in range(cruise_count):
                url = (cruise_urls[i] if i < len(cruise_urls) else "").strip()
                paid_price_text = (cruise_prices[i] if i < len(cruise_prices) else "0").strip() or "0"
                label = (cruise_labels[i] if i < len(cruise_labels) else "").strip()

                if not url:
                    continue
                paid_price = float(paid_price_text)
                cruise_watchlist.append(
                    {"url": url, "paid_price": paid_price, "label": label}
                )

            notification_urls = request.form.getlist("notification_url[]")
            notifications = [{"url": item.strip()} for item in notification_urls if item.strip()]

            schedule_times_raw = (request.form.get("schedule_times") or "07:00,19:00").strip()
            schedule_times = [item.strip() for item in schedule_times_raw.split(",") if item.strip()]
            if not schedule_times:
                raise ValueError("At least one schedule time is required.")

            for time_item in schedule_times:
                if len(time_item.split(":")) != 2:
                    raise ValueError(f"Invalid time format: {time_item}")

            addon_categories_raw = (request.form.get("addon_categories") or "").strip()
            addon_categories = [item.strip() for item in addon_categories_raw.split(",") if item.strip()]

            payload = {
                "accounts": accounts,
                "cruise_watchlist": cruise_watchlist,
                "addon_tracking": {
                    "enabled": request.form.get("addon_enabled") == "on",
                },
                "casino_tracking": {
                    "enabled": request.form.get("casino_enabled") == "on",
                    "notify_new_offers": request.form.get("casino_notify_new_offers") == "on",
                },
                "schedule": {
                    "times": schedule_times,
                    "timezone": (request.form.get("schedule_timezone") or "America/New_York").strip(),
                },
                "notifications": notifications,
                "settings": {
                    "currency": (request.form.get("currency") or "USD").strip(),
                    "min_savings_threshold": float(
                        (request.form.get("min_savings_threshold") or "5").strip()
                    ),
                    "price_history_days": int(
                        (request.form.get("price_history_days") or "90").strip()
                    ),
                    "apprise_test": request.form.get("apprise_test") == "on",
                },
            }

            if addon_categories:
                payload["addon_tracking"]["categories"] = addon_categories

            _save_config(config_file, payload)
            flash("Settings saved to config.yaml.", "success")
        except Exception as exc:
            flash(f"Unable to save settings: {exc}", "error")

        return redirect(url_for("settings_page"))

    @app.get("/addons")
    def addons_page() -> str:
        return render_template(
            "addons.html",
            config_path=str(config_file),
            scheduler_enabled=bool(app.extensions.get("web_scheduler")),
        )

    @app.get("/cruises")
    def cruises_page() -> str:
        return render_template("cruises.html")

    @app.get("/api/ships")
    def api_ships() -> Any:
        from modules.addons import get_ship_dictionary

        ships_dict = get_ship_dictionary()
        ships = [{"ship_code": code, "ship_name": name} for code, name in sorted(ships_dict.items(), key=lambda x: x[1])]
        return jsonify({"ships": ships})

    @app.get("/api/sailings")
    def api_sailings() -> Any:
        ship_code = request.args.get("ship_code", "").strip()
        if not ship_code:
            return jsonify({"sailings": []})

        url = "https://www.royalcaribbean.com/cruises/graph"
        query = """query cruiseSearch_Cruises($filters: String, $qualifiers: String, $sort: CruiseSearchSort, $pagination: CruiseSearchPagination) {
  cruiseSearch(
    filters: $filters
    qualifiers: $qualifiers
    sort: $sort
    pagination: $pagination
  ) {
    results {
      cruises {
        sailings {
          sailDate
        }
      }
    }
  }
}"""

        headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "brand": "R",
            "country": "USA",
            "language": "en",
            "currency": "USD",
            "office": "MIA",
            "countryalpha2code": "US",
            "apollographql-client-name": "rci-NextGen-Cruise-Search",
            "skip_authentication": "true",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        }

        payload = {
            "operationName": "cruiseSearch_Cruises",
            "variables": {
                "filters": f"ship:{ship_code}",
                "sort": {"by": "RECOMMENDED"},
                "pagination": {"count": 100, "skip": 0},
            },
            "query": query,
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("data", {}).get("cruiseSearch", {}).get("results", {})
                cruises = results.get("cruises") or []

                all_dates = set()
                for cruise in cruises:
                    for sailing in cruise.get("sailings", []):
                        d = sailing.get("sailDate")
                        if d:
                            all_dates.add(str(d))

                # Sort dates
                sorted_dates = sorted(list(all_dates))
                return jsonify({"sailings": sorted_dates})

            return jsonify({"sailings": [], "error": f"API error: {resp.status_code}"})

        except Exception as exc:
            return jsonify({"sailings": [], "error": str(exc)})

    @app.get("/api/addons")
    def api_addons() -> Any:
        ship_code = request.args.get("ship_code", "").strip()
        sail_date = request.args.get("sail_date", "").strip()

        if not ship_code or not sail_date:
            return jsonify({"purchased": [], "available": [], "source": "none"})

        # ── 1. Fetch live add-on data via unauthenticated RC APIs ──
        live_available: list[dict[str, Any]] = []
        live_error: str | None = None
        diagnostics: dict[str, Any] = {"categories": {}}

        WEB_APPKEY = "hyNNqIPHHzaLzVpcICPdAdbFV8yvTsAm"
        GRAPHQL_URL = "https://aws-prd.api.rccl.com/en/royal/web/graphql"
        CATALOG_UNAUTH_BASE = (
            "https://aws-prd.api.rccl.com/en/royal/web/commerce-api/catalog-unauth/v2"
        )

        # Category slugs used by the cruise planner GraphQL API
        UNAUTH_CATEGORIES = {
            "beverage": "Beverage",
            "dining": "Dining",
            "internet": "Internet",
            "shorex": "Shore Excursions",
            "cococay": "CocoCay",
            "onboardactivities": "Onboard Activities",
        }

        # Category slugs used by the catalog-unauth REST API
        UNAUTH_REST_CATEGORIES = {
            "beverage": "pt_beverage",
            "dining": "pt_dining",
            "internet": "pt_internet",
            "shorex": "pt_shoreX",
            "cococay": "pt_cococay",
            "onboardactivities": "pt_onboardActivities",
        }

        # Format sail date as YYYY-MM-DD for GraphQL
        try:
            if len(sail_date) == 8:
                gql_sail_date = f"{sail_date[:4]}-{sail_date[4:6]}-{sail_date[6:8]}"
            else:
                gql_sail_date = sail_date
        except Exception:
            gql_sail_date = sail_date

        cfg = _load_config_loose(config_file)
        currency = cfg.get("settings", {}).get("currency", "USD")

        api_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "AppKey": WEB_APPKEY,
        }

        gql_query = """query WebProductsByCategory($category: String!, $shipCode: ShipCodeScalar!, $sailDate: LocalDateScalar!, $reservationId: String, $pageSize: Long, $currentPage: Long, $sorting: Sorting, $filter: FilterInput, $currencyCode: String!) {
  products(
    category: $category
    guestTypes: [ADULT]
    shipCode: $shipCode
    sailDate: $sailDate
    reservationId: $reservationId
    pageSize: $pageSize
    currentPage: $currentPage
    sorting: $sorting
    filter: $filter
    currencyIso: $currencyCode
  ) {
    ... on CommerceProductResultSuccess {
      commerceProducts {
        id
        baseId
        title
        price {
          currency
          promotionalPrice
          shipboardPrice
          formattedPromotionalPrice
          formattedBasePrice
        }
      }
    }
  }
}"""

        PAGE_SIZE = 24

        try:
            session = requests.Session()
            diagnostics["auth"] = "unauth (no login needed)"

            for cat_slug, cat_name in UNAUTH_CATEGORIES.items():
                try:
                    all_commerce_products: list[dict] = []
                    current_page = 0

                    # Paginate through all pages for this category
                    while True:
                        gql_payload = {
                            "operationName": "WebProductsByCategory",
                            "variables": {
                                "category": cat_slug,
                                "shipCode": ship_code,
                                "sailDate": gql_sail_date,
                                "reservationId": "0",
                                "pageSize": PAGE_SIZE,
                                "currentPage": current_page,
                                "sorting": {
                                    "sortKey": "RANK",
                                    "sortKeyOrder": "ASCENDING",
                                },
                                "filter": {"includeVariantProducts": False},
                                "currencyCode": currency,
                            },
                            "query": gql_query,
                        }

                        resp = session.post(
                            GRAPHQL_URL,
                            headers=api_headers,
                            json=gql_payload,
                            timeout=45,
                        )

                        if resp.status_code != 200:
                            diagnostics["categories"][cat_name] = {
                                "status": resp.status_code,
                                "method": "GraphQL",
                                "error": resp.text[:150],
                            }
                            break

                        gql_data = resp.json()
                        if "errors" in gql_data:
                            diagnostics["categories"][cat_name] = {
                                "status": 200,
                                "method": "GraphQL",
                                "error": str(gql_data["errors"][0].get("message", ""))[:150],
                            }
                            break

                        products_result = (
                            gql_data.get("data", {}).get("products") or {}
                        )
                        page_products = products_result.get("commerceProducts", [])
                        all_commerce_products.extend(page_products)

                        # If we got fewer than PAGE_SIZE, we've reached the last page
                        if len(page_products) < PAGE_SIZE:
                            break
                        current_page += 1

                    diagnostics["categories"][cat_name] = {
                        "status": 200,
                        "method": "GraphQL",
                        "products": len(all_commerce_products),
                        "pages": current_page + 1,
                    }

                    # For each product, try to get the price from catalog-unauth
                    rest_cat = UNAUTH_REST_CATEGORIES.get(cat_slug, f"pt_{cat_slug}")

                    for prod in all_commerce_products:
                        prod_id = str(prod.get("id") or "")
                        base_id = str(prod.get("baseId") or "")
                        title = prod.get("title") or "Unknown"

                        if not prod_id:
                            continue

                        # Check if GraphQL already returned pricing
                        price_list = prod.get("price", [])
                        gql_price: float | None = None
                        gql_base_price: float | None = None
                        if isinstance(price_list, list) and price_list:
                            p0 = price_list[0]
                            gql_price = p0.get("promotionalPrice")
                            gql_base_price = p0.get("shipboardPrice")
                        elif isinstance(price_list, dict):
                            gql_price = price_list.get("promotionalPrice")
                            gql_base_price = price_list.get("shipboardPrice")

                        # If GraphQL didn't provide price, fetch from catalog-unauth
                        current_price = gql_price
                        base_price = gql_base_price

                        if current_price is None:
                            try:
                                detail_url = (
                                    f"{CATALOG_UNAUTH_BASE}/{ship_code}"
                                    f"/categories/{rest_cat}/products/{prod_id}"
                                )
                                detail_params = {
                                    "reservationId": "0",
                                    "startDate": sail_date,
                                    "currencyIso": currency,
                                }
                                detail_resp = session.get(
                                    detail_url,
                                    headers=api_headers,
                                    params=detail_params,
                                    timeout=30,
                                )
                                if detail_resp.status_code == 200:
                                    detail_data = detail_resp.json()
                                    payload = detail_data.get("payload", {})
                                    sfp = payload.get("startingFromPrice", {})
                                    if isinstance(sfp, dict):
                                        current_price = sfp.get("adultPromotionalPrice")
                                        base_price = sfp.get("adultShipboardPrice")
                            except Exception:
                                pass  # Price lookup failed, product still listed

                        live_available.append({
                            "product_code": base_id or prod_id,
                            "product_name": title.strip(),
                            "category": cat_name,
                            "current_price": current_price,
                            "base_price": base_price,
                            "currency": currency,
                            "source": "live",
                        })

                except requests.exceptions.RequestException as exc:
                    diagnostics["categories"][cat_name] = {"error": str(exc)}
                    live_error = f"Network error for {cat_name}: {exc}"
                except Exception as exc:
                    diagnostics["categories"][cat_name] = {"error": str(exc)}

        except Exception as e:
            live_error = f"Error fetching add-ons: {e}"
            diagnostics["error"] = str(e)

        # ── 2. Pull any historical/purchased data from DB ──
        purchased: list[dict[str, Any]] = []
        db_available: list[dict[str, Any]] = []

        if db_path.exists():
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                try:
                    rows = conn.execute(
                        """
                        SELECT ph.check_date, ph.account_username, ph.reservation_id,
                               ph.product_code, ph.product_name, ph.passenger_name,
                               ph.paid_price, ph.current_price, ph.currency, ph.notified
                        FROM price_history ph
                        JOIN (
                            SELECT product_code,
                                   COALESCE(passenger_name, '-') AS pk,
                                   COALESCE(reservation_id, '-') AS rk,
                                   MAX(id) AS max_id
                            FROM price_history
                            WHERE record_type = 'addon'
                              AND ship_code = ?
                              AND sail_date = ?
                            GROUP BY product_code, COALESCE(passenger_name, '-'), COALESCE(reservation_id, '-')
                        ) latest ON ph.id = latest.max_id
                        ORDER BY ph.product_name
                        """,
                        (ship_code, sail_date),
                    ).fetchall()
                    purchased = [dict(r) for r in rows]

                    # Also get history for available items
                    rows_avail = conn.execute(
                        """
                        SELECT ph.check_date, ph.product_code, ph.product_name,
                               ph.current_price, ph.currency
                        FROM price_history ph
                        JOIN (
                            SELECT product_code, MAX(id) AS max_id
                            FROM price_history
                            WHERE record_type = 'addon'
                              AND ship_code = ?
                              AND sail_date = ?
                              AND paid_price = 0
                            GROUP BY product_code
                        ) latest ON ph.id = latest.max_id
                        """,
                        (ship_code, sail_date),
                    ).fetchall()
                    db_available = [dict(r) for r in rows_avail]

                except sqlite3.OperationalError:
                    # Table might not exist yet
                    pass

        # ── 3. Merge Live + DB ──
        # If we have live data, use it as primary source for "Available"
        final_available = []
        if live_available:
            # Maybe enrich with history (e.g. "lowest price was X")
            final_available = live_available
            source = "live"
        else:
            final_available = db_available
            source = "db" if db_available else "none"

        # Calculate savings for purchased
        for p in purchased:
            # Try to find current live price for this item
            current = None
            if live_available:
                # fast lookup
                match = next((x for x in live_available if x["product_code"] == p["product_code"]), None)
                if match:
                    current = match["current_price"]
            
            # If no live price, use last DB price
            if current is None:
                current = p["current_price"]

            paid = p["paid_price"]
            if current is not None and paid is not None:
                p["current_price"] = current
                p["savings"] = paid - current
            else:
                p["savings"] = 0

        return jsonify({
            "purchased": purchased,
            "available": final_available,
            "source": source,
            "error": live_error,
            "diagnostics": diagnostics
        })

    @app.get("/api/cruises")
    def api_cruises() -> Any:
        from modules.addons import get_ship_dictionary
        
        ship_code = request.args.get("ship_code", "").strip()
        port_code = request.args.get("port_code", "").strip()
        date_range = request.args.get("date_range", "").strip() # YYYY-MM
        guests = request.args.get("guests", "2")
        max_price_str = request.args.get("max_price", "").strip()
        
        # Max Price
        max_price = None
        if max_price_str:
            try:
                max_price = float(max_price_str)
            except:
                pass

        # Resolve Ship Dictionary for lookups
        ships = get_ship_dictionary()
        
        # Build Filters
        filters_parts = []
        if ship_code:
            filters_parts.append(f"ship:{ship_code}")
        
        if port_code:
            filters_parts.append(f"departurePort:{port_code}")
            
        if date_range:
             filters_parts.append(f"date:{date_range}")

        try:
            g_int = int(guests)
            filters_parts.append(f"adults:{g_int}")
        except:
            filters_parts.append("adults:2")
            
        filters_str = "|".join(filters_parts)

        url = "https://www.royalcaribbean.com/cruises/graph"
            
        # Updated Query with stateroomClassPricing
        query = """query cruiseSearch_Cruises($filters: String, $sort: CruiseSearchSort, $pagination: CruiseSearchPagination) {
    cruiseSearch(
        filters: $filters
        sort: $sort
        pagination: $pagination
    ) {
        results {
        cruises {
            id
            sailings {
                sailDate
                itinerary {
                    name
                }
                stateroomClassPricing {
                    price {
                        value
                    }
                    stateroomClass {
                        name
                    }
                }
            }
        }
        }
    }
    }"""

        payload = {
            "operationName": "cruiseSearch_Cruises",
            "variables": {
                "filters": filters_str,
                "sort": {"by": "RECOMMENDED"},
                "pagination": {"count": 50, "skip": 0}, # Increased count
            },
            "query": query
        }

        # Headers REQUIRED to avoid timeout/403
        headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "brand": "R",
            "country": "USA",
            "language": "en",
            "currency": "USD",
            "office": "MIA",
            "countryalpha2code": "US",
            "apollographql-client-name": "rci-NextGen-Cruise-Search",
            "skip_authentication": "true",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        }

        # print(f"DEBUG: Fetching cruises with filters: {filters_str}")
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            
            if response.status_code != 200:
                print(f"API Error: {response.text}")
                return jsonify({"cruises": [], "error": f"API Error {response.status_code}"})

            data = response.json()
            if "errors" in data:
                print(f"GraphQL Errors: {data['errors']}")
                # Continue if partial data? No, errors usually mean no data.

            results = data.get("data", {}).get("cruiseSearch", {}).get("results", {})
            raw_cruises = results.get("cruises") or []

            # Process Results
            processed_cruises = []
            import re
            
            for c in raw_cruises:
                cid = c.get("id", "")
                
                # Derive Ship Name from ID (e.g. IC07MIA -> IC)
                derived_ship_code = cid[:2]
                current_ship_name = ships.get(derived_ship_code, derived_ship_code)
                
                # Derive Nights
                nights_match = re.search(r'^[A-Z]{2}(\d+)', cid)
                nights = int(nights_match.group(1)) if nights_match else 0

                for s in c.get("sailings", []):
                    prices = {}
                    pricing_list = s.get("stateroomClassPricing", []) or []
                    
                    lowest_val = 999999
                    
                    for p_obj in pricing_list:
                        if not p_obj or not p_obj.get("price"): continue
                        
                        val = p_obj.get("price", {}).get("value")
                        cat_name = p_obj.get("stateroomClass", {}).get("name", "").upper()
                        
                        if val is not None:
                            if val < lowest_val: lowest_val = val
                            
                            if "INTERIOR" in cat_name: prices["INTERIOR"] = val
                            elif "BALCONY" in cat_name: prices["BALCONY"] = val
                            elif "OUTSIDE" in cat_name or "OCEAN" in cat_name: prices["OCEANVIEW"] = val
                            elif "SUITE" in cat_name: prices["SUITE"] = val
                    
                    # Max Price Filter
                    if max_price and lowest_val > max_price:
                        continue

                    item = {
                        "ship_name": current_ship_name,
                        "ship_code": derived_ship_code,
                        "title": s.get("itinerary", {}).get("name", "Cruise"),
                        "sail_date": s.get("sailDate"),
                        "nights": nights,
                        "prices": prices
                    }
                    processed_cruises.append(item)

            # Sort by date
            processed_cruises.sort(key=lambda x: x['sail_date'])
            
            return jsonify({"cruises": processed_cruises})

        except Exception as exc:
            print(f"Exception fetching cruises: {exc}")
            return jsonify({"cruises": [], "error": str(exc)})

    started, startup_message = start_background_scheduler()
    if started:
        set_run_state(message=startup_message)

    if run_on_startup:
        queued, queued_message = queue_run(None)
        app.extensions["startup_run"] = {
            "enabled": True,
            "queued": queued,
            "message": queued_message,
        }
    else:
        app.extensions["startup_run"] = {
            "enabled": False,
            "queued": False,
            "message": "Startup run disabled.",
        }

    return app


def _register_drink_tool_routes(app: Flask) -> None:
    @app.route("/drink-tool", methods=["GET", "POST"])
    def drink_tool_page():
        counts = {entry["key"]: 0 for entry in DRINK_TYPES}
        if request.method == "POST":
            for entry in DRINK_TYPES:
                raw = request.form.get(entry["key"], "0")
                try:
                    counts[entry["key"]] = max(0, int(raw))
                except ValueError:
                    counts[entry["key"]] = 0
        total_cost = sum(
            counts[entry["key"]] * entry["avg_price"] for entry in DRINK_TYPES
        )
        total_drinks = sum(counts.values())
        travel_days = 7
        cost_per_day = total_cost / travel_days if travel_days else 0
        recommended_package = next(
            (pkg for pkg in PACKAGES if cost_per_day <= pkg["threshold"]),
            PACKAGES[-1],
        )
        recommendation = recommended_package["name"]
        drink_rows = [
            {
                "key": entry["key"],
                "label": entry["label"],
                "count": counts[entry["key"]],
                "avg_price": entry["avg_price"],
                "cost": counts[entry["key"]] * entry["avg_price"],
                "icon": entry["icon"],
            }
            for entry in DRINK_TYPES
        ]
        return render_template(
            "drink-tool.html",
            drink_rows=drink_rows,
            total_cost=total_cost,
            total_drinks=total_drinks,
            cost_per_day=cost_per_day,
            recommendation=recommendation,
            packages=PACKAGES,
            recommended_package=recommended_package,
        )


def run_webapp(
    config_path: str = "config.yaml",
    host: str = "127.0.0.1",
    port: int = 5000,
    enable_scheduler: bool = False,
    run_on_startup: bool = True,
) -> None:
    if (
        str(Path(config_path).resolve()) == str(Path(_DEFAULT_CONFIG_PATH).resolve())
        and enable_scheduler == _DEFAULT_ENABLE_SCHEDULER
        and run_on_startup == _DEFAULT_RUN_ON_STARTUP
    ):
        web_app = app
    else:
        web_app = create_app(
            config_path=config_path,
            enable_scheduler=enable_scheduler,
            run_on_startup=run_on_startup,
        )
    web_app.run(host=host, port=port, debug=False)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RC Price Tracker Web App")
    parser.add_argument("--config", default=os.environ.get("RC_CONFIG_PATH", "config.yaml"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument(
        "--enable-scheduler",
        action="store_true",
        default=os.environ.get("RC_ENABLE_SCHEDULER", "0") == "1",
        help="Enable scheduled checks in web mode.",
    )
    parser.add_argument(
        "--no-run-on-startup",
        action="store_true",
        help="Disable automatic all-module run on web app startup.",
    )
    return parser.parse_args()


_DEFAULT_CONFIG_PATH = os.environ.get("RC_CONFIG_PATH", "config.yaml")
_DEFAULT_ENABLE_SCHEDULER = os.environ.get("RC_ENABLE_SCHEDULER", "0") == "1"
_DEFAULT_RUN_ON_STARTUP = os.environ.get("RC_RUN_ON_STARTUP", "1") == "1"

# Gunicorn entrypoint: gunicorn -w 1 -b 0.0.0.0:8000 webapp:app
app = create_app(
    config_path=_DEFAULT_CONFIG_PATH,
    enable_scheduler=_DEFAULT_ENABLE_SCHEDULER,
    run_on_startup=_DEFAULT_RUN_ON_STARTUP,
)


if __name__ == "__main__":
    args = _parse_args()
    run_webapp(
        config_path=args.config,
        host=args.host,
        port=args.port,
        enable_scheduler=args.enable_scheduler,
        run_on_startup=not args.no_run_on_startup,
    )
