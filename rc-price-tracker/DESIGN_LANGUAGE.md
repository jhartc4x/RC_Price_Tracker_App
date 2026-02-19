# RC Price Tracker — Design Language v1

## Reference products reviewed
- Linear
- Notion
- Stripe
- Atlassian Jira

## Positioning
A premium operations console for cruise pricing intelligence.

## Core principles
1. **Calm hierarchy** — one dominant action per section.
2. **Readable density** — compact data, generous spacing.
3. **State clarity** — status, freshness, and errors are obvious at a glance.
4. **Progressive disclosure** — hide complexity behind expanders/details.
5. **Consistent navigation** — same top-level IA on every screen.

## Navigation language
- Top-level: Dashboard, Cruises, Add-ons, Settings, Health.
- Keep labels as nouns (not verbs).
- Active route always highlighted.

## Visual system
- Surface-first UI: soft canvas + elevated white cards.
- Rounded corners (14–20px) and subtle shadows.
- Minimal accent usage (blue for action, green for positive deltas, red for risk/errors).
- Typographic scale: strong title, quiet metadata.

## Component patterns
- **Hero**: summary + primary CTA + status card.
- **Metric cards**: 4-up quick scan row.
- **Data cards**: ship/watchlist entities with key facts.
- **Tables**: muted headers, hover affordance, no heavy borders.
- **Status pills**: success/warn/error visual consistency.

## Interaction standards
- Primary button = gradient blue, secondary = bordered neutral.
- Polling states should update in place; no full-screen interruptions.
- Empty states provide exactly one next step.

## Content tone
- Short, practical, confidence-inspiring.
- Avoid technical clutter in primary views.
- Put diagnostics behind expandable sections.

## Next-phase UI targets
1. Redesign Settings into guided sections (Accounts, Watchlist, Notifications, Automation).
2. Add sticky table headers + client-side sort/search where useful.
3. Add "Last successful run" and "Data freshness" badges globally.
4. Add compact chart sparkline blocks for trend visibility.
