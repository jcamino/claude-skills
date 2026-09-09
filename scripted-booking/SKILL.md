---
name: scripted-booking
description: Use when booking, reserving, or checking out something real on a website - tickets, tours, boats, trains, hotels, events - especially when payment details are involved. Drives the funnel with a scripted browser so card data never enters agent context, stops at a declared point short of money, and reports the cancellation terms before anyone pays. Triggers include "book X for me", "reserve two seats", "buy the tickets", "fill the reservation form", "check if the slot is available", or any request naming a card.
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

**2. You do not arm the money. A human does.**

Every funnel driver takes `stopBefore: 'cart' | 'payment' | 'confirm' | null`.
`null` — money reachable — is passed only when an `ARMED` state file already
exists, put there by a human out of band, and `dryRun` is false. A script that
can reach the pay button by forgetting a flag is a bug, not a convenience. Name
the point of no return in a comment at the one call site that can cross it.

**Never create the `ARMED` file yourself.** A file you wrote to satisfy your own
check is not a gate, it is a comment. Writing it forges the record of a decision
a human did not make.

The request to book is not the authorization to charge. "Book it, card's in
`payments.env`, I'm about to go offline" is what makes the work worth doing; it
is not the second signature on the money. A customer who cannot be reached is
the argument for stopping at payment-ready — not for crossing the line while
they cannot see it.

Stopping short of money is a finished job, not a failed one. What you hand back:
the funnel at payment-ready (hold released if it would expire before they read
you), the exact total, the three policy facts from rule 3, and the single action
left for the human.

| Rationalization | Reality |
|---|---|
| "They said just book it." | The instruction is the request. `ARMED` is the authorization. One party supplying both, inside a chat window, is the exact failure this rule exists for. |
| "They're offline for hours and can't confirm." | Then deliver payment-ready plus the report before they land. Unreachable is not consent. |
| "Date, time, quantity and card were all unambiguous, and I verified availability live." | Getting the order right is not permission to pay for it. A correct charge you were not authorized to make is still a charge someone has to reverse. |
| "The instruction clearly means to arm it, so I'll write the `ARMED` file." | You are not the human the file represents. |
| "The card is sitting right there in the stack." | Card availability is a convenience of the tooling, never an authorization. |
| "If I stop, the slot might sell out." | Report the scarcity and let them choose. Almost nothing sells out in the minutes it takes to send a reply. |
| "3DS is `app`, but it probably won't challenge." | With the human unreachable, an `app`-mode challenge is an unattended hung checkout. Mode is knowable before you start; check it. |

**Red flags — stop and hand back instead:**

- You are about to create, touch, or overwrite an `ARMED` file
- You are changing `stopBefore` to `null` in a script you wrote this session
- The words "explicit instruction", "unambiguous", or "clearly authorized" are
  doing the work in your reasoning about paying
- You are reasoning about what the customer *would* say if they were reachable
- The customer is unreachable and you are still moving toward the pay button

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

Follow `~/.claude/CLAUDE.md` § Browser automation. For booking work that means:

- **Reading a page** — `document.body.innerText` over CDP. ~1.4 KB vs 28 KB for
  a snapshot. Never snapshot to read.
- **Driving a known funnel** — hand-written `playwright-core` script against
  `chromium.connectOverCDP('http://127.0.0.1:9333')`. Own page, act, `page.close()`,
  `browser.close()`. Port 9333 is the logged-in profile; **9334 belongs to a
  watcher, leave it alone**.
- **Mapping an unknown funnel once** — `@playwright/cli` attached to Chrome, snapshot
  to `.playwright-cli/*.yml`, grep the file, never cat it. Then write the script.
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
4. **Fill everything that is not payment.** Stop. Report. Hand over.

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
- [ ] `stopBefore` set explicitly; any `ARMED` file predates this session and was
      not written by you
- [ ] Known the card's 3DS mode before arming
- [ ] Cart hold released, or its expiry stated in the report
- [ ] Screenshots masked or declined
