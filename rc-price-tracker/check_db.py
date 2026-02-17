
import sqlite3
import os

DB_PATH = "price_tracker.db"

abs_path = os.path.abspath(DB_PATH)
print(f"Checking Database at: {abs_path}")

if not os.path.exists(DB_PATH):
    print(f"Database {DB_PATH} not found.")
else:
    print(f"Opening {DB_PATH}...")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        
        tables = ["price_history", "casino_offers", "booked_cruises", "run_log"]
        for t in tables:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                print(f"Table '{t}': {count} rows")
            except Exception as e:
                print(f"Table '{t}' error: {e}")

        print("\n--- Casino Offers (Detail Dump) ---")
        row = conn.execute("SELECT offer_details FROM casino_offers LIMIT 1").fetchone()
        if row:
            import json
            details = row[0]
            try:
                parsed = json.loads(details)
                print(json.dumps(parsed, indent=2))
            except:
                print(details)
        else:
            print("No offers found to inspect.")
