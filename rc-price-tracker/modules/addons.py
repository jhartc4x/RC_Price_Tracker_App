"""Add-on price checks using Royal Caribbean internal APIs."""

from __future__ import annotations

import json
import time
from datetime import date
from typing import Any

import requests

from modules.casino import get_loyalty_status, print_loyalty_summary

MOBILE_APPKEY = "cdCNc04srNq4rBvKofw1aC50dsdSaPuc"
WEB_APPKEY = "hyNNqIPHHzaLzVpcICPdAdbFV8yvTsAm"
MOBILE_SHIPS_URL = "https://api.rccl.com/en/all/mobile/v2/ships"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

# Categories to scrape for "Available" items
CATALOG_CATEGORIES = {
    "1000000002": "Beverage",
    "1000000003": "Internet",
    "1000000004": "Dining",
}

_ship_cache: dict[str, str] | None = None


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _payload(data: Any) -> Any:
    if isinstance(data, dict) and isinstance(data.get("payload"), (dict, list)):
        return data["payload"]
    return data


def _extract_ship_dictionary(data: Any) -> dict[str, str]:
    raw = _payload(data)

    if isinstance(raw, dict):
        if all(isinstance(k, str) and isinstance(v, str) for k, v in raw.items()):
            return raw

        ships = raw.get("ships") if isinstance(raw, dict) else None
        if isinstance(ships, list):
            return _extract_ship_dictionary(ships)

    if isinstance(raw, list):
        mapping: dict[str, str] = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            code = item.get("shipCode") or item.get("code") or item.get("id")
            name = item.get("shipName") or item.get("name") or code
            if code:
                mapping[str(code)] = str(name)
        if mapping:
            return mapping

    return {}


def get_ship_dictionary() -> dict[str, str]:
    global _ship_cache
    if _ship_cache is not None:
        return _ship_cache

    headers = {"appkey": MOBILE_APPKEY, "appversion": "1.54.0"}
    try:
        response = requests.get(MOBILE_SHIPS_URL, headers=headers, timeout=30)
        response.raise_for_status()
        _ship_cache = _extract_ship_dictionary(response.json())
    except Exception:
        _ship_cache = {}

    if not _ship_cache:
        print(f"{YELLOW}[ADDONS] Could not parse ship dictionary; using ship codes only.{RESET}")
    return _ship_cache


def _extract_bookings(data: Any) -> list[dict[str, Any]]:
    source = _payload(data)
    if isinstance(source, dict) and isinstance(source.get("profileBookings"), list):
        return source["profileBookings"]
    if isinstance(data, dict) and isinstance(data.get("profileBookings"), list):
        return data["profileBookings"]
    return []


def _extract_orders(data: Any) -> list[dict[str, Any]]:
    source = _payload(data)
    if not isinstance(source, dict):
        return []

    orders: list[dict[str, Any]] = []
    for key in ("myOrders", "ordersOthersHaveBookedForMe"):
        value = source.get(key)
        if isinstance(value, list):
            orders.extend([v for v in value if isinstance(v, dict)])
    return orders


def _extract_order_items(data: Any) -> list[dict[str, Any]]:
    source = _payload(data)
    if isinstance(source, dict) and isinstance(source.get("orderHistoryDetailItems"), list):
        return [item for item in source["orderHistoryDetailItems"] if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("orderHistoryDetailItems"), list):
        return [item for item in data["orderHistoryDetailItems"] if isinstance(item, dict)]
    return []


def _date_from_iso(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _estimate_nights(booking: dict[str, Any]) -> int:
    for key in ("numberOfNights", "nights", "duration"):
        nights = _as_int(booking.get(key), default=0)
        if nights > 0:
            return nights

    start = _date_from_iso(booking.get("sailDate") or booking.get("startDate"))
    end = _date_from_iso(booking.get("returnDate") or booking.get("endDate"))
    if start and end and end > start:
        return max((end - start).days, 1)

    return 1


def _normalize_paid_price(paid_price: float, sales_unit: str | None, quantity: int, nights: int) -> float:
    value = paid_price
    if sales_unit in {"PER_NIGHT", "PER_DAY"} and nights > 0:
        value = value / nights
    if quantity > 1:
        value = value / quantity
    return round(value, 2)


def _extract_current_price(data: Any) -> float | None:
    source = _payload(data)
    if not isinstance(source, dict):
        return None

    starting = source.get("startingFromPrice")
    if not isinstance(starting, dict):
        # Fallback for catalog response which might be different
        price = source.get("price") or source.get("lowestPrice")
        if price:
            return _as_float(price)
        return None

    promo = starting.get("adultPromotionalPrice")
    if promo is not None:
        return _as_float(promo)

    shipboard = starting.get("adultShipboardPrice")
    if shipboard is not None:
        return _as_float(shipboard)

    return None


def _fetch_json(session: requests.Session, url: str, headers: dict[str, str], params: dict[str, Any]) -> Any:
    response = session.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def check_all_addons(
    account_config: dict,
    db,
    notifier,
    settings: dict,
    auth_context: dict,
) -> None:
    access_token = auth_context["access_token"]
    account_id = auth_context["account_id"]
    session: requests.Session = auth_context["session"]
    brand_code = auth_context["brand_code"]
    account_username = str(account_config.get("username") or f"account-{account_id}")

    currency = settings.get("currency", "USD")
    threshold = _as_float(settings.get("min_savings_threshold"), default=5.0)
    categories_filter = set(settings.get("addon_categories") or [])

    try:
        loyalty_data = get_loyalty_status(access_token, account_id)
        if loyalty_data:
            print_loyalty_summary(loyalty_data)
    except Exception as exc:
        print(f"{YELLOW}[ADDONS] Loyalty status lookup failed: {exc}{RESET}")

    ships = get_ship_dictionary()

    booking_headers = {
        "Access-Token": access_token,
        "AppKey": WEB_APPKEY,
        "vds-id": account_id,
    }
    booking_params = {"brand": brand_code, "includeCheckin": "false"}
    bookings_url = f"https://aws-prd.api.rccl.com/v1/profileBookings/enriched/{account_id}"

    try:
        bookings_data = _fetch_json(session, bookings_url, booking_headers, booking_params)
    except Exception as exc:
        print(f"{RED}[ADDONS] Failed to fetch bookings: {exc}{RESET}")
        return

    bookings = _extract_bookings(bookings_data)

    if not bookings:
        print(f"{YELLOW}[ADDONS] No booked reservations found.{RESET}")
        return

    # Track distinct items we have processed to avoid checking them again in catalog loop
    # Key: reservation_id|product_code
    processed_products: set[str] = set()

    for booking in bookings:
        reservation_id = str(booking.get("reservationId") or booking.get("bookingId") or "")
        
        if not reservation_id:
            print(f"{YELLOW}[ADDONS] Skipping booking with no ID (res/booking).{RESET}")
            continue

        ship_code = str(booking.get("shipCode") or "")
        sail_date = str(booking.get("sailDate") or "")
        ship_name = ships.get(ship_code, ship_code or "Unknown Ship")
        nights = _estimate_nights(booking)
        stateroom_number = str(booking.get("stateroomNumber") or "")
        passengers = booking.get("passengers", []) or []
        guest_count = len(passengers) if isinstance(passengers, list) else 0

        db.insert_booked_cruise(
            {
                "account_username": account_username,
                "cruise_line": account_config.get("cruise_line", "royal"),
                "reservation_id": reservation_id,
                "sail_date": sail_date,
                "ship_code": ship_code,
                "ship_name": ship_name,
                "stateroom_number": stateroom_number,
                "guest_count": guest_count,
                "raw_details": booking,
            }
        )

        print(f"{GREEN}[ADDONS] Checking reservation {reservation_id} on {ship_name}.{RESET}")

        passenger_ids = set()
        top_pid = booking.get("passengerId")
        if top_pid:
            passenger_ids.add(str(top_pid))
        for p in passengers:
            pid = p.get("id") or p.get("passengerId")
            if pid:
                passenger_ids.add(str(pid))
        
        # Primary passenger for catalog searches
        primary_passenger_id = list(passenger_ids)[0] if passenger_ids else None

        if not passenger_ids:
            print(f"{YELLOW}[ADDONS] No passenger IDs for reservation {reservation_id}; skipping.{RESET}")
            continue

        # 1. Process Order History (Purchased Items)
        for passenger_id in passenger_ids:
            history_headers = {
                "Access-Token": access_token,
                "AppKey": WEB_APPKEY,
                "Account-Id": account_id,
            }
            history_params = {
                "passengerId": passenger_id,
                "reservationId": reservation_id,
                "sailingId": f"{ship_code}{sail_date}",
                "currencyIso": currency,
                "includeMedia": "false",
            }
            history_url = (
                "https://aws-prd.api.rccl.com/en/royal/web/commerce-api/calendar/v1/"
                f"{ship_code}/orderHistory"
            )

            try:
                order_history_data = _fetch_json(session, history_url, history_headers, history_params)
            except Exception as exc:
                print(
                    f"{YELLOW}[ADDONS] Order history failed for {reservation_id}/{passenger_id}: "
                    f"{exc}{RESET}"
                )
                continue

            for order in _extract_orders(order_history_data):
                order_code = order.get("orderCode")
                total = _as_float((order.get("orderTotals") or {}).get("total"), default=0.0)
                if not order_code or total <= 0:
                    continue

                detail_url = (
                    "https://aws-prd.api.rccl.com/en/royal/web/commerce-api/calendar/v1/"
                    f"{ship_code}/orderHistory/{order_code}"
                )
                try:
                    detail_data = _fetch_json(session, detail_url, history_headers, history_params)
                except Exception as exc:
                    print(f"{YELLOW}[ADDONS] Failed order detail {order_code}: {exc}{RESET}")
                    continue

                for item in _extract_order_items(detail_data):
                    product_summary = item.get("productSummary") or {}
                    prefix = ((product_summary.get("productTypeCategory") or {}).get("id") or "").strip()
                    if not prefix:
                        continue
                    
                    # Store product code to avoid duplicate checks in catalog
                    product_id = str(product_summary.get("id") or "")
                    base_id = str(product_summary.get("baseId") or "")
                    product_code = base_id if prefix in {"pt_beverage", "pt_internet"} else product_id
                    
                    if not product_code:
                        continue
                        
                    processed_key = f"{reservation_id}|{product_code}"
                    processed_products.add(processed_key)

                    if categories_filter and prefix not in categories_filter:
                        continue

                    title = str(product_summary.get("title") or f"{prefix} {product_code}")
                    sales_unit = product_summary.get("salesUnit")

                    for guest in item.get("guests", []) or []:
                        order_status = str(guest.get("orderStatus") or item.get("orderStatus") or "").upper()
                        if order_status == "CANCELLED":
                            continue

                        guest_id = str(guest.get("id") or passenger_id)
                        guest_reservation_id = str(guest.get("reservationId") or reservation_id)
                        passenger_name = str(guest.get("firstName") or guest_id)
                        
                        price_details = guest.get("priceDetails") or {}
                        paid_subtotal = _as_float(price_details.get("subtotal"), default=0.0)
                        quantity = _as_int(price_details.get("quantity"), default=1)
                        paid_currency = str(price_details.get("currency") or currency)
                        paid_price = _normalize_paid_price(
                            paid_subtotal,
                            sales_unit,
                            quantity,
                            nights,
                        )

                        catalog_headers = {
                            "Access-Token": access_token,
                            "AppKey": WEB_APPKEY,
                            "vds-id": account_id,
                        }
                        catalog_params = {
                            "reservationId": guest_reservation_id,
                            "startDate": sail_date,
                            "currencyIso": paid_currency,
                            "passengerId": guest_id,
                            "resGuests": guest_id, # Can help with pricing accuracy
                        }
                        catalog_url = (
                            "https://aws-prd.api.rccl.com/en/royal/web/commerce-api/catalog/v2/"
                            f"{ship_code}/categories/{prefix}/products/{product_code}"
                        )

                        try:
                            catalog_data = _fetch_json(session, catalog_url, catalog_headers, catalog_params)
                        except Exception as exc:
                            print(
                                f"{YELLOW}[ADDONS] Price lookup failed for {title} ({product_code}): "
                                f"{exc}{RESET}"
                            )
                            continue

                        current_price = _extract_current_price(catalog_data)
                        if current_price is None:
                            print(
                                f"{YELLOW}[ADDONS] {title} ({passenger_name}) is no longer for sale.{RESET}"
                            )
                            # Record unavailable state
                            db.insert_price(
                                {
                                    "record_type": "addon",
                                    "account_username": account_username,
                                    "reservation_id": guest_reservation_id,
                                    "product_code": product_code,
                                    "product_name": f"{title} (unavailable)",
                                    "passenger_name": passenger_name,
                                    "sail_date": sail_date,
                                    "ship_code": ship_code,
                                    "paid_price": paid_price,
                                    "current_price": paid_price,
                                    "currency": paid_currency,
                                    "notified": 0,
                                    "label": account_config.get("username"),
                                }
                            )
                            time.sleep(0.5)
                            continue

                        last_record = db.get_last_price(
                            product_code,
                            guest_reservation_id,
                            passenger_name,
                            account_username=account_username,
                        )
                        changed = (
                            last_record is None
                            or _as_float(last_record.get("current_price"), default=-999999.0)
                            != current_price
                        )
                        savings = round(paid_price - current_price, 2)
                        should_alert = (
                            paid_price > 0
                            and current_price < paid_price
                            and savings > threshold
                            and changed
                        )

                        if should_alert:
                            print(
                                f"{RED}[ADDONS] DROP {title} ({passenger_name}): "
                                f"${current_price:.2f} (paid ${paid_price:.2f}, save ${savings:.2f})"
                                f"{RESET}"
                            )
                            notifier.send(
                                "RC Add-on Price Drop",
                                (
                                    f"{title} ({passenger_name})\n"
                                    f"Current: ${current_price:.2f} {paid_currency}\n"
                                    f"Paid: ${paid_price:.2f} {paid_currency}\n"
                                    f"Savings: ${savings:.2f}"
                                ),
                            )
                        else:
                            print(
                                f"{GREEN}[ADDONS] {title} ({passenger_name}): "
                                f"${current_price:.2f} (paid ${paid_price:.2f}){RESET}"
                            )

                        db.insert_price(
                            {
                                "record_type": "addon",
                                "account_username": account_username,
                                "reservation_id": guest_reservation_id,
                                "product_code": product_code,
                                "product_name": title,
                                "passenger_name": passenger_name,
                                "sail_date": sail_date,
                                "ship_code": ship_code,
                                "paid_price": paid_price,
                                "current_price": current_price,
                                "currency": paid_currency,
                                "notified": int(should_alert),
                                "label": account_config.get("username"),
                            }
                        )

                        time.sleep(0.5)

        # 2. Process Available Catalog Items (Not Purchased)
        if not primary_passenger_id:
            continue
            
        print(f"{GREEN}[ADDONS] Scanning available catalog items for {ship_name}...{RESET}")
        
        catalog_headers = {
            "Access-Token": access_token,
            "AppKey": WEB_APPKEY,
            "vds-id": account_id,
        }
        
        for cat_id, cat_name in CATALOG_CATEGORIES.items():
            cat_url = (
                "https://aws-prd.api.rccl.com/en/royal/web/commerce-api/catalog/v2/"
                f"{ship_code}/categories/{cat_id}/products"
            )
            cat_params = {
                "reservationId": reservation_id,
                "startDate": sail_date,
                "currencyIso": currency,
                "passengerId": primary_passenger_id,
                "resGuests": primary_passenger_id,
            }
            
            products = []
            try:
                # Try GET first
                products_resp = _fetch_json(session, cat_url, catalog_headers, cat_params)
                products = products_resp.get("products") or []
            except requests.exceptions.HTTPError as err:
                if err.response.status_code == 405:
                    # 405 Method Not Allowed implies we likely need POST for this endpoint
                    try:
                        # For POST, params usually go in body
                        # Fix: resGuests often expects a list in POST body
                        post_payload = cat_params.copy()
                        # Add sailingId just in case
                        post_payload["sailingId"] = f"{ship_code}{sail_date}"

                        # Remove resGuests entirely for POST as it implies GET-style param
                        post_payload.pop("resGuests", None)

                        print(f"{YELLOW}[ADDONS] CLEANED POST Payload: {json.dumps(post_payload)}{RESET}")
                        post_resp = session.post(cat_url, headers=catalog_headers, json=post_payload, timeout=30)
                        if post_resp.status_code != 200:
                             print(f"{YELLOW}[ADDONS] Catalog {cat_name} POST failed ({post_resp.status_code}): {post_resp.text[:200]}{RESET}")
                        post_resp.raise_for_status()
                        products = post_resp.json().get("products") or []
                    except Exception as post_exc:
                        err_body = ""
                        if hasattr(post_exc, "response") and post_exc.response is not None:
                             # Capture body from HTTPError or similar
                             err_body = f" Body: {post_exc.response.text[:200]}"
                        print(f"{YELLOW}[ADDONS] Catalog {cat_name} POST error: {post_exc}{err_body}{RESET}")
                        continue
                elif err.response.status_code in (401, 403, 404):
                    print(f"{YELLOW}[ADDONS] Catalog {cat_name} access denied (HTTP {err.response.status_code}).{RESET}")
                    continue
                else:
                    print(f"{YELLOW}[ADDONS] Catalog {cat_name} error: {err}{RESET}")
                    continue
            except Exception as exc:
                print(f"{YELLOW}[ADDONS] Catalog scan failed for {cat_name}: {exc}{RESET}")
                continue
            
            count_new = 0
            for prod in products:
                base_id = str(prod.get("baseId") or "")
                prod_id = str(prod.get("id") or "")
                code = base_id if base_id else prod_id
                
                if not code:
                    continue

                check_key = f"{reservation_id}|{code}"
                if check_key in processed_products:
                    continue  # Already processed as purchased

                title = prod.get("title") or prod.get("name") or "Unknown Product"
                current_price = _extract_current_price(prod)
                
                if current_price is None:
                    continue

                # Insert as "Available" (paid_price = None)
                # We reuse 'addon' type but maybe we want 'catalog'?
                # For now 'addon' works, standardizing passenger_name="Available" or similar.
                
                db.insert_price({
                    "record_type": "addon",
                    "account_username": account_username,
                    "reservation_id": reservation_id,
                    "product_code": code,
                    "product_name": title,
                    "passenger_name": "Available", # Generic
                    "sail_date": sail_date,
                    "ship_code": ship_code,
                    "paid_price": None, # Indicates not purchased
                    "current_price": current_price,
                    "currency": currency,
                    "notified": 0,
                    "label": account_config.get("username"),
                })
                processed_products.add(check_key)
                count_new += 1
            
            if count_new > 0:
                print(f"{GREEN}[ADDONS] Added {count_new} available {cat_name} items.{RESET}")
            time.sleep(1)
