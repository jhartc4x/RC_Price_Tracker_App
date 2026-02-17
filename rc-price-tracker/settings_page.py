#!/usr/bin/env python3
"""Local GUI editor for rc-price-tracker config.yaml."""

from __future__ import annotations

import argparse
import copy
import re
import shutil
from pathlib import Path

import yaml

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
    _TK_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover
    tk = None
    ttk = None
    messagebox = None
    _TK_ERROR = exc


def _default_config() -> dict:
    return {
        "accounts": [
            {
                "username": "your@email.com",
                "password": "yourRCpassword",
                "cruise_line": "royal",
                "cna_number": "123456789",
                "last_name": "SMITH",
            }
        ],
        "cruise_watchlist": [
            {
                "url": "https://www.royalcaribbean.com/checkout/guest-info?sailDate=2026-06-13&shipCode=IC...",
                "paid_price": 4500.0,
                "label": "Icon of the Seas June 2026",
            }
        ],
        "addon_tracking": {"enabled": True},
        "casino_tracking": {"enabled": True, "notify_new_offers": True},
        "schedule": {"times": ["07:00", "19:00"], "timezone": "America/New_York"},
        "notifications": [{"url": "mailto://yourgmail:apppassword@gmail.com"}],
        "settings": {
            "currency": "USD",
            "min_savings_threshold": 5.0,
            "price_history_days": 90,
            "apprise_test": False,
        },
    }


def _load_config(path: Path) -> dict:
    config = _default_config()
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh) or {}
            if isinstance(loaded, dict):
                config.update(loaded)

    config.setdefault("accounts", [])
    config.setdefault("cruise_watchlist", [])
    config.setdefault("addon_tracking", {"enabled": True})
    config.setdefault("casino_tracking", {"enabled": True, "notify_new_offers": True})
    config.setdefault("schedule", {"times": ["07:00", "19:00"], "timezone": "America/New_York"})
    config.setdefault("notifications", [])
    config.setdefault("settings", {})
    return config


class SettingsPage:
    def __init__(self, root: tk.Tk, config_path: str):
        self.root = root
        self.config_path = Path(config_path)
        self.root.title(f"RC Price Tracker Settings - {self.config_path}")
        self.root.geometry("1080x760")

        self.account_rows: list[tuple[ttk.Frame, dict]] = []
        self.cruise_rows: list[tuple[ttk.Frame, dict]] = []
        self.notification_rows: list[tuple[ttk.Frame, tk.StringVar]] = []

        self.config = _load_config(self.config_path)
        self._build_ui()
        self._load_into_form(self.config)

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.accounts_tab = ttk.Frame(notebook)
        self.cruise_tab = ttk.Frame(notebook)
        self.notifications_tab = ttk.Frame(notebook)
        self.options_tab = ttk.Frame(notebook)

        notebook.add(self.accounts_tab, text="Accounts")
        notebook.add(self.cruise_tab, text="Cruise Watchlist")
        notebook.add(self.notifications_tab, text="Notifications")
        notebook.add(self.options_tab, text="Options")

        self._build_accounts_tab()
        self._build_cruise_tab()
        self._build_notifications_tab()
        self._build_options_tab()

        actions = ttk.Frame(self.root)
        actions.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(actions, text="Save", command=self.save).pack(side="left")
        ttk.Button(actions, text="Reload", command=self.reload).pack(side="left", padx=6)
        ttk.Button(actions, text="Quit", command=self.root.destroy).pack(side="right")

    def _build_accounts_tab(self) -> None:
        header = ttk.Frame(self.accounts_tab)
        header.pack(fill="x", padx=8, pady=8)
        ttk.Label(header, text="Accounts (one or more)").pack(side="left")
        ttk.Button(header, text="Add Account", command=self._add_account_row).pack(side="right")

        self.accounts_container = ttk.Frame(self.accounts_tab)
        self.accounts_container.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _build_cruise_tab(self) -> None:
        header = ttk.Frame(self.cruise_tab)
        header.pack(fill="x", padx=8, pady=8)
        ttk.Label(header, text="Cruise watchlist").pack(side="left")
        ttk.Button(header, text="Add Cruise", command=self._add_cruise_row).pack(side="right")

        self.cruise_container = ttk.Frame(self.cruise_tab)
        self.cruise_container.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _build_notifications_tab(self) -> None:
        header = ttk.Frame(self.notifications_tab)
        header.pack(fill="x", padx=8, pady=8)
        ttk.Label(header, text="Notification targets (Apprise URLs)").pack(side="left")
        ttk.Button(header, text="Add Notification", command=self._add_notification_row).pack(side="right")

        self.notifications_container = ttk.Frame(self.notifications_tab)
        self.notifications_container.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _build_options_tab(self) -> None:
        frame = ttk.Frame(self.options_tab)
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        self.addon_enabled_var = tk.BooleanVar(value=True)
        self.addon_categories_var = tk.StringVar(value="")
        self.casino_enabled_var = tk.BooleanVar(value=True)
        self.casino_notify_var = tk.BooleanVar(value=True)

        self.schedule_times_var = tk.StringVar(value="07:00,19:00")
        self.schedule_timezone_var = tk.StringVar(value="America/New_York")

        self.currency_var = tk.StringVar(value="USD")
        self.threshold_var = tk.StringVar(value="5.00")
        self.history_days_var = tk.StringVar(value="90")
        self.apprise_test_var = tk.BooleanVar(value=False)

        row = 0
        ttk.Checkbutton(frame, text="Enable add-on tracking", variable=self.addon_enabled_var).grid(
            row=row, column=0, sticky="w"
        )
        row += 1
        ttk.Label(frame, text="Add-on categories (comma-separated, optional)").grid(row=row, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.addon_categories_var, width=80).grid(row=row, column=1, sticky="ew", padx=(8, 0))
        row += 1

        ttk.Checkbutton(frame, text="Enable casino offer tracking", variable=self.casino_enabled_var).grid(
            row=row, column=0, sticky="w"
        )
        row += 1
        ttk.Checkbutton(frame, text="Notify only for new casino offers", variable=self.casino_notify_var).grid(
            row=row, column=0, sticky="w"
        )
        row += 1

        ttk.Label(frame, text="Schedule times (comma-separated HH:MM)").grid(row=row, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.schedule_times_var, width=80).grid(row=row, column=1, sticky="ew", padx=(8, 0))
        row += 1

        ttk.Label(frame, text="Timezone").grid(row=row, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.schedule_timezone_var, width=40).grid(row=row, column=1, sticky="w", padx=(8, 0))
        row += 1

        ttk.Label(frame, text="Currency").grid(row=row, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.currency_var, width=20).grid(row=row, column=1, sticky="w", padx=(8, 0))
        row += 1

        ttk.Label(frame, text="Minimum savings threshold").grid(row=row, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.threshold_var, width=20).grid(row=row, column=1, sticky="w", padx=(8, 0))
        row += 1

        ttk.Label(frame, text="Price history days to keep").grid(row=row, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.history_days_var, width=20).grid(row=row, column=1, sticky="w", padx=(8, 0))
        row += 1

        ttk.Checkbutton(frame, text="Send Apprise test on startup", variable=self.apprise_test_var).grid(
            row=row, column=0, sticky="w"
        )

        frame.columnconfigure(1, weight=1)

    def _add_account_row(self, data: dict | None = None) -> None:
        row_frame = ttk.Frame(self.accounts_container, relief="groove", borderwidth=1)
        row_frame.pack(fill="x", pady=4)

        vars_map = {
            "username": tk.StringVar(value=(data or {}).get("username", "")),
            "password": tk.StringVar(value=(data or {}).get("password", "")),
            "cruise_line": tk.StringVar(value=(data or {}).get("cruise_line", "royal")),
            "cna_number": tk.StringVar(value=(data or {}).get("cna_number", "")),
            "last_name": tk.StringVar(value=(data or {}).get("last_name", "")),
        }

        ttk.Label(row_frame, text="Email").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(row_frame, textvariable=vars_map["username"], width=30).grid(row=0, column=1, padx=4, pady=4)

        ttk.Label(row_frame, text="Password").grid(row=0, column=2, sticky="w", padx=4, pady=4)
        ttk.Entry(row_frame, textvariable=vars_map["password"], width=20, show="*").grid(row=0, column=3, padx=4, pady=4)

        ttk.Label(row_frame, text="Cruise Line").grid(row=0, column=4, sticky="w", padx=4, pady=4)
        ttk.Combobox(
            row_frame,
            textvariable=vars_map["cruise_line"],
            values=["royal", "celebrity"],
            width=10,
            state="readonly",
        ).grid(row=0, column=5, padx=4, pady=4)

        ttk.Label(row_frame, text="C&A #").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(row_frame, textvariable=vars_map["cna_number"], width=20).grid(row=1, column=1, padx=4, pady=4)

        ttk.Label(row_frame, text="Last Name").grid(row=1, column=2, sticky="w", padx=4, pady=4)
        ttk.Entry(row_frame, textvariable=vars_map["last_name"], width=20).grid(row=1, column=3, padx=4, pady=4)

        ttk.Button(
            row_frame,
            text="Remove",
            command=lambda: self._remove_account_row(row_frame, vars_map),
        ).grid(row=1, column=5, padx=4, pady=4)

        self.account_rows.append((row_frame, vars_map))

    def _remove_account_row(self, row_frame: ttk.Frame, vars_map: dict) -> None:
        row_frame.destroy()
        self.account_rows = [r for r in self.account_rows if r[0] != row_frame]

    def _add_cruise_row(self, data: dict | None = None) -> None:
        row_frame = ttk.Frame(self.cruise_container, relief="groove", borderwidth=1)
        row_frame.pack(fill="x", pady=4)

        vars_map = {
            "url": tk.StringVar(value=(data or {}).get("url", "")),
            "paid_price": tk.StringVar(value=str((data or {}).get("paid_price", "0.0"))),
            "label": tk.StringVar(value=(data or {}).get("label", "")),
        }

        ttk.Label(row_frame, text="URL").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(row_frame, textvariable=vars_map["url"], width=95).grid(
            row=0, column=1, columnspan=3, sticky="ew", padx=4, pady=4
        )

        ttk.Label(row_frame, text="Paid Price").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(row_frame, textvariable=vars_map["paid_price"], width=15).grid(row=1, column=1, padx=4, pady=4)

        ttk.Label(row_frame, text="Label").grid(row=1, column=2, sticky="w", padx=4, pady=4)
        ttk.Entry(row_frame, textvariable=vars_map["label"], width=40).grid(row=1, column=3, padx=4, pady=4)

        ttk.Button(
            row_frame,
            text="Remove",
            command=lambda: self._remove_cruise_row(row_frame),
        ).grid(row=1, column=4, padx=4, pady=4)

        self.cruise_rows.append((row_frame, vars_map))

    def _remove_cruise_row(self, row_frame: ttk.Frame) -> None:
        row_frame.destroy()
        self.cruise_rows = [r for r in self.cruise_rows if r[0] != row_frame]

    def _add_notification_row(self, url: str = "") -> None:
        row_frame = ttk.Frame(self.notifications_container, relief="groove", borderwidth=1)
        row_frame.pack(fill="x", pady=4)

        url_var = tk.StringVar(value=url)
        ttk.Label(row_frame, text="URL").pack(side="left", padx=4, pady=4)
        ttk.Entry(row_frame, textvariable=url_var, width=100).pack(side="left", fill="x", expand=True, padx=4, pady=4)
        ttk.Button(
            row_frame,
            text="Remove",
            command=lambda: self._remove_notification_row(row_frame),
        ).pack(side="right", padx=4, pady=4)

        self.notification_rows.append((row_frame, url_var))

    def _remove_notification_row(self, row_frame: ttk.Frame) -> None:
        row_frame.destroy()
        self.notification_rows = [r for r in self.notification_rows if r[0] != row_frame]

    def _clear_rows(self) -> None:
        for frame, _ in self.account_rows:
            frame.destroy()
        for frame, _ in self.cruise_rows:
            frame.destroy()
        for frame, _ in self.notification_rows:
            frame.destroy()

        self.account_rows.clear()
        self.cruise_rows.clear()
        self.notification_rows.clear()

    def _load_into_form(self, config: dict) -> None:
        self._clear_rows()

        accounts = config.get("accounts") or []
        for account in accounts:
            if isinstance(account, dict):
                self._add_account_row(account)
        if not self.account_rows:
            self._add_account_row()

        watchlist = config.get("cruise_watchlist") or []
        for cruise in watchlist:
            if isinstance(cruise, dict):
                self._add_cruise_row(cruise)
        if not self.cruise_rows:
            self._add_cruise_row()

        notifications = config.get("notifications") or []
        for item in notifications:
            if isinstance(item, dict):
                self._add_notification_row(str(item.get("url") or ""))
            elif isinstance(item, str):
                self._add_notification_row(item)
        if not self.notification_rows:
            self._add_notification_row()

        addon_tracking = config.get("addon_tracking") or {}
        self.addon_enabled_var.set(bool(addon_tracking.get("enabled", True)))
        self.addon_categories_var.set(
            ", ".join(addon_tracking.get("categories") or [])
        )

        casino_tracking = config.get("casino_tracking") or {}
        self.casino_enabled_var.set(bool(casino_tracking.get("enabled", True)))
        self.casino_notify_var.set(bool(casino_tracking.get("notify_new_offers", True)))

        schedule = config.get("schedule") or {}
        self.schedule_times_var.set(
            ", ".join([str(t) for t in (schedule.get("times") or ["07:00", "19:00"])])
        )
        self.schedule_timezone_var.set(str(schedule.get("timezone") or "America/New_York"))

        settings = config.get("settings") or {}
        self.currency_var.set(str(settings.get("currency") or "USD"))
        self.threshold_var.set(str(settings.get("min_savings_threshold", 5.0)))
        self.history_days_var.set(str(settings.get("price_history_days", 90)))
        self.apprise_test_var.set(bool(settings.get("apprise_test", False)))

    def _parse_schedule_times(self, value: str) -> list[str]:
        items = [item.strip() for item in value.split(",") if item.strip()]
        if not items:
            raise ValueError("Schedule times cannot be empty.")

        for item in items:
            if not re.match(r"^\d{2}:\d{2}$", item):
                raise ValueError(f"Invalid time format: {item}. Use HH:MM.")
            hour, minute = item.split(":", 1)
            if int(hour) > 23 or int(minute) > 59:
                raise ValueError(f"Invalid time value: {item}.")
        return items

    def _collect_config(self) -> dict:
        config = copy.deepcopy(_default_config())

        accounts = []
        for _, vars_map in self.account_rows:
            username = vars_map["username"].get().strip()
            password = vars_map["password"].get().strip()
            cruise_line = vars_map["cruise_line"].get().strip().lower() or "royal"
            cna_number = vars_map["cna_number"].get().strip()
            last_name = vars_map["last_name"].get().strip()

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
        config["accounts"] = accounts

        cruise_watchlist = []
        for _, vars_map in self.cruise_rows:
            url = vars_map["url"].get().strip()
            paid_price_text = vars_map["paid_price"].get().strip() or "0"
            label = vars_map["label"].get().strip()

            if not url:
                continue

            try:
                paid_price = float(paid_price_text)
            except ValueError as exc:
                raise ValueError(f"Invalid paid_price '{paid_price_text}' in cruise watchlist.") from exc

            cruise_watchlist.append(
                {
                    "url": url,
                    "paid_price": paid_price,
                    "label": label,
                }
            )

        config["cruise_watchlist"] = cruise_watchlist

        addon_categories = [
            item.strip()
            for item in self.addon_categories_var.get().split(",")
            if item.strip()
        ]
        addon_tracking = {"enabled": bool(self.addon_enabled_var.get())}
        if addon_categories:
            addon_tracking["categories"] = addon_categories
        config["addon_tracking"] = addon_tracking

        config["casino_tracking"] = {
            "enabled": bool(self.casino_enabled_var.get()),
            "notify_new_offers": bool(self.casino_notify_var.get()),
        }

        config["schedule"] = {
            "times": self._parse_schedule_times(self.schedule_times_var.get()),
            "timezone": self.schedule_timezone_var.get().strip() or "America/New_York",
        }

        notifications = []
        for _, url_var in self.notification_rows:
            url = url_var.get().strip()
            if url:
                notifications.append({"url": url})
        config["notifications"] = notifications

        try:
            threshold = float(self.threshold_var.get().strip())
        except ValueError as exc:
            raise ValueError("Minimum savings threshold must be a number.") from exc

        try:
            history_days = int(self.history_days_var.get().strip())
        except ValueError as exc:
            raise ValueError("Price history days must be an integer.") from exc

        if history_days <= 0:
            raise ValueError("Price history days must be greater than 0.")

        config["settings"] = {
            "currency": self.currency_var.get().strip() or "USD",
            "min_savings_threshold": threshold,
            "price_history_days": history_days,
            "apprise_test": bool(self.apprise_test_var.get()),
        }

        return config

    def save(self) -> None:
        try:
            config = self._collect_config()
        except Exception as exc:
            messagebox.showerror("Validation Error", str(exc))
            return

        try:
            if self.config_path.exists():
                backup_path = self.config_path.with_suffix(self.config_path.suffix + ".bak")
                shutil.copy2(self.config_path, backup_path)

            with self.config_path.open("w", encoding="utf-8") as fh:
                yaml.safe_dump(config, fh, sort_keys=False, default_flow_style=False)

            messagebox.showinfo("Saved", f"Saved settings to {self.config_path}")
        except Exception as exc:
            messagebox.showerror("Save Failed", str(exc))

    def reload(self) -> None:
        try:
            self.config = _load_config(self.config_path)
            self._load_into_form(self.config)
            messagebox.showinfo("Reloaded", f"Reloaded settings from {self.config_path}")
        except Exception as exc:
            messagebox.showerror("Reload Failed", str(exc))


def launch_settings_ui(config_path: str = "config.yaml") -> None:
    if tk is None or ttk is None or messagebox is None:
        raise RuntimeError("tkinter is required for --settings UI") from _TK_ERROR

    root = tk.Tk()
    SettingsPage(root, config_path)
    root.mainloop()


def main() -> int:
    parser = argparse.ArgumentParser(description="Open RC Price Tracker settings UI")
    parser.add_argument("--config", default="config.yaml", help="Path to config YAML file.")
    args = parser.parse_args()

    launch_settings_ui(args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
