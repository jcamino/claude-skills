# agent-browser — measured costs

Reference only. SKILL.md carries the decisions; this file carries the numbers behind
them. Re-measure after any upgrade and note the date and versions.

Versions when measured: agent-browser **0.36.0**, playwright-cli **0.1.19**.

## Serial latency, `example.com`, n=10, medians (2026-09-08)

| path | navigate | snapshot | snapshot bytes |
|---|---|---|---|
| raw CDP script | **0.24 s** (whole connect→goto→innerText) | n/a | 129 B innerText |
| agent-browser `--cdp`, warm | 0.44 s | **0.46 s** | **74 B** |
| agent-browser own Chrome | 2.1 s cold / 0.53 s warm | 0.41 s | 74 B |
| playwright-cli | 1.07 s | 0.95 s | 779 B |

Add per-invocation CLI boot to anything driven from the shell: playwright-cli pays
**~1–1.5 s every call** (`list` against zero sessions takes 1.1–1.5 s doing no browser
work), so a 4-command task costs ~10 s, not ~4 s. Measured 2026-09-09: `open` 3.4 s,
`attach` 6.9 s, `eval` 1.5–2.5 s.

An own-browser Python Playwright two-page click-through: **8.9–10.2 s cold, 3.0 s warm**.

## Snapshot bytes do not generalise

The 74 B / 779 B figures are `example.com` and are the best case anywhere.

| page | agent-browser snapshot | playwright-cli snapshot |
|---|---|---|
| `example.com` | 74 B | 779 B |
| `iana.org/help/example-domains` | — | **6.6 KB** (`eval` got the same content in 945 B) |
| `duckduckgo.com` | 0.58 s / **9.6 KB** | 1.17 s / **41.6 KB** |

Assume kilobytes, not bytes, on any real page. The vendor guide's "~200–400 tokens" for
`snapshot -i` does not hold outside toy pages.

## Complex unknown DOM — cost, not capability (2026-09-08)

Task: `github.com/trending`, extract top-5 repos plus "stars today", then drive the
date-range control to "This week" by clicking rather than by URL. Three parallel Sonnet
subagents, one per path. **All three fully succeeded and returned identical data.**

| path | tool-output tokens | total agent tokens | tool calls |
|---|---|---|---|
| raw CDP script | **5,086** | **70,879** | **10** |
| playwright-cli | 8,432 | 80,276 | 35 |
| agent-browser | 9,459 | 73,698 | 24 |

Wall time was measured under parallel CPU contention and is not comparable; use the
serial table above.

The finding that generalised: **`eval` with a targeted DOM query beat every
accessibility-tree approach by 10–40×**, and was more correct. `snapshot -i` omits static
text entirely (it could not see "stars today" at all); playwright-cli `find` elides
sibling content with `...`, collapsing repo names away from their star counts. The CDP
path's whole discovery cost was one `outerHTML` dump of a single representative row
(11.3 KB of its 12.6 KB total), then structured JSON forever after.

## The measurement bug that poisoned the 2026-09-04 run

The original file recorded ~184 s to open `example.com` and 39 s for a snapshot that
returned **73 B**. The same snapshot today returns **74 B in 0.41 s** — identical
payload, 95× the time. The harness hung, not Chrome: `out=$(agent-browser …)` around a
command that spawns a new daemon waits for an EOF that arrives only at the daemon's
1-hour idle timeout. See "Traps that cost hours" in SKILL.md.

playwright-cli's 2026-09-04 numbers reproduced almost exactly (0.9 s → 0.95 s) because it
runs no daemon and never hit the trap — which is how the bug was isolated.
