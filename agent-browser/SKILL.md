---
name: agent-browser
description: Use when a task needs a real browser or an Electron desktop app on this machine - opening pages, filling forms, clicking, screenshots, scraping, logging in, QA or dogfood sweeps, Slack/VS Code/Discord/Figma automation, deriving a standalone API client from a site's own traffic, or cloud browsers (Vercel Sandbox, AWS AgentCore). Also use when choosing between agent-browser, a raw CDP script, and playwright-cli.
allowed-tools: Bash(agent-browser:*), Bash(npx agent-browser:*)
hidden: true
---

# agent-browser

`agent-browser` is one of three browser paths on this machine. This file routes between them and covers the cases only agent-browser can do. It does not replace the CLI's own guides.

**Re-measured 2026-09-08 on 0.36.0 — agent-browser is fast. The old "~184 s to open
`example.com`" was a harness bug, now understood (see [The 1-hour hang](#the-1-hour-hang)).**
Medians, n=10 per op, its own headless Chrome:

| op | cold | warm |
|---|---|---|
| `open` | **2.1 s** (1.7–2.5) | 0.53 s |
| `snapshot -i` (example.com) | — | **0.41 s / 74 B** |
| `get title` / `eval` / `screenshot` | — | 0.40–0.47 s |
| `snapshot -i` (duckduckgo.com) | — | 0.58 s / **9.6 KB** |

In `--cdp` mode against an existing Chrome: cold 0.87 s, warm ops ~0.40–0.46 s.
The 2026-09-04 run logged 39 s for the snapshot that returned **73 B**; the same
snapshot today returns **74 B** in 0.41 s — same payload, 95× the time, because the
harness hung rather than Chrome being slow.

### All three paths, same page, same day

`example.com`, n=10, medians (2026-09-08). Only agent-browser's old numbers were
wrong — playwright-cli's 2026-09-04 figures reproduce almost exactly (0.9 s → 0.95 s),
because it runs no daemon and so never hits the pipe trap.

| path | navigate | snapshot | snapshot bytes |
|---|---|---|---|
| raw CDP script | **0.24 s** (whole connect→goto→innerText cycle) | n/a | 129 B innerText |
| agent-browser `--cdp`, warm | 0.44 s | **0.46 s** | **74 B** |
| agent-browser own Chrome, warm | 0.53 s | 0.41 s | 74 B |
| playwright-cli extension | 1.07 s | 0.95 s | 779 B |

On a heavy page (`duckduckgo.com`): agent-browser snapshot 0.58 s / **9.6 KB**,
playwright-cli snapshot 1.17 s / **41.6 KB**, playwright-cli goto 1.89 s.

**So playwright-cli is now the slowest of the three and returns 10-40× more bytes.**
Its remaining edge is the one thing it alone does: attach to the real logged-in Chrome
through the extension with **no debug port**. Reach for it for that, not for speed.

### Complex unknown DOM: all three succeed, cost differs

2026-09-08, three parallel Sonnet subagents, same task on `github.com/trending`
(extract top-5 repos + "stars today", then drive the date-range control to "This week"
by clicking, not by URL). **All three fully succeeded and returned identical data**, so
this is a cost comparison, not a capability one. Latency was measured under parallel CPU
contention — use the serial table above for latency.

| path | tool-output tokens | total agent tokens | tool calls | wall (contended) |
|---|---|---|---|---|
| raw CDP script | **5,086** | **70,879** | **10** | 9 s |
| playwright-cli | 8,432 | 80,276 | 35 | 36 s |
| agent-browser | 9,459 | 73,698 | 24 | 133 s |

**The finding that actually changes how to use all three: `eval` with a targeted DOM
query beat every accessibility-tree approach, by 10-40×.** A hand-rolled selector cost
500-900 B where a snapshot/`find` cost 9-40 KB, and it was *more* correct:

- **agent-browser `snapshot -i` omits static text.** The "stars today" figure is not an
  interactive element, so the snapshot cannot answer that half of the task at all —
  the agent had to fall back to `eval`. Do not assume a snapshot sees the page.
- **playwright-cli `find` elides sibling content with `...`**, which collapsed the repo
  names away from the star counts exactly when both were needed. `eval` fixed it in one
  shot.
- **The CDP path's whole discovery cost was one `outerHTML` dump of a single
  representative row** (11.3 KB of its 12.6 KB total), then structured JSON forever
  after. Peek at one element, not the list.
- playwright-cli also mirrors every action's snapshot to `.playwright-cli/*.yml`
  (105 KB across 4 files here). That is disk, not context — until someone `cat`s one.

So: snapshot to find *refs to click*, then `eval` to *read data*. Snapshotting to read is
the expensive mistake on every one of the three paths.

`snapshot -i` is only small on a small page: 74 B on `example.com` but 9.6 KB on a
marketing homepage. The "~200–400 tokens" claim in the vendor guide does not hold for
busy pages — use `find`/`get` when you already know the target.

## The 1-hour hang

**Never `out=$(agent-browser …)`.** A command that spawns a new daemon hands the daemon
the command-substitution pipe's write end, so the shell waits for an EOF that only
arrives when the daemon exits — at its **1-hour idle timeout**. Confirmed 2026-09-08:

| capture | daemon | result |
|---|---|---|
| direct | new | ok, 1.8 s |
| **`$(...)`** | **new** | **hang (killed at 60 s guard; would be ~1 h)** |
| `> file` | new | ok, 2.2 s |
| `$(...)` | warm | ok, 1.0 s |

Redirect to a file and read the file, or pre-warm the daemon once before capturing.
This is almost certainly what produced the 2026-09-04 numbers, and it hits any wrapper
script — the stall looks exactly like "the tool is slow".

**Cleanup is not automatic either.** `close` prints "✓ Browser closed" while the session
stays in `session list`; a killed script orphans its daemon *and* ~20 Chromes, and
leftover `~/.agent-browser/<session>.*` files make `session list`/`doctor` respawn them.
Killing a background task kills the wrapper, not the child `bash script.sh` — kill the
script by name too.

Use the wrapper in this directory rather than doing it by hand:

```bash
pwsh ~/.claude/skills/agent-browser/ab-cleanup.ps1                    # status (read-only, default)
pwsh ~/.claude/skills/agent-browser/ab-cleanup.ps1 -Session eval-ab-1 # close + kill daemon + purge its state
pwsh ~/.claude/skills/agent-browser/ab-cleanup.ps1 -All -DryRun       # show what a full nuke would do
pwsh ~/.claude/skills/agent-browser/ab-cleanup.ps1 -All               # nuke (prompts; -Force to skip)
```

It matches Chrome **only** on the private `--user-data-dir=…agent-browser-chrome-<uuid>`
profile, so it cannot touch the user's Chrome, the `.chrome-cdp-yunnan` CDP profile or
the `takanaka-watch` watcher — verified 2026-09-08 against 55 live Chrome processes
(kill set 11, zero overlap with either protected profile). `-Session` cannot kill that
session's browsers, because the profile dir is a random uuid with no session name in it;
it reports the leftovers and leaves them for `-All`.

## Pick by task shape

| Task | Use | How |
|---|---|---|
| The user named a tool ("use agent-browser", "use playwright") | **the tool they named** | see [When the user names the tool](#when-the-user-names-the-tool) |
| **Read a page you are not logged into** | **no browser at all** | `curl` first; on 403/302/000 retry with `curl_cffi`: `requests.get(url, impersonate="chrome")`. 0.1–1.3 s. See [No browser needed](#no-browser-needed) |
| Read text off a page that needs the login | CDP `innerText` | `connectOverCDP('http://127.0.0.1:9333')` → `page.evaluate(() => document.body.innerText)`. 1.4 KB, vs 28 KB for a snapshot |
| Recurring, on a timer, or selectors already known | hand-written CDP script | connect to `:9333`, own page, parse, close. **0.24 s / 129 B** on `example.com` (n=10, 2026-09-08); still cheapest, but only ~2× ahead of agent-browser now, not 100× |
| Unknown web page, must click or fill, needs the real login **and there is no debug port** | `playwright-cli` extension mode | `playwright-cli attach --extension=chrome`, then `playwright-cli -s=chrome <goto\|snapshot\|click\|fill>`. goto 1.07 s, snapshot 0.95 s / 779 B (41.6 KB on a busy page) — slowest of the three, pick it for the no-port login, not for speed. `tab-new` first so you never drive a tab the user is in; `detach` when done, never `close` |
| **Electron desktop app** (Slack, VS Code, Discord, Figma, Notion, Spotify) | **agent-browser** | [below](#electron-desktop-apps) — nothing else here does this |
| **Standalone API client derived from a site's traffic** | **agent-browser** | `agent-browser skills get derive-client` |
| **Cloud browser** (Vercel Sandbox microVM, AWS Bedrock AgentCore) | **agent-browser** | `agent-browser skills get vercel-sandbox` / `agentcore` |
| Structured QA / dogfood sweep of a web app | agent-browser, budgeting ~2 s per navigation | `agent-browser skills get dogfood` |

Port **9333** is the logged-in CDP profile. Port **9334** belongs to a watcher — leave it alone.
Confirm **9333 is actually listening** before routing to it; it has been found down while
Chrome was running, and a script that assumes it silently fails.

## No browser needed

A bot wall is usually a **TLS fingerprint** problem, not a site that needs a browser.
Measured 2026-09-08, plain `curl` → `curl_cffi` with `impersonate="chrome"`:

- `l-tike.com` (Akamai): `000` after 25 s → **200, 104 KB, 0.1 s**
- `iherb.com` search (PerimeterX): `403` → **200, 2.6 MB, 0.8 s**
- `tradead.tixplus.jp`: `302` → **200, 158 KB, 1.3 s**

So try that **before** opening anything. Two caveats measured the same day:

- A Cloudflare **managed challenge** is real and no fingerprint passes it
  (`travel.state.gov` stayed challenged across five impersonation profiles, and after
  warming `__cf_bm` on the origin root). That case needs `:9333`.
- Some shields answer with a **success status and no content** — Booking.com returns
  `202` with 3.9 KB. Check the body length, not the status code.

Full measurements and the challenge-detection snippet: `~/Code/CURL.md`.

## When the user names the tool

Run the tool they named. State the measured cost in one sentence and offer the faster path once; if they don't take it, proceed with what they asked for.

Never swap in a different tool and report the result as if you had used theirs. A slower tool the user chose is not a failure condition — silently substituting is.

## Electron desktop apps

The non-obvious part: **an already-running Electron app exposes no debug port.** Quit it fully and relaunch with the flag, or nothing will be listening.

```bash
# 1. Find the exe (paths vary by app and installer)
find "$LOCALAPPDATA" -maxdepth 3 -iname '*.exe' 2>/dev/null \
  | grep -iE 'slack|discord|figma|notion|spotify|Code\.exe'

# 2. Quit the app, then relaunch it with a debug port
"$LOCALAPPDATA/slack/slack.exe" --remote-debugging-port=9222

# 3. Drive it
agent-browser connect 9222
agent-browser snapshot -i          # accessibility refs (@e5) for clicking
agent-browser get text <selector>  # or plain CDP on :9222 for a pure read
```

Once the app is on a CDP port, a raw CDP script works too and is far cheaper — use `snapshot` only while you still need refs. `agent-browser skills get electron` (or `slack`) for the full guide.

## Before running any agent-browser command

Load the version-matched guide. This file ships with the CLI and cannot change between releases:

```bash
agent-browser skills get core          # workflows, patterns, troubleshooting
agent-browser skills get core --full   # + full command reference
agent-browser skills list              # everything on the installed version
```

## Maintenance

`npm i -g agent-browser && agent-browser install` overwrites this file with the vendor stub. It is tracked in the `~/.claude/skills` git repo — restore with `git checkout -- agent-browser/SKILL.md`. Re-measure the latency after an upgrade and update the number above.
