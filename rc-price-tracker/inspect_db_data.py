import sqlite3
import json
import sys

DB_PATH = "price_tracker.db"

def inspect_latest_offer():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        row = cur.execute("SELECT offer_details, offer_code FROM casino_offers WHERE offer_code LIKE '26EST1%' ORDER BY id DESC LIMIT 1").fetchone()
        
        if not row:
            print("No offers found in DB.")
            return

        print(f"--- Latest Offer: {row['offer_code']} ---")
        details = json.loads(row['offer_details'])
        
        # Check keys
        print("Top keys:", list(details.keys()))
        
        if "campaignOffer" in details:
            print("Found 'campaignOffer'. Checking keys...")
            co = details["campaignOffer"]
            print("Keys in campaignOffer:", list(co.keys()))
            
            internal_code = co.get("offerCode")
            print(f"DEBUG: Internal offerCode = {internal_code}")
            
            inclusion = co.get("sailingInclusionMode")
            print(f"DEBUG: sailingInclusionMode = {inclusion}")

            if "sailings" in co:
                sailings = co["sailings"]
                print(f"FOUND 'sailings'! Count: {len(sailings)}")
                if sailings:
                    print("Sample sailing:", json.dumps(sailings[0], indent=2))
            else:
                print("MISSING 'sailings' in campaignOffer.")
        else:
            print("MISSING 'campaignOffer' in details.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    inspect_latest_offer()
