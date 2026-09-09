---
name: researching-purchases
description: Use when researching something to buy online - comparing products, checking price, stock, sizing, specs, compatibility, or delivery dates, especially against a deadline or a specific shipping address. Applies to any retailer, not one particular site.
---

# Researching Purchases

**A product page is a default view, not a fact.** Price, stock, delivery date and spec
table all change with the variant, the destination and the shipping option. Every number
you report is pinned to the exact thing being bought, or it is not reported.

## Required output

One row per candidate. Every cell gets a value. Where you could not establish one, the
cell reads `unverified` — that is a finding to say out loud, not a gap to leave blank.

| Field | What goes in it |
|---|---|
| **Variant / SKU** | the exact ID being bought — the variant, not the listing |
| **Price** | for that SKU |
| **Stock** | for that SKU |
| **Standard delivery** | date + cost, for the user's postcode |
| **Expedited delivery** | date + cost, or `not available` |
| **Rating** | stars **and** review count, both |
| **Requirements** | each requirement the user named, and the source that confirms it |
| **Confidence** | `verified — <source>` or `inferred` |

Then rank on what the user actually asked for, and say plainly when the best-spec option
fails on logistics.

## The four defaults that lie

| Default | What happens | Fix |
|---|---|---|
| **Variant** | The page loads someone else's size; its price, stock, date and spec table are not yours | Resolve the child ID, load *that* page, read it there |
| **Destination** | No address set = wrong country, foreign-export fees, fictional dates | Set the postcode **before** reading any price or date |
| **Shipping** | The headline date is standard; an earlier expedited date sits on the same card | Read both. Never report one as "the" date |
| **Spec table** | Seller-entered, contradicts the manufacturer | Cross-check anything that decides compatibility |

## Source hierarchy

Manufacturer datasheet > independent measurement > retailer spec table > product title >
marketing copy.

**When the retailer's field contradicts the manufacturer, the manufacturer wins.**
Retailer fields are data entry, not engineering. Check the manufacturer whenever a spec
decides **fit or compatibility** — socket, thread, mount, gauge, voltage, size, connector.
Wrong here makes the purchase unusable, not merely suboptimal.

**Measured is not claimed.** A manufacturer's figure and an independent measurement are
different evidence classes. Say which one you have.

## Ratings

Review **count** is evidence strength: 4,4★ from 3.000 beats 4,8★ from 7. A brand name
substitutes for neither. Under 30 reviews is unverified quality — say so, or pick the
alternative with thousands.

If a whole category clusters below ~3,5★, there is generally a physical reason it doesn't
work rather than bad luck (UV traps catch insects that navigate by UV; houseflies in
daylight navigate by food odour, so indoor UV fly traps all rate badly). Stop shopping the
category, spend the budget on what works, and say why.

## Red flags — stop and re-check

- "The page says…" → which variant is selected?
- A delivery date read before the address was set
- Concluding absence from a capped list — dropdowns cap around 10 and sort by popularity.
  Query by ID before declaring something doesn't exist
- A spec that's surprising for the product (a 75 W red decorative bulb, an E27 socket in a
  tiny clamp lamp) → the listing is wrong, not the physics
- Any number that came from a title or ad copy
- A price for one size next to stock for another
- A recommendation carrying no review count

## Tooling

If the page renders price or delivery through JS, if the site returns a bot-check, or if
the destination needs a session cookie, curl cannot do it — drive a real browser and
persist cookies after setting the destination.

- `references/browser-setup.md` — site-agnostic browser pattern
- `references/amazon.md` — Amazon-specific selectors and ASIN handling

## Scope

This skill stops at the recommendation. Once the decision is made and something is being
paid for, use `scripted-booking` instead — it keeps card data out of agent context.
