# Phase 1 QA Checklist

## Purpose
Validate the core tracking & visibility deliverables before moving on to Phase 2. Focus areas: notifications, estimator, calendar, login flows, price visuals.

### Audit coverage
- Confirm each key action (price drop, estimator change, calendar sync, login events, price graph refresh) writes to `run_log`/`price_history` with timestamps and statuses.
- Ensure notifications/alerts log the channel, threshold triggered, and which user received it (Apprise delivery review).
- Verify QA user stories cover failure recovery (e.g., API fetch fails, notification endpoint missing).

### IA clarity
- Navigation labels for Dashboard, Cruises, Add-ons, Settings, Health must match the documented topology.
- Each page must clearly describe why the user is there (headings/tooltips for price tracking, estimator results, drink tool, notifications, calendar sync status).
- Progressive disclosure (modals, accordions) should reveal details only when requested; default views stay clean.

### Roadmap alignment
- Check every feature against roadmap commitments:
  - notifications trigger text/email/Apprise per threshold.
  - estimator combos (base fare + add-ons + gratuity + drink packages) calculate totals and deltas.
  - calendar sync is two-way (or clearly marked one-way) with visible status.
  - login includes user profile storage (watchlist, budgets, alerts) and secure hashed credentials.
  - price visuals include sparkline + modal + per-person normalization.

### Validation per area
- **Notifications**: test delivery to configured channel, see entry in UI, check thresholds, ensure failure states are surfaced.
- **Estimator**: verify calculations for sample package breakdowns, check savings vs. paid price, ensure UI copy explains assumptions.
- **Calendar sync**: add/edit events, confirm sync indicators, test conflict resolution and permission handling.
- **Login flows**: register/login/logout, check secure hash storage, MFA or token persistence, session cookies.
- **Price visuals**: review charts (sparkline + modal) for accuracy, legends, drill-down interactions, and filters (cabin, port, add-ons).

## Deliverables
- Export updated run/notification logs to confirm coverage.
- Capture screenshots or logs for each validation scenario.
- Report any mismatches before the design system starts.
