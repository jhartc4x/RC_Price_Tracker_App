# UI Prompt Playbook (Bruce)

## What worked in community discussions (Reddit pattern synthesis)
1. **Use visual references explicitly** (brand sites + 2-3 app inspirations).
2. **Constrain style + density hard** ("quiet", "not noisy", "max 3 visual weights").
3. **Force architecture first, then implementation** (IA/wireframe pass before code).
4. **Require component inventory + design tokens** before touching pages.
5. **Use progressive disclosure** (modals/drawers/detail views) to reduce clutter.
6. **Set acceptance tests for visuals** (spacing, contrast, hierarchy, consistency).
7. **Iterate page-by-page with screenshots + critique loop**, not one-shot full build.

## Master prompt template (for this app)

You are a senior product designer + frontend engineer.

Goal:
Redesign this app into a premium, calm, iPhone-quality experience.
It must feel intentional and minimal — NOT noisy, NOT "vibe coded".

Brand + reference inputs:
- Product domain: Royal Caribbean pricing tracker.
- Visual cues: Royal Caribbean brand energy (blue gradients), Apple HIG clarity, Google Material clarity, modern app card rhythm.
- Keep trustful utility tone (finance/monitoring), not playful gimmicks.

Hard constraints:
- Mobile-first at 390-430px width, scales cleanly to desktop.
- Max 2 accent gradients per page.
- Max 3 text emphasis levels per screen.
- Strong spacing system (4/8/12/16/24).
- Keep cognitive load low: one primary action per section.
- Use progressive disclosure for heavy data (modal/sheet/drawer), never dump all data at once.

Process (must follow in order):
1) Information architecture proposal per page (Dashboard, Cruises, Add-ons, Settings).
2) Component inventory (cards, lists, tables, filters, buttons, modals, empty states).
3) Design token proposal (color, type scale, radius, shadow, spacing).
4) Low-fidelity layout map (what appears first/second/hidden).
5) Implement page-by-page (Dashboard first), with screenshot after each page.
6) Run visual QA checklist and fix issues.

Dashboard requirements:
- Top summary with run status and one clear CTA.
- "What needs attention" list first.
- Opportunity table second (short list, sorted by value).
- Recent offers condensed list with "View all" modal.
- Remove repetitive card noise.

Cruises requirements:
- Filters in compact panel.
- Result cards with 4 cabin prices and one key delta.
- Detail modal for itinerary/ports instead of long card bodies.

Add-ons requirements:
- Summary strip first (counts + savings + source).
- Tabs for Purchased/Available.
- Diagnostics hidden behind expandable panel.

Settings requirements:
- Step-like sections or tabbed sections.
- Sticky save action.
- Inline field hints for risky inputs.

Output requirements:
- Provide changed files only.
- Keep code clean and consistent with existing stack (Flask/Jinja + CSS + vanilla JS).
- Do not break existing endpoints or form field names.
- End with: "Visual QA report" listing what changed and why it improves UX.

## Quick critique prompt (between iterations)

Critique this UI like a strict product design lead.
Return only:
1) Top 5 problems hurting premium feel
2) Top 5 problems hurting usability
3) Exact CSS/markup fixes
4) Priority order for next pass

Reject vague advice. Be specific with spacing, hierarchy, contrast, and information density.
