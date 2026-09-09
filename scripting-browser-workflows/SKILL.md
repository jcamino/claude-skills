---
name: scripting-browser-workflows
description: Use when a browser workflow that was just driven by hand will be needed again - an availability or appointment poller, a price or stock watcher, a booking or checkout funnel, a login-and-scrape - or when asked to turn a session into a script, to replay a workflow without an agent in the loop, or to pick between a browser CLI, a CDP script and the site's own JSON API for repeat runs.
---

# Scripting browser workflows

Driving a workflow with an agent costs **~100k tokens and 7-14 minutes**. Replaying
the same workflow as a script costs **~13 tokens and 0.2-1.9 s**. Measured on this
machine, 2026-09-09, three agents against the same fixture: 94k / 107k / 132k tokens
to do it once and hand back code, against 29-68 bytes of stdout per replay.

So the script pays for itself on the second run. The whole job of this skill is
making that second run trustworthy — because a script that silently returns
"nothing available" after the site moved is worse than no script at all.

**Use it for:** anything that will run more than once — pollers, watchers, funnels,
scheduled scrapes, QA replays.
**Not for:** a one-off lookup (just read the page), or an unknown funnel you have not
yet driven — drive it first, then come back here.

## What you leave behind

Four things are required in one directory per workflow. Add whatever else the
workflow needs — a second backend, a `setcase.mjs`, the scheduled wrapper.

```
workflows/<name>/
  recipe.json     REQUIRED  what you OBSERVED and why each selector was chosen — emitted from, never executed
  run.<tier>.mjs  REQUIRED  the runnable script; one per backend you emitted
  bench.json      REQUIRED  the cases, including the one that must FAIL
  README.md       REQUIRED  how to run it, what it costs, what breaks it
  run.naive.mjs   worth keeping: the obvious version, as evidence of what it gets wrong
```

`recipe.json` is the part everyone skips. Without it the next session cannot tell a
deliberate selector from a lucky one, and re-emits from scratch. Schema and a worked
example: `references/recipe-schema.md`, `examples/slot-watch/recipe.json`.

**Write recipe.json while you drive, not from memory afterwards.** Every observation
you do not write down at the moment you make it is one you will re-pay 100k tokens for.

## Three outcomes, never two

Every run ends in **found** / **trustworthy negative** / **blind** — or your poller will
report "no appointments" forever after a class rename, and look perfectly healthy doing it.

| Shape | found | trustworthy negative | blind |
|---|---|---|---|
| watcher / poller | `open` | `none` | `drift` |
| funnel to a stop point | `ready`, then `confirmed` past the gate | `blocked` — the site itself refused (empty cart, sold out, login) | `drift` |

| verdict | test | meaning |
|---|---|---|
| found | a positive signal matched | act on it |
| negative | rows present but none available, **or** the site's own empty-state / refusal element is showing | a real zero you can trust |
| `drift` | neither held | you have gone blind — alert a human, never report a zero |

For a funnel, the stop point is a **status, not an exception**: `ready` means parked at
the last step before money with everything filled, and it exits 0. A funnel that can
only either complete or throw has no safe resting place.

Three rules that make this work:

- **Assert the negative explicitly.** "No slots" must be proven by the site's own
  empty-state, not inferred from your selector matching nothing.
- **Carry a canary.** One element that proves the page rendered at all (a nav link,
  the footer). Canary present + rows gone = drift. Canary gone = the site is down or
  you are looking at a challenge page.
- **Wait for either outcome, never for the good one.** `waitForSelector('.slot')` turns
  a genuine "none" into a timeout, and a timeout into a crash loop.

Verify it by breaking the page on purpose: `?variant=v2` in the fixture renames the
class and deletes the empty banner while slots stay open. A backend that answers `none`
there passes every other test and is still dangerous.

## Pick the tier before the backend

| Tier | When | Cost here |
|---|---|---|
| **No browser** — an HTTP client: the page's own `fetch`/XHR, **or** the server-rendered HTML itself | the answer is in a response body | **110-205 ms** |
| **CDP script** — `playwright-core` → `connectOverCDP` | needs the DOM, a login, or real clicks | **0.7-1.5 s** |
| **CLI** — `agent-browser --session` | no debug port, or the funnel is still moving | **1.3-2.0 s**, ~9.3-9.9 s on the drift path |

Medians, three runs of `harness/bench.mjs` against the local fixture, 2026-09-09.
The ratio is the transferable part — roughly **8× / 1.3×** — not the absolutes.
An independent agent measuring the same two backends its own way got 1868 ms vs
2768 ms — same ~1.3-1.4× ratio.

**The no-browser tier is the prize** — ~8× cheaper than the DOM here. Two ways in, and
you must check both: capture the site's own calls while you drive (`agent-browser
network requests`, or CDP `Network`) and see whether one answers the question; and
`curl` the page itself, because a server-rendered page needs no JSON endpoint at all.
Naming the tier "API" makes agents skip the second check and reach for a browser.

It breaks on: one-shot CSRF tokens, client-computed signatures, short-lived bearers,
and behavioural bot walls. Re-mint tokens per run — never replay a captured request
verbatim. If the mint step is itself a scrape, keep a DOM fallback in the same recipe.

**Replay token cost is identical across backends** — 29-68 bytes either way, because
the output contract decides it, not the tool. The CLI's extra bytes are spent while an
agent is driving it, not once packaged. Choose the backend on latency, lifecycle and
what it can reach; not on tokens.

## Method

1. **Drive it once** and write `recipe.json` as you go — every selector you tried,
   which one held, what the truth signal actually was.
2. **Capture the network** in the same pass. Decide the tier from what you saw.
3. **Emit the scripts.** One per backend you need. All emit the same JSON contract on
   stdout and exit 0.
4. **Bench them**: `node harness/bench.mjs <dir> -n 10`. Include the must-fail case.
5. **Leave the README** with the numbers you measured and the conditions that break it.

Skip step 4 only when the workflow reads one static page and nothing branches. Say so
in the README when you do.

**The shape every emitted script has**, in this order: compute one result object →
close the browser/connection → one `console.log(JSON.stringify(result))` → exit 0.
One log site, one exit site, at the end. Branches set the result and fall through;
they do not print and they do not exit early. Errors are a `status`, not a non-zero
exit — a poller that exits non-zero gets retried by the scheduler with the reason
thrown away.

## Money, secrets, and other people's sites

- Anything that can spend money is a `scripted-booking` job first and a codegen job
  second. **REQUIRED: use the `scripted-booking` skill** — its `stopBefore` / `ARMED`
  discipline governs the *emitted script* just as much as the live session. A
  script that re-runs a checkout end to end charges the card every single run, silently.
  One baseline agent left exactly that, and charged the fixture twice.
- **Three properties an emitted funnel script must have**: it stops at `ready` by
  default and reaching money takes an argument a human types (or an `ARMED` file that
  predates the session — you never write one); the secrets it needs are absent by
  default, so an accidental arm still cannot pay; and it carries a re-charge guard —
  an order key or a state file — so running it twice does not buy twice.
- **Never write a credential or a card number into the emitted file.** Take them by
  reference — env var name, or a path resolved at run time. A baseline agent hardcoded
  a fabricated PAN into the script it handed over; a real one would have been committed.
- **Rate-limit in the script, not in the scheduler.** Hardcode a floor interval and
  honour `Retry-After`. Never poll an authenticated or reservation-holding URL when a
  public one answers the same question — polling the authenticated one can take the
  slot out of the public pool.

## Traps that cost time here

| Trap | Symptom | Fix |
|---|---|---|
| `import` of an absolute Windows path in `.mjs` | `ERR_UNSUPPORTED_ESM_URL_SCHEME` | `createRequire(import.meta.url)('C:/…/playwright-core')` |
| `connectOverCDP` keeps the event loop alive | script "hangs" long after it printed the answer; orphan node process | `await page.close(); await browser.close()` — measured: closing exits 0 on its own, not closing still ran at the 10 s kill. Reach for `process.exit()` only if something else holds the loop, and then **after** cleanup: it is synchronous, so an exit inside a `try` skips the `finally` and leaks the very connection that hangs you |
| `out=$(agent-browser …)` | hangs ~1 hour | redirect to a file; see the `agent-browser` skill |
| A CDP port number written into the emitted script | works today, dead next month — the logged-in port has already moved once on this box | take it from an env var, resolve it at run time (`agent-browser/preflight.sh`), and fail with `status: "error"` naming the port when nothing answers |
| `rm -rf "$TMPDIR"` in a CLI wrapper | 80 lines of "Device or resource busy" | agent-browser parks a live Chrome profile under TMPDIR — clean up files, not trees |
| CLI session left open | a Chrome + daemon per run | reuse a named session on purpose, or close it; decide which and say so |
| `el.click()` inside `evaluate` | no-op on React and on any `isTrusted` guard | real `locator().click()` |
| `.first()` on a shared class | clicks *Reset*, wipes the basket, reports success | `.filter({ hasText })` |
| Duplicate ids in per-item forms | strict-mode violation, or row 2 lands on row 1 | scope by block index |
| Availability read from `innerText` | every slot looks open | read `disabled` / `data-*`, never the label |

## Checklist

- [ ] `recipe.json` written **during** the drive, with the selector candidates that
      were tried and the truth signal that was used
- [ ] Both no-browser routes checked — the page's own calls **and** a plain `curl` of
      the page — and the tier choice justified in the recipe
- [ ] Output contract: one JSON object, exit 0, identical across backends; one log
      site and one exit site, after cleanup
- [ ] `drift` verdict implemented, with an explicit negative signal and a canary
- [ ] Must-fail case in `bench.json`, and it actually fails the naive version. If the
      site gives you no way to break it, say so in the README and fingerprint the last
      good run instead
- [ ] `node harness/bench.mjs <dir> -n 10` run, numbers in the README
- [ ] Interval floor and `Retry-After` honoured in the script itself
- [ ] No secret, card number or session cookie written into any emitted file
- [ ] Money path gated per `scripted-booking`, or provably unreachable
- [ ] Alert path exercised at least once — an alert nobody receives is not an alert

## Rationalizations

| Excuse | Reality |
|---|---|
| "The selector is obvious, I'll skip the recipe." | The next session re-derives it for 100k tokens. Writing it down costs 30 seconds. |
| "If it returns nothing, there's nothing there." | That is the vaccine-poller failure exactly. Prove the zero or report drift. |
| "I tested the happy path, it works." | All three baseline agents said this. None had tested a broken page; two admitted it unprompted. |
| "Benching it is overkill for one page." | The bench is what catches a fast wrong answer. Four cases take ~2 minutes. |
| "It's a test site, so the checkout is safe to complete." | The script you leave behind will not know that. Gate it now. |
| "I'll re-use the captured API call, it worked when I ran it." | One-shot tokens 403 on run 2. Re-mint every run. |

## Files

- `harness/bench.mjs` — speed / correctness / bytes across backends, with per-backend
  expectations for cases where two tiers legitimately see different truths
- `harness/test-chrome.mjs` — disposable Chrome on its own port and profile. It kills
  only the profile it created, so it cannot touch the user's Chrome or the watcher
- `harness/live-smoke.mjs` — both tiers against a real URL, so a fixture-only number
  is never quoted as if it applied to the open internet
- `fixtures/site/server.mjs` + `fixtures/README.md` — offline site carrying nine
  real-world traps and the must-fail drift case
- `examples/slot-watch/` — the worked example: recipe, three backends, bench, numbers
- `references/recipe-schema.md` — the recipe format and how to emit from it
- `references/measured-costs.md` — every number quoted above, and how to re-measure

Tool routing (curl_cffi vs CDP vs CLI, and the cost of each) belongs to the
`agent-browser` skill — this skill assumes that choice is already made.
