# slot-watch — worked example

"Tell me when a time slot opens up." The shape behind vaccine-appointment watchers,
ticket-drop pollers and stock alerts.

## Run it

```bash
node ../../fixtures/site/server.mjs 8712 &          # the target
node ../../harness/test-chrome.mjs start 9345       # a disposable Chrome
export WF_SITE=http://127.0.0.1:8712 WF_URL=http://127.0.0.1:8712/slots WF_CDP=http://127.0.0.1:9345

node run.api.mjs        # {"status":"none","slots":[]}
node setcase.mjs many   # open some slots
node run.api.mjs        # {"status":"open","slots":["10:30","13:00","17:00"]}
node setcase.mjs drift  # slots stay open; the markup moves
node run.cdp.mjs        # {"status":"drift",...}  <- the point of the whole example
node run.naive.mjs      # {"status":"none","slots":[]}  <- wrong, and confident

node ../../harness/test-chrome.mjs stop 9345
```

## Files

| File | What it is |
|---|---|
| `recipe.json` | what was observed and why — everything else is emitted from this |
| `run.api.mjs` | the page's own JSON call, re-minting the one-shot token each run |
| `run.cdp.mjs` | `playwright-core` over CDP, for when the DOM is the only source |
| `run.cli.sh` | `agent-browser`, for when there is no debug port |
| `run.naive.mjs` | the script agents write by default. Kept because it fails the one case that matters |
| `bench.json` / `bench.naive.json` | the four cases; the second one demonstrates the failure |

## Measured, n=10 per cell, 2026-09-09

| case | api | cdp | cli | correct |
|---|---|---|---|---|
| many | 153 ms | 1273 ms | 1710 ms | 10/10 all three |
| one | 139 ms | 1264 ms | 1610 ms | 10/10 all three |
| none | 141 ms | 1380 ms | 1718 ms | 10/10 all three |
| drift | 181 ms | 1372 ms | 9923 ms | 10/10 all three |

Two further runs put the spread at api 110-205 ms, cdp 683-1539 ms, cli 1286-1991 ms.
The ratios are the stable part; see `../../references/measured-costs.md`.

`run.naive.mjs` on the same drift case: **0/5, in 6.0 s** — it waits out its timeout and
then reports `{"status":"none","slots":[]}` while three slots are open.

Bytes are 29-68 either way: the output contract sets replay cost, not the backend.

## What breaks this

- The `x-slot-token` is one-shot and minted per page render. A captured request replayed
  verbatim 403s on the second run — `run.api.mjs` re-mints every time.
- If the API shape changes, `run.api.mjs` reports `drift`, not `none`. That check is the
  API tier's substitute for a canary, and it is not optional.
- The CLI backend leaves its session warm on purpose so the next poll is cheap.
  `WF_CLOSE=1` for a one-shot run, or every invocation leaks a Chrome.
- The drift path costs the full timeout on both DOM backends. Budget for it.
