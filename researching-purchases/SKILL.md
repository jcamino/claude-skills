---
name: researching-purchases
description: Use when researching something to buy online - comparing products, checking price, stock, sizing, specs, compatibility, or delivery dates, especially against a deadline or a specific shipping address. Applies to any retailer, not one particular site.
---

# Researching Purchases

**A product page is a default view, not a fact.** Price, stock, delivery date and spec
table all change with the variant, the destination and the shipping option. Every number
you report is pinned to the exact thing being bought, or it is not reported.

## Required output

**Your answer contains this table.** Copy the skeleton and fill it — one column per
candidate, including the ones you are rejecting.

| | Candidate A | Candidate B |
|---|---|---|
| **Link** | | |
| **Variant / SKU** | | |
| **Price** | | |
| **Stock** | | |
| **Standard delivery** | | |
| **Expedited delivery** | | |
| **Rating** | | |
| **Requirements** | | |
| **Confidence** | | |

Every cell gets a value. A cell you could not establish reads `unverified` — that is a
finding to report, not a gap to leave blank.

- **Link** — the full URL of that SKU's own page, written out raw
  (`https://www.amazon.com/dp/B0FD1TT96X`) so it is clickable as-is: the variant's page,
  not a search result or the parent listing
- **Variant / SKU** — the exact ID being bought: the variant, not the listing
- **Price**, **Stock** — for that SKU, not for the listing it sits under
- **Standard / Expedited delivery** — date **and** cost for the user's postcode, or
  `not available`
- **Rating** — stars **and** review count, both. A listing-level rating is shared across
  every variant under it, so when the number does not belong to the SKU in the column,
  write that in the cell
- **Requirements** — each requirement the user named, and the source that confirms it
- **Confidence** — `verified — <source>` or `inferred`

Prose around the table is fine. Prose instead of the table is not.

Then rank on what the user actually asked for, and say plainly when the best-spec option
fails on logistics.

**Your first line is the pick and its link**: name, price, raw URL. The user should be able
to click and buy without reading past it. Every alternative you name in prose carries its
URL too.

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
- An ASIN, part number or SKU with no URL beside it

## Tooling

If the page renders price or delivery through JS, or the destination needs a session
cookie, curl cannot do it — drive a real browser and persist cookies after setting the
destination.

A **bot-check alone is not a reason to open a browser.** It is usually the TLS
fingerprint. Retry with `curl_cffi` first — `requests.get(url, impersonate="chrome")` —
which turns iHerb search from `403` into a 2.6 MB page in 0.8 s, and does the same for
Akamai-fronted retail. Falls down on two things: a Cloudflare managed challenge, and
shields that answer with a success status and an empty body (Booking.com: `202`, 3.9 KB),
so check body length, not just the status. Measurements: `~/Code/CURL.md`.

- `references/browser-setup.md` — site-agnostic browser pattern
- `references/amazon.md` — Amazon-specific selectors and ASIN handling

## Scope

This skill stops at the recommendation. Once the decision is made and something is being
paid for, use `scripted-booking` instead — it keeps card data out of agent context.
