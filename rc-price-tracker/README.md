# Royal Caribbean Price Tracker

A Python tool to monitor Royal Caribbean and Celebrity pricing data from three sources:

1. Cruise cabin pricing from checkout page HTML
2. Personalized add-on pricing from Royal Caribbean internal APIs
3. Club Royale offers from ClubRoyaleOffers.com plus loyalty summary from RC API

This project automates the same network calls your browser already makes when you use these sites.

## Prerequisites

- Python 3.11+
- Google Chrome (required for ClubRoyaleOffers.com scraping)

## Installation

```bash
cd /Users/jhartung/Documents/RC_Price_Tracker/rc-price-tracker
pip install -r requirements.txt
```

## Configuration

1. Copy the sample config:

```bash
cp config_sample.yaml config.yaml
```

2. Edit `config.yaml` and fill in your account details, watchlist, schedule, and notification URL(s).

You can also use the built-in settings UI:

```bash
python tracker.py --settings
```

## How to Capture Your Cruise URL

1. Log out of royalcaribbean.com.
2. Start a mock booking for the exact ship, sail date, room type, and guest count.
3. Continue to the **Guest Info** page where the blue price bar appears.
4. Copy the full browser URL from the address bar.
5. Paste that URL into `cruise_watchlist.url` in `config.yaml`.
6. Set `paid_price` to what you paid (no dollar sign, no commas).

## Running

Run one full check and exit:

```bash
cd /Users/jhartung/Documents/RC_Price_Tracker/rc-price-tracker
python tracker.py --run-once
```

Start the daily scheduler:

```bash
cd /Users/jhartung/Documents/RC_Price_Tracker/rc-price-tracker
python tracker.py
```

Run only one module:

```bash
cd /Users/jhartung/Documents/RC_Price_Tracker/rc-price-tracker
python tracker.py --module cruise --run-once
python tracker.py --module addons --run-once
python tracker.py --module casino --run-once
```

Send a test notification:

```bash
cd /Users/jhartung/Documents/RC_Price_Tracker/rc-price-tracker
python tracker.py --test-notify
```

Open settings UI only:

```bash
cd /Users/jhartung/Documents/RC_Price_Tracker/rc-price-tracker
python tracker.py --settings
```

Run the web app:

```bash
cd /Users/jhartung/Documents/RC_Price_Tracker/rc-price-tracker
python tracker.py --web --host 0.0.0.0 --port 5000
```

Then open:

```text
http://localhost:5000
```

On startup, the web app automatically queues a full run (`cruise + addons + casino`).

Web app with embedded scheduler:

```bash
cd /Users/jhartung/Documents/RC_Price_Tracker/rc-price-tracker
python tracker.py --web --enable-web-scheduler
```

You can also run the web app entrypoint directly:

```bash
cd /Users/jhartung/Documents/RC_Price_Tracker/rc-price-tracker
python webapp.py --host 0.0.0.0 --port 5000
```

Disable startup auto-run (direct webapp entrypoint):

```bash
cd /Users/jhartung/Documents/RC_Price_Tracker/rc-price-tracker
python webapp.py --no-run-on-startup
```

Or with Gunicorn in local/prod style:

```bash
cd /Users/jhartung/Documents/RC_Price_Tracker/rc-price-tracker
gunicorn -w 1 -b 0.0.0.0:8000 webapp:app
```

## Web App UX

The web experience is designed as a high-end control surface with:

- A cruise-first dashboard with currently booked cruises pulled from your account
- Watchlist cruise cards that show matched booked sailings and their tracked add-ons
- Account-linked add-on and casino offer tables so you can see which account each result belongs to
- Browser-based settings editor that writes directly to `config.yaml`
- Run controls for full checks or single module checks
- Recent price checks in dashboard and run-log popup in Settings
- Primary dashboard sections:
  - `Currently Booked Cruises`
  - `Watchlist Cruises + Matched Add-ons`
  - `Recent Add-on Checks`
  - `Recent Casino Offers`

Routes:

- `/` dashboard
- `/settings` configuration editor
- `/api/run-status` live status endpoint
- `/api/run-log` run log data used by settings popup
- `/health` deployment health endpoint

## Deployment

Gunicorn production command:

```bash
cd /Users/jhartung/Documents/RC_Price_Tracker/rc-price-tracker
gunicorn -w 1 -b 0.0.0.0:8000 webapp:app
```

Environment variables:

- `RC_CONFIG_PATH` (default: `config.yaml`)
- `RC_ENABLE_SCHEDULER` (`1` to enable scheduler in web mode)
- `RC_RUN_ON_STARTUP` (`1` by default; set `0` to disable auto-run in `webapp.py`)
- `RC_WEBAPP_SECRET` Flask session secret

Note: if scheduler is enabled in web mode, run a single worker to avoid duplicate scheduled jobs.

Docker deployment:

```bash
docker build -t rc-price-tracker .
docker run --rm -p 8000:8000 -v $(pwd)/config.yaml:/app/config.yaml rc-price-tracker
```

## What to Do When a Price Drop Is Detected

1. Verify the lower price manually on the Royal Caribbean website.
2. Contact your travel agent or Royal Caribbean directly before final payment date.
3. Check updated booking terms before repricing (you may lose OBC).
4. After repricing, update `paid_price` in `config.yaml`.

## Casino Offers and C&A Number

ClubRoyaleOffers.com login uses:

- Last name
- Crown and Anchor number (`cna_number`)

You can find your C&A number in your Royal Caribbean account profile and loyalty section.

## Notifications

This app uses Apprise for notifications. Supported targets include email, Discord, Slack, SMS gateways, ntfy, and more:

- https://github.com/caronc/apprise

## Known Limitations

- Royal Caribbean frontend updates can break cruise page selectors.
- `r0x` and `r0y` checkout params expire and are stripped automatically.
- Add-ons are tied to booked reservations; watchlist cruises without a matching booking cannot show add-ons.
- If a cabin or add-on is no longer available, the tracker logs it as unavailable and skips alerts.
- Passwords containing `%` may fail against RC OAuth; using a different symbol may be necessary.
- ClubRoyaleOffers.com content is JavaScript-rendered and may require selector updates if site layout changes.
- The desktop settings UI (`--settings`) needs a Python build with tkinter support.
