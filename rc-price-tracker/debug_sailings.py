
import requests
import yaml
import json
import os
import sys

# Load Config
CONFIG_PATH = os.environ.get("RC_CONFIG_PATH", "config.yaml")

def load_config():
    if not os.path.exists(CONFIG_PATH):
        print("Config not found.")
        sys.exit(1)
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

config = load_config()
account = config.get("accounts", [{}])[0]
username = account.get("username")
password = account.get("password")
lastname = account.get("last_name")

if not username or not password:
    print("No credentials found in config.")
    sys.exit(1)

print(f"Authenticating as {username}...")

# Simple Auth Flow (Partial duplication of auth.py for standalone debugging)
# Use the auth module's login function
sys.path.append(os.getcwd())
try:
    from modules import auth
    # auth.login returns (access_token, account_id, session)
    access_token, account_id, session = auth.login(username, password, "royal")
    print(f"Authentication successful. Account ID: {account_id}")
except Exception as e:
    print(f"Auth failed: {e}")
    sys.exit(1)
brand_code = "R"

# Loyalty Lookup (to get C&A ID)
from modules import casino
loyalty = casino.get_loyalty_status(access_token, account_id)
ca_id = loyalty.get("crownAndAnchorId")
print(f"C&A ID: {ca_id}")

# Hardcoded from check_db.py output
campaign_code = "26EST1"
offer_code = "26EST109"
player_offer_id = "9562853e-8d24-46c5-b20b-9e6849c5f953"

print(f"\n--- Probing Details for PlayerOfferId: {player_offer_id} ---")

# User snippet has firstName, lastName, offers[]
# This suggests a lookup by loyalty ID that returns details.

candidates = [
    # Path Variations based on Browser Hint
    f"https://www.royalcaribbean.com/services/casino-offers/v1/offers?cruiseLoyaltyId={ca_id}",
    f"https://www.royalcaribbean.com/services/casino-offers/v2/offers?cruiseLoyaltyId={ca_id}",
    f"https://www.royalcaribbean.com/services/casino/casino-offers/v1/offers?cruiseLoyaltyId={ca_id}",
    
    # Try the original V2 search with /services/ instead of /api/
    f"https://www.royalcaribbean.com/services/casino/casino-offers/v2/search?cruiseLoyaltyId={ca_id}&brand=R",
    
    # Try finding the specific offer
    f"https://www.royalcaribbean.com/services/casino-offers/v1/offer/{offer_code}/sailings",
]

# Add a POST probe - VARIATIONS
post_candidates = [
    # 1. Standard (what we use)
    ("https://www.royalcaribbean.com/api/casino/casino-offers/v2", {
        "brand": "R", "country": "USA", "language": "en", "cruiseLoyaltyId": ca_id,
        "includeSailings": True 
    }),
    # 2. explicit string "true" (unlikely but possible if bad parser)
    ("https://www.royalcaribbean.com/api/casino/casino-offers/v2", {
        "brand": "R", "country": "USA", "language": "en", "cruiseLoyaltyId": ca_id,
        "includeSailings": "true" 
    }),
    # 3. brand "ROYAL"
    ("https://www.royalcaribbean.com/api/casino/casino-offers/v2", {
        "brand": "ROYAL", "country": "USA", "language": "en", "cruiseLoyaltyId": ca_id,
        "includeSailings": True 
    }),
    # 4. brand "Royal Caribbean International"
    ("https://www.royalcaribbean.com/api/casino/casino-offers/v2", {
        "brand": "Royal Caribbean International", "country": "USA", "language": "en", "cruiseLoyaltyId": ca_id,
        "includeSailings": True 
    }),
    # 5. No language/country
    ("https://www.royalcaribbean.com/api/casino/casino-offers/v2", {
        "brand": "R", "cruiseLoyaltyId": ca_id,
        "includeSailings": True 
    }),
]

headers = {
    "Authorization": f"Bearer {access_token}",
    "Account-Id": account_id,
    "Content-Type": "application/json",
    "Referer": "https://www.royalcaribbean.com/club-royale/offers/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
}

# Create a fresh session for probing to avoid "Request Header Fields Too Large"
# from accumulated cookies in the auth session.
probe_session = requests.Session()

# for url in candidates:
#     print(f"Trying GET {url} ...")
#     try:
#         r = probe_session.get(url, headers=headers)
#         if r.status_code == 200:
#             print(f"SUCCESS! {url}")
#             print(json.dumps(r.json(), indent=2)[:500] + "...")
#         else:
#             print(f"Failed ({r.status_code}) : {r.text[:100]}")
#     except Exception as e:
#         print(f"Error: {e}")

for url, body in post_candidates:
    print(f"Trying POST {url} with {json.dumps(body)} ...")
    try:
        r = probe_session.post(url, headers=headers, json=body)
        if r.status_code == 200:
            print(f"SUCCESS! {url}")
            print(json.dumps(r.json(), indent=2)[:500] + "...")
            # Check if sailings are there
            data = r.json()
            # Handle both wrapped and unwrapped
            if "offers" in data:
                offers = data["offers"]
            else:
                offers = data.get("payload", {}).get("offers", [])
            
            if offers and isinstance(offers, list):
                # Check direct sailings (V1?) or nested (V2)
                s1 = offers[0].get("sailings") or offers[0].get("campaignOffer", {}).get("sailings", [])
                print(f"Sailings count in response (first offer): {len(s1)}")
                # Dump one sailing to see what it looks like
                if s1:
                    print(f"Sample sailing: {json.dumps(s1[0])}")
        else:
             print(f"Failed ({r.status_code}) : {r.text[:100]}")
    except Exception as e:
        print(f"Error: {e}")

sys.exit(0)

