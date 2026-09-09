# Measured costs

Everything the SKILL.md quotes, with the method. Windows 11, Node 22.19.0,
Chrome 152 headless, agent-browser 0.36.0, playwright-core 1.62.1, 2026-09-09.
All against the local fixture, so the numbers are floors — a real site adds its own
latency to every row equally.

## Deriving vs replaying

Three subagents (Sonnet) each drove one workflow on the fixture and handed back code.
Token and duration figures are the harness's own accounting for the whole subagent run.

| Workflow | Tokens to derive | Wall | Replay after |
|---|---|---|---|
| Availability poller | 94,107 | 6m 47s | 0.2 s, 52 B |
| Checkout funnel, end to end | 107,069 | 7m 22s | 2.5 s |
| Same page, two backends + a comparison | 132,464 | 13m 43s | 1.4 s, 52 B |

**~8,000× fewer tokens to replay than to derive** (≈13 tokens of stdout against ~107k).
The break-even is the second run. It is not close, and it is the entire argument for
writing the script at all.

## Backends, same workflow, same page

`node harness/bench.mjs examples/slot-watch -n 10`, medians in ms, four page states:

| case | api | cdp | cli | bytes (all) | correct |
|---|---|---|---|---|---|
| many | **153** | 1273 | 1710 | 52 | 10/10 each |
| one | **139** | 1264 | 1610 | 36 | 10/10 each |
| none | **141** | 1380 | 1718 | 29 | 10/10 each |
| drift | **181** | 1372 | 9923 | 52-68 | 10/10 each |

Three runs, two at n=10 and one at n=6 after a refactor, on the same machine and page:

| tier | spread across runs |
|---|---|
| no-browser | 110-205 ms |
| cdp | 683-1539 ms |
| cli | 1286-1991 ms (drift 9311-9923 ms) |

The absolutes move ~2× with machine load; the **ratios hold** — ~8× between the
no-browser and DOM tiers, ~1.3× between CDP and the CLI. Quote the spread, not one run.

Read three things off this:

1. **The API tier is ~8× faster than the DOM tier**, and the gap is structural — it
   skips browser startup, page load and the site's own 400 ms render delay.
2. **CDP beats the CLI by ~1.3×** because the CLI pays a process launch per command
   (open, wait, eval). An independent agent measuring the same pair its own way got
   1868 ms vs 2768 ms — the same ratio from different code.
3. **Bytes are identical across backends.** The output contract decides replay cost,
   not the tool. The CLI's famous extra bytes are spent while an *agent* drives it
   interactively, not by a packaged script.

The `drift` row is the interesting one: the DOM backends spend their whole timeout
before concluding they have gone blind (the CLI's 9.8 s is its longer default wait).
Budget for the drift path being the slowest, not the fastest.

## Correctness

All three backends answered 10/10 on all four cases *after* the drift verdict was
built in. Before it, the naive version — wait for `.slot`, report what you find —
answers `none` on the drift case, which is wrong in the most dangerous direction:
slots were open, and the poller reported nothing while looking healthy. Not a
hypothetical — `examples/slot-watch/run.naive.mjs` is that script, and it scores
**0/5 on the drift case, taking 6.0 s to be wrong** (it waits out its timeout first,
then reports `{"status":"none","slots":[]}` with three slots open).

`bench.json` lets a backend that legitimately sees a different truth say so: the API
tier never touches the DOM, so renamed markup cannot fool it, and its expectation for
that case is `open` with an explicit `forbid` on `none`.

## Off the fixture

`node harness/live-smoke.mjs https://example.com` — same two tiers, real network,
2026-09-09: **HTTP 231 ms / 559 B**, **CDP 411 ms**, both reading `Example Domain`
from `<h1>`, `agree: true`. The tier gap narrows on a trivial page because there is
nothing to render; it widens again on anything that fetches its content client-side,
which is where the fixture's 8× gap comes from.

Every number above the line is a floor. A real site adds its own latency to both
tiers, so treat the *ratios* as the transferable part and re-measure the absolutes
when they would change a decision.

## Re-measuring

```bash
node fixtures/site/server.mjs 8712 &
node harness/test-chrome.mjs start 9345
cd examples/slot-watch
WF_SITE=http://127.0.0.1:8712 WF_URL=http://127.0.0.1:8712/slots \
  WF_CDP=http://127.0.0.1:9345 node ../../harness/bench.mjs . -n 10
node ../../harness/test-chrome.mjs stop 9345
```

Re-measure after an agent-browser or playwright upgrade, and when a number here would
change a routing decision. Quote the date with the number, as above — a stale
benchmark that reads as current is how the `agent-browser` skill once carried a
100× error for four days.
