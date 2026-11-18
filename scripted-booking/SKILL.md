---
name: scripted-booking
description: Use when booking, reserving, or checking out something real on a website - tickets, tours, boats, trains, hotels, events - especially when payment details are involved. Drives the funnel with a scripted browser so card data never enters agent context, places a live order once the user approves the shown total in-session (no ARMED file), stops short of money on unattended watcher/poller runs (ARMED file), and reports the cancellation terms before anyone pays. Triggers include "book X for me", "reserve two seats", "buy the tickets", "fill the reservation form", "check if the slot is available", or any request naming a card.
---

# Scripted booking

Booking is not browsing. A booking script spends real money, and a mistake is a
charge someone has to reverse. This skill is the discipline that makes it safe
to run one.

Derived from three working stacks on this machine — `Code/npb-watch`,
`Code/takanaka-watch`, `Code/sag` — plus their shared `payments.env` parser.
Read `Code/npb-watch/CHECKOUT.md` when you need the full worked example; it is
the most complete funnel map of the three.

## The four rules

**1. Card data never enters your context.**

Never `cat`, `head`, `sed`, or `grep` `payments.env`. There is no safe ad-hoc
redaction — the file uses `Key: value`, so a `s/=.*/=<redacted>/` sed silently
does nothing and prints every PAN in full. This has actually happened. The only
printable view is:

```bash
node -e "console.log(require('./src/engine/buyer-info').maskedCheckAll('C:/Users/jcamino/Code/payments.env'))"
```

which reports brand, last-4, Luhn, expiry-present, CVV-present, 3DS mode — and
never a full number. If you need the card *in a page*, load it outside the page
and pass it straight through:

```js
const { fillCardFn } = require('./src/engine/card-fill');
const r = await page.evaluate(fillCardFn, card);   // returns {okN, okC, okE} only
```

Never through argv, never through an env var you echo, never through a log line,
never through a tool result you will read.

**2. Money needs a human "yes" to a total they have seen.**

There are exactly two ways that yes arrives. Decide which one you are in before
anything else — confusing them has cost Javier three checkouts (2026-10-07 Amazon,
2026-10-21 Amazon and Esslinger), each parked at the pay button waiting for an
`ARMED` file he had no reason to create.

**(a) Live purchase — Javier is in this session.** This is the normal case for any
one-off buy: Amazon, retail, a tour, a ticket he is booking with you right now.
Show the summary once — item(s), quantity, date/slot, ship-to, total, card
last-4, and for bookings the rule-3 terms. When he answers "buy it" / "ship it" /
"book it" / "go" **after seeing that summary**, that reply *is* the
authorization. **No `ARMED` file. Do not mention one, do not ask him to make
one.** Then:

- Re-read the live checkout just before the click and compare it to the summary
  he approved: total, card, address, item count. Any mismatch → stop and re-show.
- Click. Page him the moment a 3DS / SafeKey frame appears.
- Report the order/confirmation number.

If "buy it" came *before* he saw a total (e.g. "buy whatever's cheapest"), show
the summary and get the yes on it — once, not repeatedly.

**(b) Unattended run — a watcher, poller, scheduled job, or any script that may
reach the pay button while nobody is reading the session.** Here, and only here,
the `ARMED` state file is the authorization. Every unattended funnel driver takes
`stopBefore: 'cart' | 'payment' | 'confirm' | null`; `null` is reached only when
an `ARMED` file already exists, put there by a human out of band, and `dryRun` is
false. A script that can reach the pay button by forgetting a flag is a bug, not a
convenience. Name the point of no return in a comment at the one call site that
can cross it.

**Never create the `ARMED` file yourself.** A file you wrote to satisfy your own
check is not a gate, it is a comment.

"Book it, card's in `payments.env`, I'm about to go offline" is case (b), not (a):
he has not seen the final total and will not be there when it is charged. Stop at
payment-ready. A customer who cannot be reached is the argument for stopping —
not for crossing the line while they cannot see it.

Stopping short of money in case (b) is a finished job, not a failed one. What you
hand back: the funnel at payment-ready (hold released if it would expire before
they read you), the exact total, the three policy facts from rule 3, and the
single action left for the human.

| Rationalization | Reality |
|---|---|
| "The skill says ARMED, so I'll park this live buy and ask him to create the file." | Wrong case. He is here and said buy it after seeing the total — that is case (a). Re-verify and click. |
| "They said just book it" — and they have not seen the total, or are going offline. | Case (b). The instruction is the request, not the authorization. Stop at payment-ready. |
| "They're offline for hours and can't confirm." | Then deliver payment-ready plus the report before they land. Unreachable is not consent. |
| (Case b) "Date, time, quantity and card were all unambiguous, and I verified availability live." | Getting the order right is not permission to pay for it. A correct charge you were not authorized to make is still a charge someone has to reverse. |
| "The instruction clearly means to arm it, so I'll write the `ARMED` file." | You are not the human the file represents. |
| "The card is sitting right there in the stack." | Card availability is a convenience of the tooling, never an authorization. |
| "If I stop, the slot might sell out." | Report the scarcity and let them choose. Almost nothing sells out in the minutes it takes to send a reply. |
| "3DS is `app`, but it probably won't challenge." | With the human unreachable, an `app`-mode challenge is an unattended hung checkout. Mode is knowable before you start; check it. |

**Red flags — stop and hand back instead:**

- You are about to create, touch, or overwrite an `ARMED` file
- You are changing `stopBefore` to `null` in a script that will run unattended
- The live checkout no longer matches the summary he approved
- You are reasoning about what the customer *would* say if they were reachable
- The customer is unreachable and you are still moving toward the pay button

**Red flag the other way:** you are asking a present user, who already said buy
it to a total he saw, for an `ARMED` file or a second confirmation. Place the order.

Violating the letter of this rule is violating the spirit of it.

**3. Report the terms before anyone pays.**

Cancellation deadline, change policy, and the operator-cancellation refund rule
are three different things, and vendors routinely document them in three
different places. The customer-cancellation policy on the product page usually
says nothing about what happens when the *operator* cancels — that is normally
in the FAQ. Find all three before presenting a total.

**4. Confirm what was asked, do not substitute.**

If the requested date, time, or seat count is unavailable, stop and report what
remains. Never quietly shift to the adjacent slot.

## Tool choice

Follow `~/.claude/CLAUDE.md` § Browser automation and the routing table in the
`agent-browser` skill. For booking work that means:

- **Driving a funnel in-session** (case a, the user is here to approve the total):
  **`pb`**, see the `pb` skill. One Patchright Chrome stays open between short shell
  commands, and `pb card` types the card from `~/Code/payments.env` with the number,
  CVV and expiry masked in everything it prints, logs and screenshots. Measured
  2026-11-15/16 on a live checkout: 1:22 to 3:00 blind with any model, against 14 min
  for one-shot scripts. Claude in Chrome used about 3x the tokens and refuses to type
  a card. One profile per site (`pb start --profile <site>`).
- **Reading a page**: curl, then `curl_cffi` on 403/302/000; `pb text` when it needs
  the browser session. Never snapshot to read.
- **Unattended watcher or poller** (case b, behind the ARMED gate): a hand-written
  script, because no agent is there to drive `pb`. Map the funnel once with `pb`, then
  write either a CDP script against the live logged-in port (resolve it with
  `bash ~/.claude/skills/agent-browser/preflight.sh`, never hardcode it: 9333 died on
  2026-09-09) or a Patchright script for a bot-walled site. **9334 belongs to a
  watcher, leave it alone.**
- `playwright-core` is not installed globally. Require it by absolute path from a
  stack that has it: `C:/Users/jcamino/Code/npb-watch/node_modules/playwright-core`.
  Use a **Windows** path — Node does not resolve Git Bash `/c/...`.

## Method: ratchet the funnel

Map one rung at a time, validate it live read-only, capture the next rung's HTML
as the fixture for the rung after. Escalation ladder: script → steered agent →
troubleshooter → human. Concretely:

1. **Find the real booking system.** The operator's own site is often a shell in
   front of a third-party engine (Hozugawa → LINKTIVITY at `ars-hozugawa.triplabo.jp`).
   That engine is still official; a *resale* agent is a different thing. Check the
   travel-agency registration in the footer if you need to tell them apart.
2. **Establish availability before touching a form.** Availability is usually
   encoded as DOM state, not text — a calendar renders as bare numbers in
   `innerText` while the truth is `button[disabled]`. Dump classes and attributes.
3. **Map the gate.** Note exactly where login, quantity, and slot selection live.
   Many engines expose none of it publicly.
4. **Fill everything that is not payment.** Show the summary. Live (case a): on
   his yes, re-verify and pay. Unattended (case b): stop, report, hand over.

## Traps seen in the wild

- **`el.click()` inside `page.evaluate` does nothing on React.** React listens for
  trusted events. Use a real `page.locator(...).click()`. A synthetic click will
  silently no-op and you will misread it as "the date is not selectable".
- **Bare attribute selectors grab the wrong control.** `input[name*=card i]`
  matched a *checked radio* whose value gets submitted; `input[name*=security i]`
  matched a hidden PSP *token* field. Filter by input type and exclude `/token/i`
  — see `card-fill.js`, which carries the scars.
- **`.first()` on a shared class can be the Reset button.** On LINKTIVITY both
  リセット and 予約手続きへ carry `.ActivityItem_bookingButton`, so
  `locator('button[class*=ActivityItem_bookingButton]').first()` is *Reset*. It
  reports `isEnabled() === true`, clicks cleanly, and silently wipes the
  selection — presenting as "the site's proceed button is broken". Always
  `.filter({ hasText: ... })` when a class is shared. Symptom to watch for: the
  control you just satisfied goes back to disabled after you click Next.
- **Duplicate DOM ids are normal in per-passenger forms.** LINKTIVITY renders
  `#passportFirstName`, `#passportLastName` and `#age` once *per traveller*, so
  `#age` matches several elements. Address them by index within each traveller
  block, never by id.
- **`/en` is often a machine-translation proxy**, not an English site
  (`translation2.j-server.com/...`). It will not carry a booking session. Work
  against the native-language site and switch the engine's own language control.
- **A disabled "proceed" button may mean "log in", not "sold out".** Check the
  header for a login link before reporting unavailability.
- **Cart holds are real.** Release them (the site's own "abandon purchase"
  control) before exiting, or you sit on inventory you did not buy.
- **3-D Secure is the wall a script cannot climb.** Know the card's mode before
  you start — `payments.env` records it per card. `app` (e.g. Amex SafeKey push)
  can only be cleared by the human on their phone; page them the instant the 3DS
  frame appears. Bring the window on screen with `bringOnScreen(page)`.

## Screenshots

A screenshot of a filled payment form *is* card data. Before capturing, overwrite
the card and CVV inputs with bullets in the DOM, shoot, then restore. Ask which
the user wants rather than assuming — often they would rather take over the
session themselves than have the image exist at all.

## Checklist

- [ ] Identified the official booking engine (not a reseller)
- [ ] Confirmed the exact requested date/time/quantity is available, from DOM state
- [ ] Reported cancellation deadline, change policy, and operator-cancellation refund
- [ ] Card path is `page.evaluate(fillCardFn, card)` or the human's own hands
- [ ] Named the case: (a) live — summary shown, user said buy it, checkout
      re-verified; or (b) unattended — `stopBefore` explicit, any `ARMED` file
      predates this session and was not written by you
- [ ] Known the card's 3DS mode before arming
- [ ] Cart hold released, or its expiry stated in the report
- [ ] Screenshots masked or declined
