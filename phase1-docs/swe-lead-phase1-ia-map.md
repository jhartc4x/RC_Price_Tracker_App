# RC Price Tracker Phase 1 Information Architecture

## iPad-First Guiding Principles
- **Layout priority**: Design for a single strong column/framing that works on 12.9" iPad Pro in landscape and portrait; use edge-to-edge cards with 20–24pt touch targets.
- **Interactions**: Favor tap-friendly controls, drag-and-drop for line reordering, and swipe-to-action patterns that respect iPad gestures.
- **Immersive chrome**: Keep navigation minimal (tab bar or split view) and reserve top bar for context (search, filters) while leaving breathing room for content.
- **Responsive enhancements**: Use adaptive grids to add secondary columns only if screen width exceeds 1000px; everything should still feel equally native on portrait orientation.

## Page Documentation

### Dashboard
- **Primary goal**: Surface the health of tracked cruises so planners instantly know where pricing is moving and when action is required.
- **Top 3 user actions**:
  1. Scan the price movement heatmap for tracked cruise lines.
  2. Tap into a high-priority cruise to view detailed pricing history and alerts.
  3. Bookmark or promote a cruise for follow-up (add to attention list or share with team).
- **Must-see content**:
  - Price change summary cards (up/down, % delta, trigger reason).
  - Active alerts list (e.g., price drop, status change) with one-tap snooze.
  - Quick filters/toggles (e.g., `Hot Now`, `By Date`, `By Ship`).
- **Optional content**:
  - Mini calendar of upcoming sailing windows.
  - Tips or GPT-driven insights (“Why this drop matters”).
  - Team notes / pinned chats referencing a cruise.

### Cruises
- **Primary goal**: Let users explore and compare cruise itineraries and pricing lines to identify the best timing and package.
- **Top 3 user actions**:
  1. Select a cruise line/itinerary to inspect detailed price tracking data.
  2. Compare pricing across cabin categories (interior to suite).
  3. Add cruise to a tracking line or schedule a notification.
- **Must-see content**:
  - List/grid of tracked cruises with summary price, trend icon, and sail date.
  - Price tracking timeline graph with selectable date ranges.
  - Cabin-level details (current price, historical low, average delta).
- **Optional content**:
  - Benchmarks vs. competitors or historical season.
  - Onboard credit promotions or limited-time offers.
  - `Add to calendar` / `Share itinerary` actions.

### Add-ons
- **Primary goal**: Manage ancillary products (drinks, excursions, Wi‑Fi) tied to a cruise and optimize bundling decisions.
- **Top 3 user actions**:
  1. Assess bundled vs à la carte pricing for enhancements (e.g., drink package tiers).
  2. Toggle auto-apply recommendations per cruise.
  3. Update traveler preferences that drive estimator modeling.
- **Must-see content**:
  - Popular add-on packages with price, inclusions, and savings.
  - Estimator widget showing total trip spend with vs without each add-on.
  - Status of already booked add-ons (linked to encouragements to upgrade).
- **Optional content**:
  - Vendor/partner callouts (Wi-Fi provider, beverage partner).
  - Notes explaining how add-ons impact loyalty or credits.
  - Forecasted price change warnings for add-ons.

### Settings
- **Primary goal**: Configure account (login, notifications, calendar links) and personalized preferences for the tracker.
- **Top 3 user actions**:
  1. Manage login/auth (SSO, MFA) and security keys.
  2. Configure default notification channels and thresholds.
  3. Sync or disconnect external calendars (e.g., iCloud, Google Calendar).
- **Must-see content**:
  - Login / identity panel with provider, last sign-in, device list.
  - Notification controls (push, email, Slack, thresholds for price movements).
  - Calendar integration toggles with sync status.
- **Optional content**:
  - App/theme preferences (light/dark, density).
  - Team sharing permissions and role assignments.
  - Export/backups of tracking lines.

### Health
- **Primary goal**: Communicate system health of price feeds and tools so planners trust the data.
- **Top 3 user actions**:
  1. Check the latest status of price tracking feeds (live/stale).
  2. Investigate a failed sync or feed lag.
  3. Submit or view support tickets for data anomalies.
- **Must-see content**:
  - Feed status tiles (price line ingestion, estimator calculations, add-on data updates).
  - Health history sparkline or incidents timeline.
  - Automated recommendations when a feed is delayed (e.g., `Retry now`).
- **Optional content**:
  - In-app changelog (recent releases/bug fixes).
  - Deep link to backend logs or diagnostics.
  - Usage quotas (API calls, calendar syncs).

## Data Requirements

### Price Tracking Lines
- Cruise identifier (line ID, itinerary ID, ship name).
- Cabin categories (distribution, deck, name).
- Current price, historical low/high, price change %.
- Trigger metadata (e.g., promo code, onboard credit, shift reason).
- Subscription status (active/paused) and alerts shared teams.
- Refresh cadence and timestamp of latest poll.
- Linked add-ons and estimations that feed into package totals.

### Login
- Unique user ID, email, role, and authentication provider (SSO/MFA).
- Device fingerprint list and session status.
- MFA factors (phone/email) plus last verification time.
- Permission scopes (read/write on cruises, admin privileges).
- Audit trail for recent logins and password changes.

### Estimator
- Selected cruise line + sail date + cabin category.
- Traveler count (adults/kids) and loyalty tier.
- Base fare + buy-up options (cabin upgrades, insurance, add-ons).
- Tax/fee breakdown per jurisdiction.
- Date of last sync with cruise vendor.
- Confidence score or variance range (for iPad first UI callouts).

### Drink-Package Tool
- Available package tiers (Premium, Classic, Basic) per cruise line.
- Price per passenger/day and included beverage counts.
- Current booking status per traveler (opted in/out, auto-renewal).
- Package change deadlines and penalties.
- Associated loyalty perks or onboard credits.
- Forecasted savings over à la carte spend.

### Notifications
- Alert type (price drop/rise, estimator change, feed health, calendar item).
- Channel preferences (push, email, SMS, Slack, Teams).
- Threshold configuration (percentage change, absolute delta, velocity).
- Delivery windows (Do Not Disturb handling, timezone-aware).
- Escalation path (who else is notified, follow-up reminders).
- Event metadata linking back to cruise line/cabin.

### Calendar
- Integration token/status (iCal URL, Google token, Apple account).
- Event schema (title, start/end, location, tags e.g., `Price Watch`).
- Sync direction (one-way import/export) and last sync timestamp.
- Recurrence rules (e.g., weekly check-ins) and reminders.
- Conflict resolution policy (overwrite or merge).
- Visibility controls (shared with team or private).

## Summary for the Team
- **Frontend**: Prioritize an iPad-first, single-column layout with responsive enhancement; key actions live on dashboard and cruise list cards with tap-to-expand flows.
- **Backend**: Deliver reliable, timestamped price feeds, estimator math, and drink-package data plus notification pipelines; health telemetry must feed real-time tiles.
- **Design**: Focus on spacious, touch-friendly cards, consistent color cues for price direction, and accessible typography for 12.9" iPad landscapes.
- **QA**: Validate price line refresh cadence, estimator outputs, notification thresholds, and calendar syncs under iPad Safari/Chrome scenarios.

Document this IA map to align the next sprint; feel free to extend details (wireframes, API contracts) once Phase 1 architecture is approved.
