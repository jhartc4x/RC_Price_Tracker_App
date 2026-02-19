# Phase 1 Backend Audit

## Focus
Catalogued all backend data sources, feeds, and persistence contracts that Phase 1 UI features depend on:

### Price tracking
- `modules/cruise_prices.check_cruise_price` scrapes `cruise_watchlist.url` and normalizes each booking/itinerary.
- `price_history` table stores `record_type`, `check_date`, `product_code`, `paid_price`, `current_price`, `currency`, `notified`, plus cruise metadata (ship, label, reservation id).
- UI uses `_fetch_cruise_views` to aggregate this data for dashboards, charts, and watchlist views.

### Login/session
- `modules/auth.login` consumes `grant_type=password` on the RCCL/Celebrity OAuth endpoint.
- Tokens/`account_id` are stored in `auth_context` (session, access_token, brand_code) reused across modules.
- All downstream calls share the same `requests.Session` w/ `Authorization` + `vds-id` headers.

### Estimator feeds
- `/api/sailings` & `/api/cruises` talk to Royal Caribbean GraphQL (`cruiseSearch_Cruises`) for price buckets.
- `/api/addons` fetches catalogs via `aws-prd.api.rccl.com` GraphQL + product detail endpoints.
- Response payloads include cabin prices, vendor details, and diagnostics for front-end estimator usage.

### Drink package
- `modules/addons` maps `CATALOG_CATEGORIES` (beverages=1000000002) and fetches bookings from `profileBookings/enriched/{account_id}` and `commerce-api/.../orderHistory`.
- UI endpoint returns `purchased` and `available` lists with live `current_price`, `savings`, `notified`, and diagnostic metadata.

### Notifications
- APScheduler run defined via `config.schedule` times/timezone; `tracker.run_all_checks` invoked by manual run or scheduler.
- `modules/notify.Notifier` uses Apprise URLs from `config.notifications` and is triggered when thresholds are hit (price changes, casino offers).

### Calendar
- Calendar APIs combine calendar/booking endpoints (`commerce-api/calendar/.../orderHistory`) with DB entries from `insert_booked_cruise` to show reservations + add-ons.
- `price_history` rows link to `reservation_id`, `passenger_name`, `ship_code`, `sail_date` so UI can tie watchlist vs booked views.

## UI-facing endpoints required
- `GET /api/run-status`, `GET /api/run-log`, `POST /run`, `GET /api/ships`, `GET /api/sailings`, `GET /api/addons`, `GET /api/cruises`, `GET /health`, `GET/POST /settings`, `GET /`.
- These endpoints return structured data for price histories, estimator calculations, add-on catalog + purchases, notification settings, and dashboard feeds.

## Data contracts
- `price_history`, `booked_cruises`, `casino_offers`, and `run_log` tables hold state for UI notifications, line graphs, and logging.
- Frontend should expect ISO date strings, normalized currency fields, and `notified` booleans for threshold tracking.

Let me know if you want this extracted into your ticketing system or expanded with sample JSON responses.
