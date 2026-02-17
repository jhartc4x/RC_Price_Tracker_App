
import requests
import yaml
import json
import os
import sys
import re
from bs4 import BeautifulSoup

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

if not username or not password:
    print("No credentials found.")
    sys.exit(1)

print(f"Authenticating as {username}...")
sys.path.append(os.getcwd())
try:
    from modules import auth
    # session is returned as third element
    access_token, account_id, session = auth.login(username, password, "royal")
    print(f"Authentication successful.")
except Exception as e:
    print(f"Auth failed: {e}")
    sys.exit(1)

CLUB_ROYALE_URL = "https://www.royalcaribbean.com/club-royale/offers/"
print(f"Fetching {CLUB_ROYALE_URL}...")

resp = session.get(CLUB_ROYALE_URL)
if resp.status_code != 200:
    print(f"Failed to fetch page: {resp.status_code}")
    sys.exit(1)

html = resp.text
print(f"Page size: {len(html)} bytes")

# 1. Search for Next.js App Router stream
# Pattern: self.__next_f.push([1,"...json string..."])
# We need to extract the string parts and reassemble or parse individual chunks.

print("Searching for self.__next_f.push...")
chunks = re.findall(r'self\.__next_f\.push\((.*?)\)', html)

with open("debug_chunks.txt", "w") as f:
    for i, chunk in enumerate(chunks):
        f.write(f"--- Chunk {i} ---\n")
        f.write(chunk)
        f.write("\n\n")

print(f"Dumped {len(chunks)} chunks to debug_chunks.txt")

# Check file for sailings
found = False
for chunk in chunks:
    if "sailings" in chunk:
        found = True
        print(f"FOUND 'sailings' in chunk of length {len(chunk)}")
        # print snippet
        idx = chunk.find("sailings")
        print(f"Context: {chunk[idx:idx+200]}")

if not found:
    print("STILL NOT FOUND 'sailings' in chunks.")
