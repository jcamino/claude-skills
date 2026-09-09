---
name: hotel-room-search
description: Use when searching for a hotel, ryokan or apartment against room-level constraints - bed configuration (twin vs double), free-cancellation deadlines, thin holiday availability, or a specific walkable neighbourhood. Complements travel-hacker:compare-hotels, which is property-level only.
---

# Hotel Room Search

## Overview

**A search result is a property. A booking is a room.** Bed configuration, the rate you will actually pay, and the free-cancellation deadline exist only at room level — and *no* metasearch API returns them.

Every hotel API in reach (Trivago, LiteAPI, SerpAPI, MoodTrip, Skiplagged) returns one price per hotel: the cheapest room that sleeps your party. That room is usually a non-refundable double. If the user asked for twins, or for cancellable, the API answer is not an answer — it is a shortlist.

Treating a property-level price as if it were the user's booking is the single most common way this work goes wrong.

## The Five Defaults That Lie

| Default | What happens | Fix |
|---|---|---|
| **Search-card price** | It is the cheapest rate on the property — typically non-refundable, often a double, sometimes a bunk or dorm | Open the room table. Quote a price only with the room it belongs to |
| **Occupancy ≠ bed layout** | "2 adults" matches a double, a twin, a sofa-bed and a bunk equally. `sleeps: 2` says nothing about beds | Match on the **bed string**, never on occupancy |
| **"Free cancellation" badge** | A property-level badge means *some* rate is cancellable — usually the dearest one. The rate you priced may not be | Read the deadline on the **rate row**, per row |
| **Radius / city search** | A 1.2 km radius anchored on Cat Street returned Kimpton Shinjuku, 6 km away. Radius params are advisory | Filter by lat/lon yourself and print the real distance |
| **Signed-out prices** | Genius / member rates and some inventory only appear logged in | Drive the signed-in browser, or say the price is public-rate |

## Source Ladder

Property-level first to build a shortlist; room-level to answer the question. Never skip the second half.

| Tier | Source | Gives | Status |
|---|---|---|---|
| 1. Shortlist | `trivago` MCP, SerpAPI `google_hotels` | name, lat/lon, nightly + total rate, rating, **check-in / check-out times** | property-level only. Verified 2026-08-29: SerpAPI returned 20 properties with no bed and no cancellation field anywhere in the record. Free tier is **250 searches/month** - meter it like Ignav |
| 2. Room-level API | **LiteAPI** `post_hotels_rates` | room types, per-rate `cancellationPolicies` with a **structured `cancelTime` timestamp + `refundableTag`**, board type | **make this call first.** Best cancellation data of any source - a real timestamp, not prose to regex. Use `refundableRatesOnly` and `maxRatesPerHotel`; do **not** use `bedTypes` (see below) |
| 3. Room-level API | **DIDA MCP** `getHotelDetail` | bed type, per-room price, free-cancel deadline timestamp | free `mcp_` key, wholesale inventory (differs from Booking's) |
| 4. Booking inventory | `booking_rooms.py` (this skill) via signed-in Chrome + CDP | full `#hprt-table`: bed, rate, conditions, scarcity | the inventory the user actually books from, at signed-in prices |
| 5. Keyless fallback | `hotelzero` npm MCP (`get_hotel_details`) | `bedType`, `cancellation`, `sleeps`, `breakfast` | own Playwright chromium, signed-out, ~25 results, CAPTCHA-prone |
| Japan | Rakuten Travel `VacantHotelSearch` | plan-level rates for JP domestic inventory | free Rakuten App ID |

**LiteAPI's `bedTypes` filter is broken - never use it.** Tested 2026-08-29 on a `sand_` key:
`bedTypes:["twin"]` and `bedTypes:["double"]` each returned **zero hotels**, while the same
unfiltered query returned 75 rates including 28 with "Twin" in the room name. It fails *silently* -
an empty result, not an error - so it reads exactly like "no twin rooms available" when there are
dozens. Pull rates unfiltered and match bed configuration yourself with `parse_beds()` from
`scripts/booking_rooms.py`, which is also the only thing that separates `1 twin bed` (a single) from
`2 twin beds`. `refundableRatesOnly` was verified working (75 rates -> 41, all `RFN`).
Re-test `bedTypes` if a production key is ever issued; this was observed on sandbox.

**Do not write a Booking.com room scraper.** Tier 4 exists in `scripts/`; tier 5 exists on npm. Both already return the schema below.

**Rejected after testing (2026-08-29):** MoodTrip MCP — returned 3 APA business hotels for all of Tokyo with `availableRooms: null`, while self-reporting `"complete": true, "authoritative": true`. A source that asserts completeness on a 3-result city search is worse than no source.

## Normalised Room Schema

Every tier normalises to this. It is `hotelzero`'s `RoomOption` plus a parsed deadline:

```
name, bedType, price, priceDisplay, sleeps, features[],
cancellation, cancelDeadline, refundable, breakfast, roomsLeft
```

`bedType` is reported **verbatim**. "2 single beds" and "1 double bed" are different products; do not collapse either into "twin/double".

## Hard Rules

- **Room-level or it didn't happen.** No bed or cancellation claim may come from a property-level source
- Every "cancellable" claim carries a **date, a time, and a timezone**. "Free cancellation" alone is not a finding
- Report the bed string verbatim alongside your interpretation, **and name the source it came from** ("Booking bed cell", "LiteAPI room name", "host listing text"). A bed claim with no source is the mistake that put a single twin in a two-bed list in Tokyo and an unattributed "2 full beds" at the top of the Kyoto list
- **Corroborate the bed on anything you rank in the top three** against the property's own site or a second inventory source. One retailer field is data entry, not a fact — if the two disagree, say so and rank on the worse reading
- **Extraction code lives in a file on disk, never typed into the page inline.** If you find yourself writing an extractor a second time, you have already lost — the one in `scripts/` is the extractor
- **Never hold scraping state in `window.__*`.** A navigation wipes it. Results accumulate in a file
- On a holiday week, name the holiday, expect thin inventory, and capture the scarcity string ("Only 2 left") — it is a real signal, not decoration
- Distinguish **available** from **available in the configuration asked for**. A hotel with only doubles left is a rejection, and the reason must be stated
- State check-in and check-out times when the arrival is late or the departure early. A 15:00 check-in fails a 22:00 arrival only if the desk closes; a ryokan with a 21:00 door and set dinner genuinely fails it

## Red Flags — Stop and Re-Check

- You are about to write extraction JS inline → use `scripts/booking_rooms.py`
- `window.__x is not a function`, or your cache is gone → state died on navigation; that is the design being wrong, not a hiccup
- A single `Runtime.evaluate` running >45 s → you put sleeps inside the evaluate. Loop outside it, one page per call
- A source reports `complete: true` with a handful of results for a large city
- Quoting a nightly rate without naming the room
- "Free cancellation" with no deadline attached
- A radius search returning a property in a different ward → the radius did not apply
- A walk time computed from a coordinate **you typed from memory** → it is a guess wearing a number. Ayanishiki Gion was reported at 5 min to Gion-Shijo from a guessed pin; Booking's own page said 3,100 ft, 12 min. Take coordinates from LiteAPI/Trivago/Airbnb records or the page's "X ft walking from Y Station" line (`booking_rooms.py` captures it as `stationLine`), and say "estimated" for anything else
- A property with **no reviews yet** on the inventory you're quoting → unverified quality; say so or drop it, never rank it on a rating from a different source
- Re-fetching the same property a third time → you are not persisting results

## Tooling

`curl` and WebFetch cannot do tier 4: Booking.com returns **403 to WebFetch** and property pages are JS-rendered. The Claude-in-Chrome extension additionally refuses results containing cookies or query strings (`[BLOCKED: Cookie/query string data]`), which silently eats room-table extractions.

Drive the user's signed-in Chrome over CDP instead. See `booking-recipe.md`. Three scripts in `scripts/`, all sharing one CDP `Page` class:

| Script | Does | Notes |
|---|---|---|
| `booking_slugs.py` | search-results page → slugs, card price, rating, distance, bed line | **Search by property name** to get an exact slug; area strings often resolve to 0 cards, and distance-sort is flooded by rental operators. Slugs are not guessable (`kyoto-mgallery` is Dhawa Yura) |
| `booking_rooms.py` | property page → every rate row, normalised; check-in/out windows; sold-out flag | persists after each property; `--bed sleeps-two --refundable-only`; prices exclude 10% JP tax (printed as `NOT in total`) |
| `airbnb_rules.py` | listing page → check-in window, checkout time, cancellation deadline, bed line | needed because `airbnb_listing_details` returns amenities only — its POLICIES/DESCRIPTION sections are empty |

Order that worked on Kyoto (2026-08-29, ~40 min, one pass each): LiteAPI rates by lat/lon → Trivago + SerpAPI for names and check-in times → `booking_slugs.py` by name → `booking_rooms.py` on ~35 slugs → `airbnb_rules.py` on the machiya shortlist → merge in a script, never by hand.

**Japan bed rules the parser encodes:** `1 twin bed` is a single. Two or more futons are two beds (a ryokan "Japanese-Style Room, 4 futon beds" sleeps two properly). A sofa bed never counts. "Twin" in a room name is a claim; the bed cell is the evidence.

**Check-in windows are the Japan-specific trap.** Small hotels and ryokan close check-in at 19:00–20:00 with no after-hours option, ryokan often open checkout at 07:30–08:00, and machiya rentals have a host hand over keys inside a 3-hour window. For any arrival after 17:00 or departure before 08:00 the windows are as decisive as the bed, and they only exist on the property page — both scripts capture them.

## Deliverable Format

One row per **room**, not per hotel:

| Hotel | Room (verbatim bed string) | Rate | Total | Free cancel until | Left | Walk |
|---|---|---|---|---|---|---|

Then: what was **ruled out and why** (bed config, cancellation, price, distance), and which sources were checked with their status. A hotel excluded for having only doubles left is a finding the user needs, not noise to drop.

## Common Mistakes

| Mistake | Reality |
|---|---|
| "Trivago gave me the price" | It gave you the cheapest room's price. You do not know its bed or its cancellation terms. |
| "It sleeps 2, so it works" | Occupancy is not bed layout. A double sleeps 2 and fails a twin request. |
| "The hotel has free cancellation" | Properties do not have cancellation policies. Rates do. |
| "I'll just grab the room table quickly" | That is 24 calls and five rewrites of the same parser. Run the script. |
| "I'll cache results in a page global" | Every `navigate` clears it. Write to a file. |
| "No availability" | You checked one OTA, signed out, for one bed type. Check the property direct and signed in. |
| "The API said complete" | A source vouching for its own completeness is making a claim, not reporting a fact. |
| "Radius 1200 m, so it's walkable" | Verify the distance from the returned lat/lon yourself. |
