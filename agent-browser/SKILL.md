---
name: agent-browser
description: Use when a task needs a real browser or an Electron desktop app on this machine - opening pages, filling forms, clicking, screenshots, scraping, logging in, QA or dogfood sweeps, Slack/VS Code/Discord/Figma automation, deriving a standalone API client from a site's own traffic, or cloud browsers (Vercel Sandbox, AWS AgentCore). Also use when choosing between agent-browser, a raw CDP script, and playwright-cli.
allowed-tools: Bash(agent-browser:*), Bash(npx agent-browser:*)
hidden: true
---

# agent-browser

`agent-browser` is one of three browser paths on this machine. This file routes between them and covers the cases only agent-browser can do. It does not replace the CLI's own guides.

**Measured here 2026-09-04:** agent-browser takes **~184 s to open `example.com`** and 39 s to snapshot it. The latency is the tool, not the page. That number decides the table below. It is a cost, not a ban.

## Pick by task shape

| Task | Use | How |
|---|---|---|
| The user named a tool ("use agent-browser", "use playwright") | **the tool they named** | see [When the user names the tool](#when-the-user-names-the-tool) |
| Read text off a page | CDP `innerText` | `connectOverCDP('http://127.0.0.1:9333')` → `page.evaluate(() => document.body.innerText)`. 1.4 KB, vs 28 KB for a snapshot |
| Recurring, on a timer, or selectors already known | hand-written CDP script | connect to `:9333`, own page, parse, close. ~1.4 s per run |
| Unknown web page, must click or fill, needs the real login | `playwright-cli` extension mode | `playwright-cli attach --extension=chrome`, then `playwright-cli -s=chrome <goto\|snapshot\|click\|fill>`. `detach` when done, never `close` |
| **Electron desktop app** (Slack, VS Code, Discord, Figma, Notion, Spotify) | **agent-browser** | [below](#electron-desktop-apps) — nothing else here does this |
| **Standalone API client derived from a site's traffic** | **agent-browser** | `agent-browser skills get derive-client` |
| **Cloud browser** (Vercel Sandbox microVM, AWS Bedrock AgentCore) | **agent-browser** | `agent-browser skills get vercel-sandbox` / `agentcore` |
| Structured QA / dogfood sweep of a web app | agent-browser, budgeting ~3 min per navigation | `agent-browser skills get dogfood` |

Port **9333** is the logged-in CDP profile. Port **9334** belongs to a watcher — leave it alone.

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
