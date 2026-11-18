# claude-skills

Personal [Claude Code](https://claude.com/claude-code) skills. This repo *is*
`~/.claude/skills`, so the working copy is what Claude actually loads — there is
no build or sync step.

Several skills hardcode this machine's paths (`C:\Users\jcamino\...`), ports and
local tools, so treat them as examples to adapt rather than drop-in installs.

## Skills

| Skill | What it does |
| --- | --- |
| `agent-browser` | The browser router: picks curl_cffi, a CDP script, `pb`, Patchright, agent-browser or playwright-cli by task shape, and covers what only agent-browser does (Electron apps, cloud browsers, deriving an API client). |
| `build-japan` | Rebuild the japan site from markdown, diff the built output, verify in a real browser at mobile width. |
| `claude-fleet` | Launch N Claude Code sessions on Windows via `launch.ps1`, scrubbing the inherited `CLAUDE_CODE_CHILD_SESSION` markers so spawned sessions keep their transcripts. |
| `declaude` | Copy-editor pass that finds LLM-sounding prose and proposes plainer rewrites, via Gemini through the `agy` CLI. Never changes facts, numbers, names or quotes. |
| `hotel-room-search` | Room-level hotel search — bed configuration, free-cancellation deadlines, thin holiday availability. Scripts scrape Booking.com and Airbnb over CDP. |
| `icloud-passwords` | Unlocks the iCloud Passwords Chrome extension with no human: reads the capture-protected code from iCloud's helper window by UI Automation and types it, fills saved logins, and reconnects an RDP-disconnected session via the UAC broker. |
| `otp-fetch` | Arms an IMAP IDLE listener before a site sends an emailed one-time code, then prints the code. Code in `scripts/otp.js` (`npm ci` there first). |
| `pb` | Persistent Patchright browser driven by short shell commands (`~/bin/pb`), for interactive flows and checkouts; card typed from the secrets file, never shown. Stable copy of `~/Code/buy/browserbench/tools/pb.py`. |
| `researching-purchases` | Online purchase research: price, stock, sizing, compatibility, delivery against a deadline. |
| `scripted-booking` | Drives real booking funnels with a scripted browser so card data never enters agent context. Places live orders on the user's in-session "buy it"; unattended runs stop short of payment unless a human-made `ARMED` file exists. Reports cancellation terms first. |
| `scripting-browser-workflows` | Turns a workflow driven once by hand into replayable code: a recipe of what was observed, scripts for the no-browser / CDP / CLI tiers, and a bench that fails them on a page that changed. Ships an offline fixture site carrying nine real traps. |

Not tracked here: `ui-ux-pro-max` and `web-design-guidelines` are symlinks into
`~/.agents/skills` and belong to their upstreams.

## Layout

Each skill is a directory with a `SKILL.md` carrying YAML frontmatter
(`name`, `description`, optionally `allowed-tools` / `hidden`). Supporting
scripts and reference docs sit alongside it and are referenced by relative path
from `SKILL.md`.
