"""SQLite persistence layer for price and offer tracking."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

_DB_PATH = "price_tracker.db"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = conn.execute(f"PRAGMA table_info({table})").fetchall()
    existing_names = {row["name"] for row in existing}
    if column not in existing_names:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db(db_path: str) -> None:
    global _DB_PATH
    _DB_PATH = db_path

    schema = """
    CREATE TABLE IF NOT EXISTS price_history (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        check_date      TEXT NOT NULL,
        record_type     TEXT NOT NULL,
        account_username TEXT,
        reservation_id  TEXT,
        product_code    TEXT,
        product_name    TEXT NOT NULL,
        passenger_name  TEXT,
        sail_date       TEXT,
        ship_code       TEXT,
        paid_price      REAL,
        current_price   REAL NOT NULL,
        currency        TEXT DEFAULT 'USD',
        notified        INTEGER DEFAULT 0,
        label           TEXT
    );

    CREATE TABLE IF NOT EXISTS casino_offers (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        check_date      TEXT NOT NULL,
        account_username TEXT,
        offer_code      TEXT,
        offer_type      TEXT,
        offer_details   TEXT,
        expiry_date     TEXT,
        is_new          INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS run_log (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        run_date        TEXT NOT NULL,
        module          TEXT NOT NULL,
        status          TEXT NOT NULL,
        message         TEXT
    );

    CREATE TABLE IF NOT EXISTS booked_cruises (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        check_date       TEXT NOT NULL,
        account_username TEXT,
        cruise_line      TEXT,
        reservation_id   TEXT,
        sail_date        TEXT,
        ship_code        TEXT,
        ship_name        TEXT,
        stateroom_number TEXT,
        guest_count      INTEGER,
        raw_details      TEXT
    );
    """

    with _connect() as conn:
        conn.executescript(schema)
        _ensure_column(conn, "price_history", "account_username", "TEXT")
        _ensure_column(conn, "casino_offers", "account_username", "TEXT")
        conn.commit()


def insert_price(record: dict[str, Any]) -> int:
    check_date = record.get("check_date") or _utc_now_iso()
    values = (
        check_date,
        record.get("record_type", "addon"),
        record.get("account_username"),
        record.get("reservation_id"),
        record.get("product_code"),
        record.get("product_name", "Unknown"),
        record.get("passenger_name"),
        record.get("sail_date"),
        record.get("ship_code"),
        record.get("paid_price"),
        record.get("current_price", 0.0),
        record.get("currency", "USD"),
        int(bool(record.get("notified", 0))),
        record.get("label"),
    )

    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO price_history (
                check_date, record_type, account_username, reservation_id, product_code, product_name,
                passenger_name, sail_date, ship_code, paid_price, current_price,
                currency, notified, label
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        conn.commit()
        return int(cur.lastrowid)


def get_last_price(
    product_code: str | None,
    reservation_id: str | None,
    passenger_name: str | None,
    account_username: str | None = None,
) -> dict[str, Any] | None:
    query = """
    SELECT *
    FROM price_history
    WHERE ((product_code = ?) OR (product_code IS NULL AND ? IS NULL))
      AND ((reservation_id = ?) OR (reservation_id IS NULL AND ? IS NULL))
      AND ((passenger_name = ?) OR (passenger_name IS NULL AND ? IS NULL))
    """

    params: list[Any] = [
        product_code,
        product_code,
        reservation_id,
        reservation_id,
        passenger_name,
        passenger_name,
    ]

    if account_username is not None:
        query += " AND account_username = ?"
        params.append(account_username)

    query += " ORDER BY id DESC LIMIT 1"

    with _connect() as conn:
        row = conn.execute(query, tuple(params)).fetchone()
        return dict(row) if row else None


def insert_casino_offer(offer: dict[str, Any]) -> int:
    details = offer.get("offer_details")
    if isinstance(details, (dict, list)):
        details = json.dumps(details, ensure_ascii=True)

    values = (
        offer.get("check_date") or _utc_now_iso(),
        offer.get("account_username"),
        offer.get("offer_code"),
        offer.get("offer_type"),
        details,
        offer.get("expiry_date"),
        int(bool(offer.get("is_new", 1))),
    )

    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO casino_offers (
                check_date, account_username, offer_code, offer_type, offer_details, expiry_date, is_new
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        conn.commit()
        return int(cur.lastrowid)


def offer_exists(offer_code: str | None, account_username: str | None = None) -> bool:
    if not offer_code:
        return False

    with _connect() as conn:
        if account_username:
            row = conn.execute(
                "SELECT 1 FROM casino_offers WHERE offer_code = ? AND account_username = ? LIMIT 1",
                (offer_code, account_username),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT 1 FROM casino_offers WHERE offer_code = ? LIMIT 1", (offer_code,)
            ).fetchone()
        return row is not None


def insert_booked_cruise(record: dict[str, Any]) -> int:
    details = record.get("raw_details")
    if isinstance(details, (dict, list)):
        details = json.dumps(details, ensure_ascii=True)

    values = (
        record.get("check_date") or _utc_now_iso(),
        record.get("account_username"),
        record.get("cruise_line"),
        record.get("reservation_id"),
        record.get("sail_date"),
        record.get("ship_code"),
        record.get("ship_name"),
        record.get("stateroom_number"),
        record.get("guest_count"),
        details,
    )

    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO booked_cruises (
                check_date, account_username, cruise_line, reservation_id, sail_date,
                ship_code, ship_name, stateroom_number, guest_count, raw_details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        conn.commit()
        return int(cur.lastrowid)


def log_run(module: str, status: str, message: str | None) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO run_log (run_date, module, status, message)
            VALUES (?, ?, ?, ?)
            """,
            (_utc_now_iso(), module, status, message),
        )
        conn.commit()


def purge_old_records(days: int) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()

    with _connect() as conn:
        conn.execute("DELETE FROM price_history WHERE check_date < ?", (cutoff,))
        conn.execute("DELETE FROM casino_offers WHERE check_date < ?", (cutoff,))
        conn.execute("DELETE FROM booked_cruises WHERE check_date < ?", (cutoff,))
        conn.execute("DELETE FROM run_log WHERE run_date < ?", (cutoff,))
        conn.commit()


def update_casino_offer(offer: dict[str, Any]) -> None:
    details = offer.get("offer_details")
    if isinstance(details, (dict, list)):
        details = json.dumps(details, ensure_ascii=True)

    with _connect() as conn:
        conn.execute(
            """
            UPDATE casino_offers
            SET check_date = ?, offer_details = ?, expiry_date = ?
            WHERE account_username = ? AND offer_code = ?
            """,
            (
                offer.get("check_date") or _utc_now_iso(),
                details,
                offer.get("expiry_date"),
                offer.get("account_username"),
                offer.get("offer_code"),
            ),
        )
        conn.commit()
