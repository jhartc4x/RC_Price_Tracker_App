# Phase 1 Design Guardrails

## Overview

The Phase 1 guiding principles (as currently framed) are distilled into interaction notes and page-level guardrails to keep the experience premium. Where the source principles are still being finalized, this document serves as the working translation for the Phase1 checklist. When more detail becomes available, these notes can be refined further.

## Guiding Principles → Interaction Notes

1. **Clarity-first storytelling**
   - Use concise hero copy and generous spacing so every first touch feels obvious. Each interaction step (choose, confirm, progress) is surfaced with labels and progress indicators that leave no mystery about what a person should do next.
   - Microcopy highlights the value of the action (e.g., “Reveal insights” instead of generic verbs) and links to contextual tooltips so people understand implications before they commit.

2. **Premium tactile rhythm**
   - Honor overhead with layered surfaces that respond to hover/focus with subtle depth changes (shadow + blur) rather than loud motion; this keeps the experience feeling crafted rather than flashy.
   - Animate transitions between states (card expand, drawer open) with eased pacing to reinforce a sense of calm momentum.

3. **Purposeful density**
   - Every screen limits cards or modules to the essentials—no more than 3 digest cards in a row and maximum 6 actionable tiles per viewport—so attention is focused and the layout stays airy.
   - Explicit spacing (“resting gutters”) ensures interactive elements never feel cramped even on smaller breakpoints.

4. **Human-centered progression**
   - Journey cues (breadcrumbs, timeline chips) align with the user’s mental model: when they complete an action, the next step is visually emphasized and the prior step subtly fades.
   - Error or validation messages appear inline and use reassuring language that keeps people in control.

## Page-Level Constraints

| Page | Gradients | Typography | Card Density |
| --- | --- | --- | --- |
| **Arrival / Landing** | Soft radial gradient (teal → deep indigo) anchored behind the hero illustration; gradients are limited to this hero backdrop so the rest of the screen stays calm. | Display type is 48/60pt serif (Playfair-like) for the hero line, with a 18/28pt sans subhead and 16/24pt body. | Single spotlight card (“What’s new” or CTA) below the fold; secondary cards hidden until scroll. Keep only 1 high-impact card per viewport to maintain breathable hero.
| **Workspace / Dashboard** | Subtle linear gradient (faint charcoal fade) on the page background, while each card uses a monochrome surface with a thin gradient stripe along the top edge to signal interactivity. | Headings use 28/34pt semi-bold sans, subheadings 20/26pt, body copy 16/22pt. Use a consistent cap-height scale to keep columns aligned. | Max 3 cards per row (desktop) and 2 per row on tablet; avoid stacking >4 cards vertically without a pause section (split by a “Highlights” panel) to prevent density creep.
| **Detail / Workflow** | Gradients are minimal—only present in accent borders or status pills (e.g., soft gradient on a progress tag) so the focus remains on the task content. | Titles use 32/38pt medium, field labels 14/20pt, action copy 16/20pt bold. Reserve italics for emphasis only to keep the text plane refined. | Layout is predominantly single-column (1 main card + 1 supporting card). If micro cards exist (checklist items), keep them to a row of 2 maximum and leave 24px between each.
| **Settings / Preferences** | Gradient use restricted to the hero band or mood-setting background; form surfaces stay solid. | Use 20/24pt bold headings, 14/18pt body, and 12/16pt caption to differentiate helper text. | Group controls into sections, each with no more than 5 toggles or fields; cards should span full width with generous padding so they breathe.

## Inspiration References for a Premium Feel

- **Apple product pages** — restrained typography scale, crisp spacing, and gradients that feel purposeful rather than decorative.
- **Tesla app/dashboard** — calm, monochrome surfaces with selective color highlights; nothing overly dense and transitions feel weighty.
- **Superhuman onboarding** — every interaction has a clear goal, microcopy feels human, and the experience leans into whitespace.
- **Notion + Linear** — card density stays intentional, gradient use is minimal, and typography prioritizes hierarchy.

These references guide how the gradients, type, and density combine so Phase 1 feels elevated without sacrificing utility.
