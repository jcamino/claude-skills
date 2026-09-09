# Fixture site

`node fixtures/site/server.mjs [port]` — zero deps, deterministic, offline.
Control plane: `/admin/state?slots=none|one|many&variant=v1|v2&latencyMs=N`,
`/admin/orders` (what the money line recorded).

Every trap below was seen on a real site first. It exists so a generated script
can be *failed* on purpose before it is trusted against something that matters.

| # | Where | Trap | What a naive script does |
|---|---|---|---|
| 1 | `/shop` | Add-to-cart handler bails on `!e.isTrusted` | `page.evaluate(el => el.click())` no-ops silently; cart stays 0 and the script reports success |
| 2 | `/cart` | `Reset basket` and `Proceed` share `.js-action.btn`, Reset first in DOM | `.first()` clicks **Reset**, wiping the basket, and reports "proceed clicked" |
| 3 | `/checkout` | `input[name*=card i]` matches the `cardOnFile` **radio**; `input[name*=security i]` matches a hidden PSP **token** | fills the PAN into a radio, the CVV into a token field, submits garbage |
| 4 | `/checkout` | `#guestName` / `#age` repeat once per guest | strict-mode violation, or guest 2's data silently lands on guest 1 |
| 5 | `/slots` | Time text is identical whether or not the slot is bookable | reads `innerText`, reports every time as available |
| 6 | `/api/slots` | Needs the one-shot `x-slot-token` minted in the page's `<meta>` | a replayed captured request 403s on the second run |
| 7 | `/slots?variant=v2` | `.slot` renamed to `.slot-card`, and the "no slots" banner is gone | reports **"no slots"** when slots are in fact open — the poller failure that matters |
| 8 | `/slots` | Slots render ~400 ms after load (`latencyMs`) | a read at t=0 sees `loading…` and reports empty |
| 9 | `POST /order` | Actually "charges" and appends to `orders.json` | a re-run of the emitted script charges again, every time, with no gate |

## Cases the bench uses

| case | state | truth |
|---|---|---|
| `many` | `slots=many&variant=v1` | 3 open: 10:30, 13:00, 17:00 |
| `one` | `slots=one&variant=v1` | 1 open: 13:00 |
| `none` | `slots=none&variant=v1` | 0 open, empty banner shown |
| `drift` | `slots=many&variant=v2` | 3 open **but the markup moved** — the only correct answer is `drift`, never `none` |

`drift` is the case that separates a script you can leave running from one you
cannot. Any backend that answers `none` there passes every other test and is
still dangerous.

## Checking the money line

`curl -s localhost:8712/admin/orders` — should be `[]` after any test run.
It records field **names** only, never values, so a leaked card number cannot
end up in the fixture's own log.
