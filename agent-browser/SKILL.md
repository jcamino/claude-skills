---
name: agent-browser
description: Use when a task will fetch, read, scrape, click, fill or log into a web page, or drive an Electron desktop app on this machine - including deciding whether a browser is needed at all. Covers screenshots, QA and dogfood sweeps, Slack/VS Code/Discord/Figma automation, deriving a standalone API client from a site's own traffic, and cloud browsers (Vercel Sandbox, AWS AgentCore). Also use when choosing between curl_cffi, a raw CDP script, an own-browser Playwright script, Patchright, agent-browser, and playwright-cli - and whenever the user says "patchright" or "stealth", or a site is behind DataDome, Kasada, Akamai or PerimeterX.
allowed-tools: Bash(agent-browser:*), Bash(npx agent-browser:*), Bash(playwright-cli:*), Bash(curl:*), Bash(python:*), Bash(pwsh:*), Bash(bash ~/.claude/skills/agent-browser/preflight.sh)
hidden: true
---

# agent-browser

Six browser paths live on this machine (`pb` has its own skill). This file routes between them and covers the
cases only agent-browser can do. It does not replace the CLI's own guides.

> **"Patchright" means Patchright. It is not Playwright.** It is a separate,
> already-installed Python package (`patchright` 1.63, `from patchright.sync_api import
> sync_playwright`) that patches the detection leaks Playwright has. Writing
> `from playwright…`, or reaching for playwright-cli, when the user asked for Patchright is
> substituting a tool, and on the sites they ask for it on it fails. See [Patchright](#patchright).

> **iCloud Passwords locked or asking for a code in the main Chrome? Never ask Javier to RDP
> in for it.** Run the `icloud-passwords` skill (`python ~/.claude/skills/icloud-passwords/scripts/icloud.py unlock --title PART`):
> it reads the capture-protected code by UI Automation and types it. `pick USERNAME` fills a
> saved login. The extension is only in the main profile, not in pb/Patchright or CDP profiles.

## Preflight — run this first

**Ports and installs on this box drift, and this file has rotted before.** On
2026-09-09 the routing table still named 9333 as the logged-in CDP port; 9333 was
dead and the logged-in profile had moved to 9222. A script that assumed 9333 failed
silently. Do not trust the numbers below over the output of:

```bash
bash ~/.claude/skills/agent-browser/preflight.sh   # ~19 s (it opens real tabs)
```

It enumerates every Chrome-owned listening port with its profile, **opens a real tab on
each and evaluates `1+1` in it**, checks for Chrome version skew, and lists driver
availability and agent-browser leftovers.

**Run it when your route needs a port** — the CDP-script, `agent-browser connect` and
playwright-cli rows. **Skip it when your route does not**: `curl_cffi`, and the
own-browser script and `agent-browser open` paths, which launch their own browser. Do not
spend 19 s discovering the state of a port you were never going to use.

**A port that answers is not a port that works.** `/json/version` replies perfectly from
a browser whose every renderer dies. That is why preflight opens a tab instead of
probing. Trust its `USABLE` / `BROKEN` verdict, not a port number from any document.

**There is deliberately no port table here.** Every version of one has rotted within
days — a later run found 9345 and 9353 live and usable, documented nowhere. Only three
facts about ports are stable enough to write down:

- **9334 is the `takanaka-watch` watcher. Never drive it, never kill it.**
- **9333 is dead.** `~/.claude/CLAUDE.md` and `~/Code/CURL.md` named it as "the
  logged-in CDP profile" for days after it moved; both were corrected 2026-09-09 to
  resolve the port instead. If any doc hands you a port number, distrust it.
- The logged-in profile `~/.chrome-cdp-yunnan` runs **`--headless=new`**, not headful,
  and as of 2026-09-09 sits on 9222 **BROKEN** (see version skew below). Do not launch
  Electron apps on 9222 while it is occupied — pick a free port such as 9223.

### Chrome version skew — the silent killer

If a CDP browser reports an **older** build than the `chrome.exe` on disk, Chrome
auto-updated underneath it. The old browser process spawns renderers from the new
binary and they die instantly with `Inspector.targetCrashed`, while `/json/version`,
`/json/list` and tab creation all still appear to succeed. `--noerrdialogs` on a
headless browser means it fails silently.

That is the exact state of 9222 today: browser `151.0.7922.174`, disk `152.0.7977.76`.
**Fix: quit that Chrome and relaunch it** — its command line already carries
`--restore-last-session`. Nothing else recovers it. Preflight now flags this.

### Raw CDP from Python: suppress the Origin header

Chrome 111+ rejects a CDP WebSocket handshake that carries an `Origin` header with
**403 Forbidden**, and `websocket-client` sends one by default:

```python
from websocket import create_connection
ws = create_connection(target["webSocketDebuggerUrl"], suppress_origin=True)
```

Verified 2026-09-09. Without it the hand-written-CDP-script path fails immediately.
Also note `/json/new` requires **PUT**, not GET, on current Chrome (`405` otherwise).

## Pick by task shape

| Task | Use | How |
|---|---|---|
| The user named a tool ("use agent-browser", "use playwright") | **the tool they named** | see [When the user names the tool](#when-the-user-names-the-tool) |
| **Read a page you are not logged into** | **no browser at all** | `curl`; on 403/302/000 retry with `curl_cffi`. 0.1–1.3 s. See [No browser needed](#no-browser-needed) |
| Read text off a page that needs the login | CDP `innerText` | connect to the **live** logged-in port from preflight → `page.evaluate(() => document.body.innerText)`. 1.4 KB, vs 28 KB for a snapshot |
| **Drive a site interactively**: a shop, checkout or booking form, a login, a site's own search form, any multi-step flow on a page whose structure is not known yet, including bot-walled ones | **`pb`** (the `pb` skill) | One Patchright Chrome stays open; short commands (`pb open`, `pb view`, `pb click`, `pb fill`, `pb text`, `pb card`). Fastest and cheapest driver measured here (2026-11-15/16): a blind checkout in 1:22 to 3:00 with any model, about 3x fewer tokens than Claude in Chrome, and it types cards without showing them. Needs no CDP port |
| **Public page, one or two clicks, no login** | agent-browser, or an own-browser Playwright script | Neither needs a CDP port. `agent-browser --session <name> open <url>` then `find text "<label>" click` is fewest calls (~6 s total); a Python `chromium.launch()` script is better when the logic is complex or you want zero daemon. See [Own-browser script](#own-browser-script). Anything longer: `pb` |
| **Bot-walled page in a script** (DataDome, Kasada, Akamai/PerimeterX past the read), or the user said "patchright"/"stealth" | **Patchright** | interactively, that is `pb` (it is Patchright). For a script, own headful Chrome with a persistent profile. See [Patchright](#patchright) |
| Recurring, on a timer, or selectors already known | hand-written CDP script | connect to the live port, own page, parse, close. Cheapest per run once selectors are known |
| Unknown page, must click/fill, needs the real login **and no debug port is listening** | `playwright-cli` extension mode | [below](#playwright-cli) |
| **Electron desktop app** (Slack, VS Code, Discord, Figma, Notion, Spotify) | **agent-browser** | [below](#electron-desktop-apps) — nothing else here does this |
| **Standalone API client derived from a site's traffic** | **agent-browser** | `agent-browser skills get derive-client` |
| **Cloud browser** (Vercel Sandbox microVM, AWS Bedrock AgentCore) | **agent-browser** | `agent-browser skills get vercel-sandbox` / `agentcore` |
| Structured QA / dogfood sweep of a web app | agent-browser | `agent-browser skills get dogfood` |

These rows describe **task shape only**. If the user named a tool, row 1 wins and the
rest of the table does not apply — go to [When the user names the tool](#when-the-user-names-the-tool)
rather than concluding from a row's conditions that their tool is disallowed.

## No browser needed

A bot wall is usually a **TLS fingerprint** problem, not a site that needs a browser.
Try `curl_cffi` **before** opening anything:

```python
from curl_cffi import requests
r = requests.get(url, impersonate="chrome")
```

Measured plain `curl` → `curl_cffi`: `l-tike.com` (Akamai) `000` after 25 s → **200 in
0.1 s**; `uk.iherb.com` search (PerimeterX) `403` → **200, 2.66 MB, 1.3 s**
(re-confirmed 2026-09-09); `tradead.tixplus.jp` `302` → **200**.

Two ways a "success" lies:

- A Cloudflare **managed challenge** can arrive as **HTTP 200 carrying the challenge
  page**. Grep the body for `Just a moment` before trusting a 200. No fingerprint
  passes it (`travel.state.gov` stayed challenged across five profiles) — that case
  needs the real logged-in Chrome.
- Some shields answer with a success status and **no content** — Booking.com returns
  `202` with 3.9 KB. **Check body length, not the status code.**

Full measurements and the challenge-detection snippet: `~/Code/CURL.md`.

## Own-browser script

For a public page that must be *driven* rather than read, launch your own browser.
No CDP port, no daemon, no shared state with the user's Chrome, and it cleans itself up.

**Either language works now.** Python (`import playwright`) has always resolved. Node
could not — `require('playwright')` outside the global npm root died with
`Cannot find module 'playwright'` — until `NODE_PATH` was set to the global
`node_modules` at User scope on 2026-09-09. Verified after the fix: `chromium.launch()`
→ page → title in **1.8 s**.

Two caveats on that fix: a **process only picks up the new `NODE_PATH` when it starts**,
so a long-running session predating the change still needs the
`NODE_PATH="$(npm root -g)"` prefix; and if `require('playwright')` ever fails again,
check the variable survived rather than assuming the package is missing.

Write the script with the Write tool (never a heredoc — backslashes in selectors and
regexes get eaten), then run it. A two-page click-through measures **8.9–10.2 s cold,
3.0 s warm** — on repeat runs this is competitive with the CDP row.

**Python stdout here is `cp1252`, so `print()`ing scraped text crashes.** Verified
2026-09-09: `print('Next →')` dies with
`UnicodeEncodeError: 'charmap' codec can't encode character '→'`. Every real page
has an arrow, em-dash or smart quote, so this hits the *normal* case, not the edge case —
and it strikes at the end, after all the browser work succeeded. Either run with
`PYTHONIOENCODING=utf-8`, or write results to a file with an explicit encoding and read
that:

```python
import json, io
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    b = pw.chromium.launch()                 # own browser: no port, no daemon
    pg = b.new_page()
    pg.goto("https://example.com/", wait_until="domcontentloaded")

    rows = pg.eval_on_selector_all(          # eval to READ - never snapshot to read
        "div.quote",
        "els => els.map(e => ({t: e.querySelector('.text').innerText,"
        "                      a: e.querySelector('.author').innerText}))")

    nxt = pg.locator("li.next a")            # target by the control, then wait for nav
    with pg.expect_navigation():
        nxt.click()
    after = pg.url

    b.close()                                # self-cleaning; verify 0 ms-playwright procs

with io.open("out.json", "w", encoding="utf-8") as f:
    json.dump({"rows": rows, "url_after": after}, f, ensure_ascii=False)
```

`expect_navigation()` matters: a bare `.click()` returns before the next page exists, so
the read that follows silently scrapes the old DOM.

## Patchright

Python `patchright` 1.63 is installed (`pip`, plus `patchright.exe` in Python313\Scripts).
It is a drop-in fork of Playwright's Python API: **change the import, nothing else.**

```python
from patchright.sync_api import sync_playwright   # NOT playwright.sync_api

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=PROFILE,        # a per-site dir you keep; cookies/captcha clears persist
        channel="chrome",             # the real installed Chrome, not bundled Chromium
        headless=False,               # headful - headless is what gets flagged
        no_viewport=True)             # no fixed viewport fingerprint
    pg = ctx.new_page()
    ...
    ctx.close()
```

Smoke-tested 2026-10-21: example.com in **3.2 s**, `navigator.webdriver` → `False`.

Where it is the only thing that has worked (each failed on playwright-cli attach, plain
Playwright and agent-browser first):

- **Zocdoc** (DataDome) — profile `%TEMP%\onemed\zd\profile` (lives in %TEMP%, so it can
  vanish; its driver `zd.py` already has, as of 2026-10-21). Details in the `health`
  project memory `zocdoc-access`.
- **Twitch** (Kasada, error 5025) — profile `~/.patchright-twitch`, plus humanized
  mouse/keys; reuse `Human` + `login()` from `~/Code/buy/workflows/twitch-prime-sub/twitch_prime.py`.
  Details in the `buy` project memory `twitch-access`.

Other working Patchright scripts to copy from before writing a new one (found 2026-10-21):
Best Buy / Walgreens / Mouser in `~/Code/buy/sr626_scripts/` (`bb_pw.py` is the shared
helper), Robinhood in `~/Code/taxes/robinhood/rh_*.py`, and
`~/Code/flights/workflows/seat3u/dx_solver.py`.

Rules:

- Use **one persistent profile per site** and reuse it. A captcha solved once in the
  window persists in the profile; a fresh profile means a fresh captcha.
- Patchright has **no Node package installed here**. If you need it from Node, say so; do
  not quietly fall back to `require('playwright')`.
- Headful means a window opens on Javier's desktop. That is expected; do not "fix" it to
  headless.
- The cp1252 `print()` trap below applies here too — run with `PYTHONIOENCODING=utf-8`.

## Traps that cost hours

**Never `out=$(agent-browser …)`.** A command that spawns a new daemon inherits the
command-substitution pipe's write end, so the shell waits for an EOF that only arrives
at the daemon's **1-hour idle timeout**. Redirect to a file and read the file, or
pre-warm the daemon first.

| capture | daemon | result |
|---|---|---|
| direct | new | ok, 1.8 s |
| **`$(...)`** | **new** | **hang (~1 h)** |
| `> file` | new | ok, 2.2 s |
| `$(...)` | warm | ok, 1.0 s |

This is what produced the bogus "agent-browser takes 184 s to open a page" figure that
sat in this file for four days. The stall looks exactly like "the tool is slow".

**Always pass `--session <task-name>`.** The default session is shared machine-wide and
persists across conversations, so two agents on this box will fight over one page — a
foreign session appearing mid-run is normal here. The vendor guide's
`export AGENT_BROWSER_SESSION=…` is **useless to an agent**: shell state does not survive
between tool calls, so it silently does nothing. Per-command `--session` is the only form
that works. `agent-browser session id --scope worktree --prefix <task>` gives a stable
name and is one of the few subcommands safe inside `$(...)` — it spawns no daemon
(verified: 563 ms, daemon count unchanged).

**agent-browser cleanup is not automatic**, but check the right thing. On 0.36.0 `close`
does clear `session list` — the residue is the **state files** left in `~/.agent-browser/`,
which make `session list`/`doctor` respawn a daemon later. An agent that checks
`session list` and sees it empty will wrongly conclude the machine is clean. Check the
state files. A killed script orphans its daemon *and* ~20 Chromes; killing a background
task kills the wrapper, not the child `bash script.sh` — kill the script by name too.

```bash
pwsh ~/.claude/skills/agent-browser/ab-cleanup.ps1                    # status (read-only, default)
pwsh ~/.claude/skills/agent-browser/ab-cleanup.ps1 -Session eval-ab-1 # close + kill daemon + purge its state
pwsh ~/.claude/skills/agent-browser/ab-cleanup.ps1 -All -DryRun       # show what a full nuke would do
pwsh ~/.claude/skills/agent-browser/ab-cleanup.ps1 -All               # nuke (prompts; -Force to skip)
```

It matches Chrome **only** on the private `--user-data-dir=…agent-browser-chrome-<uuid>`
profile, so it cannot touch the user's Chrome, the `.chrome-cdp-yunnan` CDP profile or
the `takanaka-watch` watcher — verified against 55 live Chrome processes (kill set 11,
zero overlap). `-Session` cannot kill that session's browsers (the profile dir is a
random uuid); it reports the leftovers and leaves them for `-All`.

**`session state: N` in the status output is often another session's, not yours.**
Never `-All` to tidy up after yourself — kill only what you started.

**`bc` is not installed** in Git Bash here. For timing use `date +%s%3N` with shell
integer arithmetic, or curl's `%{time_total}`.

## Reading vs clicking — the rule that saves the most

**`eval` to read data. Never snapshot to read.** Snapshotting in order to read is the
expensive mistake on every path. A hand-rolled selector costs 500–900 B where a snapshot
costs 9–40 KB, and it is *more* correct:

**To click, try `find` before `snapshot`.** If you know the control's visible label,
`agent-browser find text "next" click` does it in **one call and ~10 B** (1.2 s including
the navigation). Reach for `snapshot -i` → `@ref` only when you *don't* know the label
and need to discover it — that is what the accessibility tree is for, and it costs
kilobytes.

- **agent-browser `snapshot -i` omits static text.** Anything that is not an interactive
  element is simply absent — a price or a star count cannot be read from it at all.
- **playwright-cli `find` elides sibling content with `...`**, which collapses names away
  from the values next to them exactly when you need both.
- **Discover with one `outerHTML` dump of a single representative row**, then read
  structured JSON forever after. **Peek at one element, not the list.**
- `snapshot -i` is only small on a small page: 74 B on `example.com`, 9.6 KB on a
  marketing homepage. The vendor guide's "~200–400 tokens" does not hold on busy pages.

## playwright-cli

Version on this machine: **0.1.19** (pin this when re-measuring; the numbers below are
worthless against a different build).

**`attach --extension=chrome` prints your live `PLAYWRIGHT_MCP_EXTENSION_TOKEN` in
plaintext on stdout**, inside the `connect.html?…&token=…` URL — straight into the
transcript, on every attach. Verified 2026-09-09. Redact it:

```bash
playwright-cli attach --extension=chrome 2>&1 | sed "s|$PLAYWRIGHT_MCP_EXTENSION_TOKEN|<TOKEN>|g"
```

(The token does **not** reach the `.yml` files — checked. Only stdout.)

Two modes. The guidance used to document only the first, which made the common case
unreachable.

**Attach mode** — its one irreplaceable trick: the real logged-in Chrome with **no debug
port**. `playwright-cli attach --extension=chrome`, then `playwright-cli -s=chrome <goto|snapshot|click|fill>`.
Run `tab-new` first so you never drive a tab the user is in, and **`tab-close <n>` your
own tab before you leave** or it sits in their Chrome forever. Finish with `detach`.

> **`tab-close` is not `close`.** `tab-close <n>` closes the one tab you opened — safe.
> `close` kills the whole session, which in attach mode is the user's real Chrome.
> In attach mode: `tab-close` yours, then `detach`. **Never `close`.**

**Own-browser mode** — `playwright-cli -s=<any-name> open <url>`, then `eval`/`click`.
`-s=` takes any session name, not just `chrome`. **End with `close`** — you opened it, so
there is nothing to detach from and `detach` would orphan a Chrome.

Either way, verify with `playwright-cli list` → `(no browsers)`. That is the
playwright-cli equivalent of `ab-cleanup.ps1`, and it is the only cleanup check there is.

Approval is skipped because `PLAYWRIGHT_MCP_EXTENSION_TOKEN` is a user env var (new
shells only).

Costs the latency table hides:

- **~1–1.5 s of Node boot on every invocation.** `playwright-cli list` against zero
  sessions takes 1.1–1.5 s doing no browser work at all, so a 4-command task costs ~10 s,
  not ~4 s. Measured `open` 3.4 s, `attach` 6.9 s, `eval` 1.5–2.5 s (2026-09-09).
- **`.playwright-cli/*.yml` is written to the current working directory.** `cd` to the
  scratchpad **before the first session command**, or it leaves untracked files in
  whatever repo you are in — including `~/.claude/skills`, which several sessions share.
  Send snapshot stdout to `/dev/null` and grep the file, never `cat` it.
- **`--raw` returns double-encoded JSON** (literal `\n` and `\"`). Prefer plain `eval`
  returning an object, or `--json`.

## Measured cost

Full tables, methodology and the history: **`benchmarks.md`** in this directory. The four
numbers that actually change a decision:

- **Ranking is stable**: raw CDP < agent-browser < playwright-cli, on both time and bytes.
  The spread is ~2–4×, not the 100× an older version of this file claimed.
- **Every shell-driven CLI call pays ~1–1.5 s of boot.** Count invocations, not just
  page operations — a 4-command playwright-cli task costs ~10 s.
- **Snapshot bytes are kilobytes on any real page** (74 B on `example.com`, 9.6–41.6 KB
  on a busy one). Never budget from the toy-page figure.
- **On a complex unknown DOM all three paths succeed and return identical data.** Tool
  choice here is a cost decision, not a capability one — so don't agonise over it.

## When the user names the tool

Run the tool they named. State the measured cost in one sentence and offer the faster
path once; if they don't take it, proceed with what they asked for.

Never swap in a different tool and report the result as if you had used theirs. A slower
tool the user chose is not a failure condition — silently substituting is.

Tools that sound alike are still different tools: **Patchright ≠ Playwright ≠
playwright-cli ≠ the Playwright MCP.** If the named tool's package seems missing, check
(`pip show patchright`) and say what you found. Do not decide the nearest lookalike will do.

## Electron desktop apps

The non-obvious part: **an already-running Electron app exposes no debug port.** Quit it
fully and relaunch with the flag, or nothing will be listening.

```bash
# 1. Find the exe (paths vary by app and installer)
find "$LOCALAPPDATA" -maxdepth 3 -iname '*.exe' 2>/dev/null \
  | grep -iE 'slack|discord|figma|notion|spotify|Code\.exe'

# 2. Quit the app, then relaunch it on a FREE port (9222 is the logged-in CDP profile —
#    check preflight before picking)
"$LOCALAPPDATA/slack/slack.exe" --remote-debugging-port=9223

# 3. Drive it
agent-browser connect 9223
agent-browser snapshot -i          # accessibility refs (@e5) for clicking
agent-browser get text <selector>  # or plain CDP for a pure read
```

Once the app is on a CDP port a raw CDP script works too and is far cheaper — use
`snapshot` only while you still need refs. `agent-browser skills get electron` (or
`slack`) for the full guide.

## Before running any agent-browser command

Load the version-matched guide. It ships with the CLI and changes between releases:

```bash
agent-browser skills get core          # workflows, patterns, troubleshooting
agent-browser skills get core --full   # + full command reference
agent-browser skills list              # everything on the installed version
```

Worth knowing it exists: `agent-browser read [url]` fetches agent-readable text in one
command, and `close --all` closes every session.

**Two things in that vendor guide are wrong for this machine — override them:**

- It teaches `cat <<'EOF' | agent-browser eval --stdin` (lines 267, 423). **Heredocs are
  blocked here** and mangle backslashes in selectors and regexes. Write the JS with the
  Write tool and redirect the file into `eval --stdin < script.js`, or use
  `eval -b <base64>`.
- Its very first command wraps agent-browser in `$(...)` (lines 29, 242). That is the
  1-hour-hang pattern — but `session id` specifically is daemon-free, so *that one line*
  is safe. Do not generalise it to any other subcommand.

## Maintenance

`npm i -g agent-browser && agent-browser install` overwrites this file with the vendor
stub. It is tracked in the `~/.claude/skills` git repo — restore with
`git checkout -- agent-browser/SKILL.md`.

Several sessions share this working tree and this file changes under you — it was edited
twice mid-task during the runs that produced it. Re-read it before acting on a detail you
read a while ago, and stage only files you touched.

**After any upgrade or machine change, re-run `preflight.sh`.** Every serious failure
this file has caused was a fact that drifted, not advice that was wrong — which is why
the durable facts live in the script and not in the prose.
