"""Cruise cabin price scraping logic."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
}


def strip_params(url: str, params_to_remove: list[str] | None = None) -> str:
    remove_set = set(params_to_remove or ["r0y", "r0x"])
    parsed = urlparse(url)
    query = [(k, v) for (k, v) in parse_qsl(parsed.query, keep_blank_values=True) if k not in remove_set]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def _extract_redirect_path(html: str) -> str | None:
    match = re.search(r"NEXT_REDIRECT;replace;([^;]+);307;", html)
    if not match:
        return None
    return match.group(1)


def _extract_price(html: str) -> float | None:
    soup = BeautifulSoup(html, "html.parser")

    node = soup.find("span", attrs={"data-testid": "pricing-total"})
    if node is None:
        node = soup.find(
            "span",
            attrs={
                "class": "SummaryPrice_title__1nizh9x5",
                "data-testid": "pricing-total",
            },
        )

    if node is None:
        return None

    text = node.get_text(" ", strip=True).replace(",", "")
    match = re.search(r"\$(.*)USD", text)
    if not match:
        return None

    try:
        return float(match.group(1).strip())
    except ValueError:
        return None


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def check_cruise_price(cruise_config: dict, db, notifier, settings: dict) -> None:
    url = cruise_config.get("url")
    if not url:
        print(f"{YELLOW}[WARN] Skipping cruise entry with empty URL.{RESET}")
        return

    paid_price = _as_float(cruise_config.get("paid_price"), default=0.0)
    label = cruise_config.get("label") or "Cruise Fare"
    currency = settings.get("currency", "USD")
    threshold = _as_float(settings.get("min_savings_threshold"), default=5.0)

    cleaned_url = strip_params(url)
    parsed = urlparse(cleaned_url)
    query = dict(parse_qsl(parsed.query))
    sail_date = query.get("sailDate")
    ship_code = query.get("shipCode")

    session = requests.Session()
    current_url = cleaned_url
    current_price: float | None = None
    unavailable = False

    for _ in range(9):
        response = session.get(current_url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        redirect_path = _extract_redirect_path(response.text)
        if redirect_path:
            current_url = urljoin("https://www.royalcaribbean.com", redirect_path)
            continue

        current_price = _extract_price(response.text)
        unavailable = current_price is None
        break
    else:
        unavailable = True

    product_code = cleaned_url
    last_record = db.get_last_price(product_code, None, None)

    if unavailable:
        print(f"{YELLOW}[CRUISE] {label}: cabin unavailable or price not found.{RESET}")
        db.insert_price(
            {
                "record_type": "cruise",
                "reservation_id": None,
                "product_code": product_code,
                "product_name": f"{label} (unavailable)",
                "passenger_name": None,
                "sail_date": sail_date,
                "ship_code": ship_code,
                "paid_price": paid_price,
                "current_price": -1.0,
                "currency": currency,
                "notified": 0,
                "label": label,
            }
        )
        return

    assert current_price is not None
    price_changed = (
        last_record is None
        or _as_float(last_record.get("current_price"), default=-999999.0) != current_price
    )

    savings = round(paid_price - current_price, 2)
    should_alert = (
        paid_price > 0
        and current_price < paid_price
        and savings > threshold
        and price_changed
    )

    if should_alert:
        print(
            f"{RED}[CRUISE] {label}: ${current_price:.2f} (paid ${paid_price:.2f}, "
            f"save ${savings:.2f}){RESET}"
        )
        notifier.send(
            "RC Cruise Price Drop",
            (
                f"{label}\n"
                f"Current: ${current_price:.2f} {currency}\n"
                f"Paid: ${paid_price:.2f} {currency}\n"
                f"Potential savings: ${savings:.2f}"
            ),
        )
    else:
        print(
            f"{GREEN}[CRUISE] {label}: ${current_price:.2f} "
            f"(paid ${paid_price:.2f}){RESET}"
        )

    db.insert_price(
        {
            "record_type": "cruise",
            "reservation_id": None,
            "product_code": product_code,
            "product_name": label,
            "passenger_name": None,
            "sail_date": sail_date,
            "ship_code": ship_code,
            "paid_price": paid_price,
            "current_price": current_price,
            "currency": currency,
            "notified": int(should_alert),
            "label": label,
        }
    )
