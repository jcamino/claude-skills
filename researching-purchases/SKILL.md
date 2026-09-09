---
name: researching-purchases
description: Use when researching something to buy online - comparing products, checking price, stock, sizing, specs, compatibility, or delivery dates, especially against a deadline or a specific shipping address.
---

# Researching Purchases

## Overview

**A product page is a default view, not a fact.** Price, stock, delivery date and spec table all change with the variant, the destination, and the shipping option. Every number you report must be pinned to the exact thing being bought.

Reporting a page's default state as if it were the user's purchase is the single most common way this work goes wrong.

## The Four Defaults That Lie

| Default | What happens | Fix |
|---|---|---|
| **Variant** | Page loads size 40 / a different style; its spec table, price, stock and date are not yours | Resolve the child ID for the exact variant, load *that* page, read it there |
| **Destination** | No address set = wrong country. Foreign-export shipping fees and dates, all fiction | Set the delivery postcode **before** reading any price or date |
| **Shipping option** | The headline date is standard shipping; a much earlier expedited date sits on the same card | Read standard **and** expedited. Never report one as "the" date |
| **Spec table** | Seller-entered, frequently wrong, contradicts the manufacturer | Cross-check anything that decides compatibility |

## Source Hierarchy for Specs

Manufacturer datasheet > independent lab measurement > retailer spec table > product title > marketing bullets.

**When the retailer's structured field contradicts the manufacturer, the manufacturer wins.** Retailer fields are data entry, not engineering.

Verify against the manufacturer whenever a spec decides **compatibility or fit**: socket, thread, mount, gauge, voltage, size, connector. Getting this wrong makes the purchase unusable, not just suboptimal.

## Hard Rules

- Never quote price, stock or delivery without knowing **which variant** it belongs to
- Set the destination first; a date without a postcode is meaningless
- Check both standard and expedited shipping
- Never conclude "doesn't exist" from a **truncated list** — dropdowns and autocompletes cap results and hide small entries. Query by ID or a narrower term before declaring absence
- Distinguish **measured** from **claimed**. Marketing numbers and independently measured numbers are different evidence classes; say which you have
- State explicitly what is verified vs inferred. An honest "unverified" beats a confident wrong number
- **Never recommend an item without its rating AND review count.** Capture both in the first sweep, not as an afterthought. No reviews or a tiny sample (<30) = unverified quality — say so or pick the alternative with thousands of reviews
- Review **count** is evidence strength: 4,4★ from 3,000 beats 4,5★ from 30. A brand name is not a substitute for either
- **The user's stated requirements are specs too.** For the recommended item, state how each core requirement is verified — a title or category page is a claim, not verification. "Requirement unverified" must be said out loud, never skipped

## When a Whole Category Rates Badly

If every product in a category clusters below ~3,5★, the category is usually wrong for the job, not unlucky — there's often a physical reason (e.g. UV traps target insects that navigate by UV; houseflies in daylight navigate by food odour, so every indoor UV fly trap rates poorly). Stop shopping the category, spend the budget on what works, and say why.

## Red Flags — Stop and Re-Check

- "The page says…" → which variant is selected?
- Reporting a delivery date you read before setting an address
- A spec that seems surprising for the product (a 75W red decorative bulb; an E27 socket in a tiny clamp lamp) → the listing is probably wrong, not the physics
- Concluding absence from a capped list
- Any number that came from a title or ad copy
- Quoting a price for one size and stock for another

## Tooling

curl is usually insufficient: bot-checks return 503, price/delivery blocks are JS-rendered, and you cannot set a delivery location without a session. Use a real headless browser and persist cookies after setting the destination.

See `browser-recipe.md` for the concrete pattern.

## Deliverable Format

For each candidate report: **exact variant ID**, price *for that variant*, stock, standard delivery, expedited delivery, and a verified/inferred marker. Rank on what the user actually asked for, and say plainly when the best-spec option fails on logistics.

## Common Mistakes

| Mistake | Reality |
|---|---|
| "The spec table is structured data, it's reliable" | It's seller-entered. It has been flatly wrong about socket type, sole material and voltage. |
| "I checked the product page" | You checked *a* product page. Variants are separate pages. |
| "Nothing arrives in time" | You read standard shipping only. Check expedited before declaring failure. |
| "It's not in the dropdown, so it doesn't exist" | Dropdowns cap at ~10 and sort by popularity. Query by ID. |
| "The brand says 10mm drop" | That's a claim. An independent measurement is a different thing. Label it. |
| "Same listing, so same price" | Price, stock and delivery vary **per size**. |
| "It's a known brand, it'll be fine" | A known brand's model had zero reviews and its sibling rated 3,7★. Check every item. |
| "4,5★, done" | From how many reviews? 30 reviews can be one seller's friends. |
