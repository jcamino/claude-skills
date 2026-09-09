# claude-skills

Personal [Claude Code](https://claude.com/claude-code) skills. This repo *is*
`~/.claude/skills`, so the working copy is what Claude actually loads — there is
no build or sync step.

Private on purpose: several skills hardcode this machine's paths
(`C:\Users\jcamino\...`) and personal hostnames.

## Skills

| Skill | What it does |
| --- | --- |
| `agent-browser` | Wrapper notes for the agent-browser CLI. Currently carries a local override telling Claude *not* to reach for it — measured ~3 min per navigation on this machine. |
| `build-japan` | Rebuild the japan site from markdown, diff the built output, verify in a real browser at mobile width. |
| `claude-fleet` | Launch N Claude Code sessions on Windows via `launch.ps1`, scrubbing the inherited `CLAUDE_CODE_CHILD_SESSION` markers so spawned sessions keep their transcripts. |
| `declaude` | Copy-editor pass that finds LLM-sounding prose and proposes plainer rewrites, via Gemini through the `agy` CLI. Never changes facts, numbers, names or quotes. |
| `hotel-room-search` | Room-level hotel search — bed configuration, free-cancellation deadlines, thin holiday availability. Scripts scrape Booking.com and Airbnb over CDP. |
| `researching-purchases` | Online purchase research: price, stock, sizing, compatibility, delivery against a deadline. |
| `scripted-booking` | Drives real booking funnels with a scripted browser so card data never enters agent context. Stops short of payment and reports cancellation terms first. |

Not tracked here: `ui-ux-pro-max` and `web-design-guidelines` are symlinks into
`~/.agents/skills` and belong to their upstreams.

## Layout

Each skill is a directory with a `SKILL.md` carrying YAML frontmatter
(`name`, `description`, optionally `allowed-tools` / `hidden`). Supporting
scripts and reference docs sit alongside it and are referenced by relative path
from `SKILL.md`.
