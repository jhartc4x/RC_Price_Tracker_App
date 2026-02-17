"""Royal Caribbean/Celebrity OAuth2 authentication."""

from __future__ import annotations

import base64
import json
from typing import Tuple

import requests

AUTHORIZATION_HEADER = (
    "Basic "
    "ZzlTMDIzdDc0NDczWlVrOTA5Rk42OEYwYjRONjdQU09oOTJvMDR2TDBCUjY1MzdwSTJ5Mmg5NE02QmJV"
    "N0Q2SjpXNjY4NDZrUFF2MTc1MDk3NW9vZEg1TTh6QzZUYTdtMzBrSDJRNzhsMldtVTUwRkNncXBQMTN3"
    "NzczNzdrN0lC"
)

TOKEN_ENDPOINTS = {
    "royal": "https://www.royalcaribbean.com/auth/oauth2/access_token",
    "celebrity": "https://www.celebritycruises.com/auth/oauth2/access_token",
}


def _extract_account_id(access_token: str) -> str:
    parts = access_token.split(".")
    if len(parts) != 3:
        raise ValueError("Access token did not look like a JWT.")

    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload + padding)
    data = json.loads(decoded.decode("utf-8"))
    account_id = data.get("sub")
    if not account_id:
        raise ValueError("JWT payload did not contain sub/account id.")
    return account_id


def login(
    username: str,
    password: str,
    cruise_line: str = "royal",
) -> Tuple[str, str, requests.Session]:
    line = (cruise_line or "royal").strip().lower()
    if line not in TOKEN_ENDPOINTS:
        raise ValueError("cruise_line must be 'royal' or 'celebrity'.")


    session = requests.Session()
    # Add User-Agent to mimic browser
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    })
    
    headers = {
        "Authorization": AUTHORIZATION_HEADER,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "password",
        "username": username,
        "password": password,
        "scope": "openid profile email vdsid",
    }

    url = TOKEN_ENDPOINTS[line]
    max_retries = 3
    
    for attempt in range(1, max_retries + 1):
        try:
            response = session.post(url, headers=headers, data=data, timeout=60)
            if response.status_code == 200:
                break
            
            # If not 200, raise specific error to trigger retry or fail final
            snippet = " ".join(response.text.split())[:300]
            message = (
                f"Login failed for {username} ({line}). "
                f"HTTP {response.status_code}: {snippet}"
            )
            if attempt == max_retries:
                print(f"[ERROR] {message}")
                raise RuntimeError(message)
            else:
                print(f"[WARN] Auth attempt {attempt} failed (HTTP {response.status_code}). Retrying...")
                
        except requests.RequestException as e:
            if attempt == max_retries:
                print(f"[ERROR] Auth failed after {max_retries} attempts: {e}")
                raise RuntimeError(
                    f"Login failed for {username} after {max_retries} attempts. "
                    f"Last error: {e}"
                )
            print(f"[WARN] Auth attempt {attempt} error: {e}. Retrying...")

    payload = response.json()
    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError("Login succeeded but response did not include access_token.")

    account_id = _extract_account_id(access_token)
    return access_token, account_id, session

