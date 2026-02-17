
import sys
import os

print("Verifying imports...")
sys.path.append(os.getcwd())

try:
    import modules.auth
    print("MATCH: modules.auth")
    import modules.cruise_prices
    print("MATCH: modules.cruise_prices")
    import modules.addons
    print("MATCH: modules.addons")
    import modules.casino
    print("MATCH: modules.casino")
    import modules.database
    print("MATCH: modules.database")
    import modules.notify
    print("MATCH: modules.notify")
    import tracker
    print("MATCH: tracker")
    import webapp
    print("MATCH: webapp")
    print("ALL MODULES IMPORTED SUCCESSFULLY.")
except Exception as e:
    print(f"IMPORT ERROR: {e}")
    sys.exit(1)
