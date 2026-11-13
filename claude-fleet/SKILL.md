---
name: claude-fleet
description: Use when Javier asks to start, spin up, or launch Claude Code sessions or instances on this Windows machine ("start N Claude instances", "spin up sessions with remote control", "claude fleet"), or to run a remote-control server for on-demand sessions.
---

# claude-fleet

Run the launcher; do not hand-roll `Start-Process` or run `claude` straight from a Bash tool call.

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\jcamino\.claude\skills\claude-fleet\launch.ps1" -Count 5
```

Options:
- `-Count N` number of sessions (default 5)
- `-Prefix name` Remote Control names become `name-1..N` (default `win-MMdd-HHmm`)
- `-Dir path` working directory for every session (default `C:\Users\jcamino\Code`)
- `-PermissionMode mode` default `bypassPermissions`
- `-StaggerSec s` pause between launches (default 2)
- `-Server -Capacity N` instead of windows, one `claude remote-control --spawn same-dir --capacity N` server that spawns sessions on demand from claude.ai/code
- `-Prompt text` first message for each window session. One line, no double quotes (Windows PowerShell 5.1 does not escape them for native programs, and the launcher refuses them); put anything longer in a file and prompt "Read <file> and do what it says." Scripts use this to start a session on a job, e.g. the Twitch Prime-sub job's repair session (`~/Code/buy/workflows/twitch-prime-sub`)

Each session runs `claude --remote-control '<name>' --permission-mode bypassPermissions` in a `-NoExit` PowerShell window, so it is interactive locally AND controllable from claude.ai/code. The script prints the window PIDs; stop a session by closing its window or `taskkill /PID <pid> /T /F` (never `/IM node.exe`, that kills pm2/plex).

## Why the launcher and not a bare `claude`

Anything started from inside a Claude Code session inherits that session's identity: `CLAUDECODE`, `CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_MESSAGING_SOCKET`/`_TOKEN`, `CLAUDE_CODE_BRIDGE_SESSION_ID`, `CLAUDE_PID`. A child-marked session turns transcript saving off (`--resume` cannot find it), ignores `--yes`, and hides some tools. `CLAUDE_CODE_CHILD_SESSION` is read with `Boolean()`, so setting it to `0` changes nothing; the launcher **removes** the whole list before spawning and refuses to launch if the marker is still present. Both the window path and `-Server` go through the same scrub.

The launcher also sets `CLAUDE_CODE_FORCE_SESSION_PERSISTENCE=1` (Claude Code skips the transcript suppression on it regardless of how a marker arrives), so every Claude launched by another Claude keeps its transcript. The same scrub + flag lives in `cloudcli-setup/start-cloudcli.cjs` (cc.<personal-domain>, the pm2 entry) and `C:\sandbox\omp\run-dev.ps1` (omp.<personal-domain>): pm2 and `Start-Process -Credential` both copy the launching Claude's environment into the server, which then forwards it to every session it spawns.

This is deliberately scoped to sessions Javier asks for by name. Subagents (Agent tool) run in-process, never pass through this script, and must not be "fixed" with a global env override in settings.json.

Report back: the names, the PIDs, and that they show at claude.ai/code within ~30 s.

## Keeping background sessions alive (idle-retire)

Window-mode sessions (the default above) are plain interactive processes, not daemon jobs, so they live until you close them. But `-Server` mode and any `claude --bg` session ARE daemon workers, and the background daemon idle-retires them: it sweeps every 60 s and kills a worker whose job has been idle past a compiled-in threshold — 8h for remote-control/bridged, 1h for plain, or 60 s whenever free RAM drops under 1 GB. Those thresholds are baked into `claude.exe` and are not configurable, so a session that goes quiet for 8h just vanishes (the conversation survives via `claude attach <id>` / `--resume`, the process and its Remote Control entry do not). This is the usual cause of "some of my rc Claudes keep dying".

To exempt daemon sessions from the idle rules, pin them:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\jcamino\.claude\skills\claude-fleet\pin.ps1"   # pins every live background session
```

Run it right after launching a `-Server` / `--bg` fleet. Pins persist in `~/.claude/jobs/pins.json` and the daemon honours them on every sweep, so pinning once is enough per session. A pinned session is still retired only as a last resort if free RAM stays under 1 GB after every non-pinned worker has been shed, so keep memory above ~1 GB (WSL is capped at 12 GB in `~/.wslconfig`). `pin.ps1 -List` shows current pins; `pin.ps1 -Unpin -Id <short>` removes one.
