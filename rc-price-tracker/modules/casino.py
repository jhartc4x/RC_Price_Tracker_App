"""Casino loyalty and Club Royale offer tracking."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

WEB_APPKEY = "hyNNqIPHHzaLzVpcICPdAdbFV8yvTsAm"
CLUB_ROYALE_URL = "https://www.royalcaribbean.com/club-royale/offers/"

GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _payload(data: Any) -> Any:
    if isinstance(data, dict) and isinstance(data.get("payload"), (dict, list)):
        return data["payload"]
    return data


def _extract_loyalty_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload = data.get("payload") if isinstance(data, dict) else None
    if isinstance(payload, dict) and isinstance(payload.get("loyaltyInformation"), dict):
        return payload.get("loyaltyInformation", {})
    if isinstance(data.get("loyaltyInformation"), dict):
        return data.get("loyaltyInformation", {})
    return {}


def get_loyalty_status(access_token: str, account_id: str) -> dict[str, Any]:
    url = "https://aws-prd.api.rccl.com/en/royal/web/v1/guestAccounts/loyalty/info"
    headers = {
        "Access-Token": access_token,
        "AppKey": WEB_APPKEY,
        "account-id": account_id,
    }

    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(
            f"Loyalty lookup failed (HTTP {response.status_code}): "
            f"{' '.join(response.text.split())[:200]}"
        )

    raw = response.json()
    info = _extract_loyalty_payload(raw)
    return {
        "crownAndAnchorId": info.get("crownAndAnchorId"),
        "crownAndAnchorSocietyLoyaltyTier": info.get("crownAndAnchorSocietyLoyaltyTier"),
        "crownAndAnchorSocietyLoyaltyIndividualPoints": info.get(
            "crownAndAnchorSocietyLoyaltyIndividualPoints"
        ),
        "crownAndAnchorSocietyLoyaltyRelationshipPoints": info.get(
            "crownAndAnchorSocietyLoyaltyRelationshipPoints"
        ),
        "clubRoyaleLoyaltyTier": info.get("clubRoyaleLoyaltyTier"),
        "clubRoyaleLoyaltyIndividualPoints": info.get("clubRoyaleLoyaltyIndividualPoints"),
    }


def print_loyalty_summary(loyalty_data: dict[str, Any]) -> None:
    ca_id = loyalty_data.get("crownAndAnchorId") or "N/A"
    ca_tier = loyalty_data.get("crownAndAnchorSocietyLoyaltyTier") or "N/A"
    ca_points = loyalty_data.get("crownAndAnchorSocietyLoyaltyIndividualPoints")

    print(
        f"{GREEN}[LOYALTY] C&A #{ca_id} | Tier: {ca_tier} | "
        f"Points: {ca_points if ca_points is not None else 'N/A'}{RESET}"
    )

    casino_points = loyalty_data.get("clubRoyaleLoyaltyIndividualPoints")
    casino_tier = loyalty_data.get("clubRoyaleLoyaltyTier")
    if casino_points:
        print(
            f"{GREEN}[LOYALTY] Club Royale Tier: {casino_tier or 'N/A'} | "
            f"Points: {casino_points}{RESET}"
        )


def _extract_expiry(text: str) -> str | None:
    patterns = [
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def _extract_offer_code(text: str) -> str | None:
    for token in re.findall(r"[A-Z0-9]{4,}", text.upper()):
        if any(ch.isalpha() for ch in token):
            return token
    return None


def _parse_offers_from_html(page_source: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(page_source, "html.parser")

    selectors = [
        "[data-offer-code]",
        ".offer-card",
        ".offer-item",
        ".offer-row",
        "tr",
        "li",
    ]

    seen_text = set()
    offers: list[dict[str, Any]] = []
    for selector in selectors:
        for node in soup.select(selector):
            text = " ".join(node.stripped_strings)
            if not text or len(text) < 12:
                continue
            if text in seen_text:
                continue
            seen_text.add(text)

            code = node.get("data-offer-code") if hasattr(node, "get") else None
            code = code or _extract_offer_code(text)
            expiry = _extract_expiry(text)
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            offer_type = lines[0][:120] if lines else "Offer"

            offers.append(
                {
                    "offer_code": code,
                    "offer_type": offer_type,
                    "offer_details": {"raw_text": text},
                    "expiry_date": expiry,
                }
            )

    unique: list[dict[str, Any]] = []
    seen_codes = set()
    for idx, offer in enumerate(offers, start=1):
        code = offer.get("offer_code")
        if not code:
            code = f"UNKNOWN-{idx}"
            offer["offer_code"] = code
        if code in seen_codes:
            continue
        seen_codes.add(code)
        unique.append(offer)

    return unique


def check_casino_offers(
    account_config: dict,
    db,
    notifier,
    settings: dict,
    auth_context: dict | None = None,
) -> None:
    account_username = str(account_config.get("username") or "unknown")
    notify_new = bool(settings.get("casino_notify_new", True))

    if not auth_context:
        print(f"{YELLOW}[CASINO] Skipped: authentication context required for new site.{RESET}")
        return

    access_token = auth_context["access_token"]
    account_id = auth_context["account_id"]
    session: requests.Session = auth_context["session"]

    # Try specific API endpoint for offers first (Pattern guess based on loyalty/info)
    # User provided: https://www.royalcaribbean.com/api/casino/casino-offers/v2 (POST)
    api_url = "https://www.royalcaribbean.com/api/casino/casino-offers/v2"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Account-Id": account_id,
        "Content-Type": "application/json",
        "Referer": CLUB_ROYALE_URL,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }
    
    # Fetch loyalty details for required IDs
    try:
        loyalty_info = get_loyalty_status(access_token, account_id)
        print(f"{YELLOW}[CASINO] Debug Loyalty Info: {json.dumps(loyalty_info, default=str)}{RESET}")
    except Exception as exc:
        print(f"{YELLOW}[CASINO] Failed to get loyalty ID for offers: {exc}{RESET}")
        return

    ca_id = loyalty_info.get("crownAndAnchorId")
    if not ca_id:
         print(f"{YELLOW}[CASINO] No C&A ID found; cannot fetch offers.{RESET}")
         return

    # "Brand is not valid" with ROYAL -> Try "R" (common abbreviation)
    # Debug script confirmed: consumerId causes 401. Only cruiseLoyaltyId needed.
    # Added includeSailings: True to get full details (2025-02-16)
    json_body = {
        "brand": "R", 
        "country": "USA",
        "language": "en",
        "cruiseLoyaltyId": ca_id,
        "includeSailings": True
    }

    print(f"{YELLOW}[CASINO] Debug Payload: {json.dumps(json_body)}{RESET}")

    offers_data = []
    
    try:
        # Method 1: Direct API (POST)
        resp = session.post(api_url, headers=headers, json=json_body, timeout=30)
        
        if resp.status_code == 200:
            payload = resp.json()
            
            # 1. Try direct 'offers' list from root (API V2 behavior with includeSailings=True)
            if "offers" in payload and isinstance(payload["offers"], list):
                 offers_data = payload["offers"]
            else:
                 # 2. Fallback to helper
                raw_offers = _payload(payload)
                if isinstance(raw_offers, list):
                    offers_data = raw_offers
                elif isinstance(raw_offers, dict) and "offers" in raw_offers:
                    offers_data = raw_offers["offers"]
        else:
            # Method 2: Fallback to scraping the page with auth?
             print(f"{YELLOW}[CASINO] API lookup at {api_url} returned {resp.status_code}: {resp.text[:200]}{RESET}")
            
    except Exception as exc:
        print(f"{YELLOW}[CASINO] API lookup failed: {exc}{RESET}")

    # Process discovered offers
    if not offers_data:
        # If API returned nothing, maybe try the HTML page with the session?
        try:
            page_resp = session.get(CLUB_ROYALE_URL, headers=headers, timeout=30)
            if page_resp.status_code == 200:
                offers_data = _parse_offers_from_html(page_resp.text)
        except Exception:
            pass
            
    if not offers_data:
        print(f"{YELLOW}[CASINO] No offers found (API & Page scrape).{RESET}")
        return

    new_count = 0
    for offer in offers_data:
        # Normalize offer structure
        # API might return different keys than HTML scrape
        # API might return different keys than HTML scrape
        code = (
            offer.get("offerCode")
            or offer.get("id")
            or offer.get("offer_code")
            or offer.get("campaignCode")
            or offer.get("externalOfferId")
        )
        if not code:
            print(f"{YELLOW}[CASINO] Skipping offer with no ID: {json.dumps(offer)[:100]}{RESET}")
            continue
            
        # Debug sailings count
        s_count = len(offer.get("sailings", []))
        if s_count > 0:
            print(f"{GREEN}[CASINO] Offer {code} has {s_count} sailings.{RESET}")
        elif offer.get("campaignOffer", {}).get("sailings"):
             # Handle nested structure if present (though parsing should have handled it?)
             s_count = len(offer.get("campaignOffer", {}).get("sailings", []))
             print(f"{GREEN}[CASINO] Offer {code} has {s_count} sailings (nested).{RESET}")
        else:
             print(f"{YELLOW}[CASINO] Offer {code} has 0 sailings.{RESET}")

        offer_type = offer.get("type") or offer.get("offerType") or offer.get("offer_type") or "Casino Offer"
        expiry = offer.get("expirationDate") or offer.get("expiry_date")
        
        is_new = not db.offer_exists(code, account_username=account_username)
        if is_new:
            new_count += 1
            db.insert_casino_offer(
                {
                    "check_date": _utc_now_iso(),
                    "account_username": account_username,
                    "offer_code": code,
                    "offer_type": offer_type,
                    "offer_details": json.dumps(offer, ensure_ascii=True),
                    "expiry_date": expiry,
                    "is_new": 1,
                }
            )
        else:
            # Update existing record to avoid duplicates
            db.update_casino_offer(
                {
                    "check_date": _utc_now_iso(),
                    "account_username": account_username,
                    "offer_code": code,
                    "offer_details": json.dumps(offer, ensure_ascii=True),
                    "expiry_date": expiry,
                }
            )

        if is_new and notify_new:
            notifier.send(
                "New Club Royale Offer",
                (
                    f"Account: {account_username}\n"
                    f"Offer code: {code}\n"
                    f"Type: {offer_type}\n"
                    f"Expires: {expiry or 'Unknown'}"
                ),
            )

    print(f"{GREEN}[CASINO] Synced {len(offers_data)} offers ({new_count} new).{RESET}")

