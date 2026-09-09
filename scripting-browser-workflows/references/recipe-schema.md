# recipe.json

The record of what you *observed*, written while you drive. Scripts are emitted from
it; it is never executed. That is deliberate — an interpreter would be one more thing
to keep working, and the value here is the reasoning, not the runtime.

Nearest prior art is Chrome DevTools Recorder's format
([schema](https://github.com/puppeteer/replay/blob/main/src/Schema.ts)), which stores
`selectors: string[][]` — several candidates per step, tried in order at replay. Steal
that idea; ignore the rest of the format, which records mouse coordinates you do not want.

## Fields

| Field | Required | What it carries |
|---|---|---|
| `name`, `goal` | yes | one line each; `goal` is what a human asked for, not what the code does |
| `recorded` | yes | `at`, `by`, `site`, `how` — how the workflow was driven when observed |
| `observed` | yes | the non-obvious facts. Late rendering, which attribute is the truth, what the label lies about. This is the expensive part to re-derive |
| `tier` | yes | `chosen`, `why`, `fallback`, `fallbackWhen` |
| `steps` | yes | the chosen tier's steps |
| `domSteps` | when tier is `api` | the DOM fallback, so the recipe survives the API changing |
| `signals` | yes | `positive`, `negative`, `canary`, `drift` — see below |
| `output` | yes | the shape every backend must print, and the contract (one JSON object, exit 0) |
| `budget` | yes | `timeoutMs`, `minIntervalMs`, anything the site asks for |
| `secrets` | yes | **names only**. `["CARD_REF", "SESSION_COOKIE"]`. Never a value, never a path with a value in it |
| `money` | yes | `reachable: true|false`. If true, name the gate and defer to `scripted-booking` |
| `verify` | yes | the bench command, the cases, and the case that must fail |

## Selector candidates

Order them by durability, most durable first, and keep the ones you rejected:

```json
{ "selector": ["#slots button", ".slot", ".slot-card"],
  "rejected": { "button:nth-child(2)": "position, not identity" } }
```

Priority, in the order Playwright itself recommends and the order that survived here:

1. Role + accessible name (`getByRole('button', { name: 'Proceed' })`)
2. A stable structural anchor plus element type (`#slots button`)
3. `data-testid` or another attribute that exists to be selected
4. The class you recorded — first to break in a redesign
5. Text alone — breaks on translation and on any label change
6. Positional CSS or absolute XPath — do not emit these

Log which candidate resolved on each run. When a script breaks, that log says where
drift started instead of forcing a rewrite.

## signals

```json
"signals": {
  "positive": { "test": "any row has available === true", "means": "open" },
  "negative": { "test": "rows exist but none available, OR #emptyBanner visible", "means": "none" },
  "canary":   { "test": "nav a[href='/slots'] exists", "means": "page rendered at all" },
  "drift":    { "test": "neither positive nor negative holds", "means": "report drift, never none" }
}
```

`negative` is the field agents leave out, and it is the one that makes a zero
trustworthy. If the site has no empty-state element, say so and use the canary plus a
row-count fingerprint from the last good run instead.

For a funnel, the same three signals read differently — write them in the funnel's own
words rather than forcing the poller's vocabulary:

```json
"signals": {
  "positive": { "test": "#placeOrder present and enabled with both guests filled", "means": "ready" },
  "negative": { "test": "#proceed disabled with cart=0, or the site's own refusal text", "means": "blocked — the site said no, and it meant it" },
  "canary":   { "test": "form#checkout exists", "means": "still the checkout page" },
  "drift":    { "test": "neither held", "means": "the funnel moved; do not report blocked" }
}
```

**When you cannot manufacture a broken page.** Some sites give you no knob to rename a
class or empty a list. Then the must-fail case is a *proxy* — feed the field a value
the parser cannot read, or point the script at a page one hop away — and the recipe
says plainly that it is a proxy and what real drift would look like. A proxy you have
labelled is worth far more than a must-fail case you skipped.

## Emitting from the recipe

Each backend is a straight transcription. The rules that keep them interchangeable:

- **One JSON object on stdout, exit 0.** Errors are a `status`, not an exit code —
  a poller that exits non-zero gets retried by the scheduler and hides the reason.
- **One log site, one exit site, after cleanup.** Every branch sets the result and
  falls through. A `process.exit()` inside a `try` skips its `finally`, leaking the
  CDP connection that is the reason the process would not end in the first place.
- **Identical bytes across backends** for the same page state. That is what lets
  `bench.mjs` diff them, and it is why replay token cost does not depend on the backend.
- **Timeouts bounded and named.** The drift path costs the whole timeout; that is the
  slowest case, not the fastest.
- **Re-mint anything one-shot** — CSRF tokens, nonces, page-minted API tokens.
- **Secrets by reference at run time.** `process.env[name]`, never a literal.
- **Explicit `process.exit()`** after the result when a CDP connection is open.

Re-emit rather than hand-patching one backend: two scripts that have drifted apart
silently answer differently, and the bench will show it as a flake.

## When the site changes

The recipe is the diff target. Update `observed` and the selector candidates, re-emit,
re-bench, and record the change in the README. Do not patch the emitted script and
leave the recipe describing a site that no longer exists — that is how the next session
inherits a lie.
