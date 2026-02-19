# Drink Package Pricing Research

## Core package tiers (Royal Caribbean + Celebrity references)
1. **Classic** – Royal Caribbean’s base package, with house beer, wine, and entry-level spirits. Keeps pour limits moderate and focuses on familiar favorites.
2. **Deluxe** – Adds premium cocktails, frozen drinks, and elevated mocktails, making it the go-to for casual mixology without top-shelf pours.
3. **Premium** – Unlimited top-shelf cocktails, sparkling wine, and specialty pours that elevate the in-cabin experience.
4. **Ultimate** – Craft cocktails, champagne, and upscale energy shots/specialty beverages for guests who drink frequently and want the rare releases.
## Average drink estimates used in the tool
| Drink bucket | Avg price used | Rationale |
|--------------|----------------|-----------|
| Beer & Wine | $10 | Combines domestic beer pours and wine by the glass (common ballpark). |
| Mixed & Cocktails | $14 | Mixing classic and premium cocktails, which often appear in deluxe plans. |
| Coffee & Soda | $4 | Mocktails, coffee, and fountain soda averages from popular lounges. |
| Energy & Specialty | $6 | Includes smoothies, energy shots, and non-alcoholic tonics. |
| Premium Spirits | $18 | Reflects top-shelf pours/shot experiences featured in Premium/Ultimate packages. |

## How the tool maps to packages
- Uses per-drink counts + averages to calculate a `cost_per_day` figure over a 7-day sailing.
- Recommends the cheapest package tier whose daily threshold aligns with the planned spend (breakeven is modeled as #drinks × avg price per day).
- Encourages upsell by surfacing the gap between actual plans and a higher tier.

Feel free to save this doc in the repo for future tuning; we can always replace the averages with live data from menu APIs when available.