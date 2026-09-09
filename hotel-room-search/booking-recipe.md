# Room-Level Extraction Recipe

## Why not the easy paths

| Path | What happens |
|---|---|
| `WebFetch` a Booking.com hotel page | **403 Forbidden**. Rakuten Travel and trunk-hotel.com too |
| `curl` | Same, plus the room table is JS-rendered — the HTML has no rates |
| Claude-in-Chrome `javascript_tool` | Works, but refuses any result containing cookies or query strings: `[BLOCKED: Cookie/query string data]`. Booking URLs are nothing but query strings, so extractions die at random |
| Inline JS in the page | State lives in `window.__*` and every navigation wipes it. This is what turned one search into 76 tool calls and five rewrites of the same parser |

Drive the user's own Chrome over **CDP** instead. No extension guard, state lives in a file, and the session is signed in — which matters, because Genius and member rates do not render signed out.

## 1. Launch Chrome with a debugging port

Chrome 136+ refuses `--remote-debugging-port` on the *default* profile, so use a dedicated one. It persists logins between runs, so you sign in to Booking.com once, ever.

```bash
"/c/Program Files/Google/Chrome/Application/chrome.exe" \
  --remote-debugging-port=9222 \
  --user-data-dir='C:\Users\jcamino\Code\.chrome-cdp-profile' \
  --no-first-run --no-default-browser-check &

curl -s http://localhost:9222/json/version    # confirm it is up
```

Same profile the `united-award` harness uses. Sign in to booking.com in that window on first use; the script warns when it does not see a session.

## 2. Get the slugs

The script takes Booking.com slugs, not names. Grab them from a search-results page in that same Chrome:

```js
[...document.querySelectorAll('[data-testid="property-card"] a[href*="/hotel/"]')]
  .map(a => a.href.match(/\/hotel\/[a-z]{2}\/([^.]+)\./)[1])
```

Or read them off any hotel URL: `booking.com/hotel/jp/<slug>.en-gb.html`.

## 3. Run the extractor

```bash
python ~/.claude/skills/hotel-room-search/scripts/booking_rooms.py \
  --checkin 2026-09-19 --checkout 2026-09-23 --adults 2 \
  --bed sleeps-two --refundable-only \
  trunk all-day-place-shibuya sequence-miyashita-park-tokyo
```

- `--bed sleeps-two` — two separate beds **or** one double/larger; drops single-bed rooms
- `--refundable-only` — only rates with a free-cancellation deadline
- `--out rooms.json` — results written after **every** property; a crash never costs the batch
- re-running skips properties already in `--out` unless you pass `--refetch`

## What the parser gets right that a hand-rolled one does not

**Rowspan carry-forward.** Booking renders one `<tr>` per *rate*, and the room-type cell carries a `rowspan` — it appears only on the first rate row of each room block. Rows 2..n inherit name and bed from above. Miss this and every cheap rate gets attributed to the wrong room.

**Bed count, not bed word.** `1 twin bed` is a **single** and fails two adults. `2 twin beds` is what a twin request means. Matching on the substring "twin" recommends a single bed to two people — the exact failure `--bed` exists to prevent.

**Price cell shape.** The cell reads:

```
$479 per night $2,478 $2,230 Original price $2,478 Current price $2,230 4 nights 10% off
Included: 15 % Service charge  Excluded: 10 % VAT
```

The first number is the **nightly** rate. Taking it as the total, or dividing it by nights, is wrong in both directions. `Current price` is authoritative.

**`Excluded:` is a real cost.** Japan adds 10% consumption tax and many properties add a 10–15% service charge on top of the displayed total. Trunk's `$2,230` is about `$2,453` on the card. The script surfaces this as `NOT in total:` — carry it into any comparison, or you will rank a tax-exclusive rate against a tax-inclusive one.

**Deadlines are dates.** `Free cancellation before September 12, 2026` — captured as a date, plus `Pay nothing until` where present. A refundable flag with no date is reported as `DATE UNPARSED - read the row`, never as a silent pass.

## 4. Other room-level sources

| Source | Setup | Notes |
|---|---|---|
| **DIDA MCP** | free `mcp_` key, `https://mcp.rollinggo.ai/mcp` | `getHotelDetail` returns bed type, per-room price, free-cancel deadline. Wholesale inventory — prices and property set differ from Booking |
| **hotelzero** | `npm i -g hotelzero && npx playwright install chromium` | Keyless Booking scraper, `RoomOption{name,bedType,cancellation,sleeps,breakfast}`. Its own chromium, so **signed out**; ~25 results; CAPTCHA-prone. Good when you do not want to drive the user's browser |
| **Rakuten Travel** | free App ID, `VacantHotelSearch` | JP domestic inventory and ryokan that Booking under-covers. Plan-level rates |

Jalan has no usable public API — only Apify scrapers. In the failed session it cost 8 tool calls and produced nothing. Skip it; use Rakuten for the JP-domestic angle.

## Gotchas

- **Run via Git Bash, not PowerShell.** PowerShell 5.1 has no `&&`, and mangles quoting in `python -c` one-liners. Anything non-trivial goes in a file
- Set `PYTHONIOENCODING=utf-8` — hotel names carry emoji and Japanese, and the Windows console default (cp1252) raises `UnicodeEncodeError` mid-run
- Poll **outside** the evaluate. Sleeps inside a single `Runtime.evaluate` hit CDP's 45 s ceiling and kill the tab
- A sold-out property returns no `#hprt-table` at all — the script reports `timeout waiting for room table`, which is a finding ("no availability"), not an error to retry
- Prices move between reads. Record when you read them, and re-check before the user books
