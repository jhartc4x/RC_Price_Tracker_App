# Dashboard Layout Plan — iPad First

## Context & Constraints
- **Target device:** 11" & 12.9" iPads in portrait (834px–1024px width). Layout must render comfortably in the narrower portrait width before enhancing for larger breakpoints.
- **Grid:** 12-column grid with 24px gutters and 16px side padding on portrait. Each card spans at least 6 columns to keep tap targets large, stacking vertically on the smallest iPad mini-width.
- **Interaction:** Touch targets should be >44px, typography tuned for readability at arm's length, and scroll behaviour should be natural (vertical scroll for the whole screen; individual sections can horizontally swipe small charts if needed).

## Layout Map
### 1. KPI Strip (top)
- **Purpose:** immediate sense of health. 
- **Content:** three Metric Cards showing `Net Revenue (MTD)`, `Active Ops vs Target`, and `Available Team Capacity`. Each uses a compact sparkline, numeric value, delta indicator, label, and contextual help icon.
- **Placement:** full-width row with cards spanning 4 columns each. On portrait, cards wrap into a single row with horizontal scroll if space shrinks.

### 2. Graph Row
- **Left (spans 7 columns):** `Engagement Trend` area/line hybrid showing summaries for the past 14 days with toggle for “Days”, “Weeks”, “Projects”. Includes axis labels, a legend, and a contextual note.
- **Right (spans 5 columns):** `Traffic Source Breakdown` stacked bar chart (or layered columns) showing activity contribution by channel (auto, manual, referral). Embedded legend uses chips.
- **Notes:** Charts should be full-bleed inside cards with subtle separators. On portrait, graphs stack (Engagement first, then Source). Future breakpoints can sit side-by-side.

### 3. Table Row
- **Primary Table (full width at 12 columns; on wider screens left 8/right 4):** `Operational Table` listing `Project`, `Owner`, `Status`, `Latest Metric`, `Next Milestone`. Enable inline sorting for Status and Metric.
- **Secondary Table (below or to the right depending on width):** `Effort Log` (Date, Activity, Drink Tool usage, Notes). Designed with alternating row shading and a compact action menu for each row (ellipsis button, accessible via touch).

### 4. Estimator + Drink Tool + Utility Widgets
- **Estimator (left column under tables):** interactive card with inputs (Project select, Timeline slider, Risk toggle) and output summary (forecast + confidence). Provides CTA to open detailed estimator view.
- **Drink Tool (adjacent or stacked):** smaller card focusing on hydration/refresh reminders; toggles between `Tea`, `Coffee`, `Water`, displays upcoming breaks or prompts, quick action button `Order Drink`.
- **Notifications & Calendar (right column or repeating section):** 
  - *Notifications:* a scrollable feed showing the latest five alerts (e.g., approvals needed, threshold breaches). Each item includes icon/color-coded severity and timestamp.
  - *Calendar:* compact agenda view showing next 3 events, with mini month selector and `Schedule` button. Includes indicator chips for busy/free periods.
- On portrait iPad, Estimator sits above Drink Tool, and Notifications sits above Calendar to maintain vertical rhythm. On wider view, use 6+6 columns (Estimator/Drink left, Notifications/Calendar right).

## Component Inventory Notes (for styling)
1. **MetricCard** — card with gradient accent, large numeric type (32px), subtle drop shadow, delta chip (green/red). Use `Inter` 500 for numbers, 400 for labels. Provide `aria-live` updates when values change.
2. **GraphCard** — full-bleed chart container with padded header. Background `#0F172A`, neon borders? Keep accessible contrast; use custom `AxisLabel` component (size 12px). Provide `ChartLegend` chips with color-coded pulses.
3. **OperationalTable** — uses `TableRow` with flexible columns, responsive stacking (label+value when narrow). `StatusBadge` uses 12px uppercase, background tinted by status.
4. **EffortLogTable** — accessible table with `aria-describedby`. Add `ActionMenu` (dots) for gestures. Even rows `#f7f8fb`, odd `#ffffff`.
5. **EstimatorCard** — form fields (select, slider, accessible toggles). Buttons `Primary` (solid) / `Secondary` (ghost). Provide `ResultSummary` callout with `confidence` pill.
6. **DrinkToolCard** — chip-based toggles, micro animation on selection, `CTA` button `Order Refreshment`. Use `icons/drink.svg`.
7. **NotificationsFeed** — vertical list with `SeverityDot`. Each item has `title`, `body`, `timestamp`, optional action button. Keep `overflow-y: auto` with visible scrollbar only when necessary.
8. **CalendarWidget** — mini calendar grid (week view) atop list of agenda items. Use `chip` to highlight selected day; `Schedule` button `full-width`. Provide optional integration indicator (e.g., Teams, Calendar API) as pill.

## Notes for Styling Later
- Work with a `surface` palette (navy backgrounds with chrome accent). Keep text contrast to WCAG AA on dark surfaces.
- Maintain `spacing scale`: 16px base, 24px gutters, 32px for sections, 12px for micro components. Use `border-radius: 16px` for cards.
- Provide `focus` outlines for interactive cards (Estimator inputs, table rows). Use consistent drop shadows `0 10px 30px rgba(15, 23, 42, 0.25)`.
- Build `tokens` for metric statuses (success/neutral/warning/critical).
- Plan to reuse `CardHeaderWithActions` and `SubtleDivider` components to ensure visual rhythm.
