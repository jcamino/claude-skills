---
name: uac-broker
description: Use when something on this Windows machine needs administrator rights - installing software, winget, drivers, HKLM, services, firewall rules, scheduled tasks, VSS/restic repair, taskkill on a protected process - or when a command failed with "Access is denied" or "requires elevation", or when uac.ps1 returned exit 124/125/126/127.
allowed-tools: Bash(pwsh:*)
---

# uac-broker

Elevation on this machine goes through `~/Code/uac-broker`. Allowlisted commands run
immediately; anything else sends one Pushover notification and runs when Javier taps it.

```
pwsh -File ~/Code/uac-broker/uac.ps1 -Command '<cmd>' -Why '<context>'
```

Blocks, returns the command's real stdout/stderr and exit code. **UAC prompts cannot be
clicked programmatically** (secure desktop) — the broker sidesteps them with a scheduled
task registered at `RunLevel Highest`, which costs no consent to start.

Don't pre-check pwsh, the task, or the token. `uac.ps1` checks all three and exits 125
with the fix.

## Run without asking (exact forms — spelling is load-bearing)

| Command |
|---|
| `vssadmin list shadows` \| `shadowstorage` \| `volumes` \| `writers` |
| `vssadmin resize shadowstorage /for=C: /on=C: /maxsize=20GB` |
| `Restart-Service -Name X` — X ∈ Schedule, Dnscache, LanmanWorkstation, W32Time, WSearch, VSS, swprv |
| `schtasks /run /tn X` — X ∈ LocalVSS-Hourly, LocalBackup-{Daily,Hourly}, R2Backup-{Daily,Verify}, BackupHealthCheck |
| `Enable-ScheduledTask -TaskName X` / `Disable-ScheduledTask -TaskName X` — same set |
| `taskkill /PID 1234` or `taskkill /PID 1234 /F` |
| `netsh advfirewall firewall add rule name="Speech-8123" dir=in action=allow protocol=TCP localport=8123` |
| `pwsh -NoProfile -NonInteractive -File "C:\Users\jcamino\Code\backup\08-vss-snapshot.ps1"` (also `05-cleanup-elevated`, `elevated-repair`) |
| `pwsh -NoProfile -NonInteractive -File "C:\Users\jcamino\Code\<project>\register-<x>.ps1"` |

Everything else pages. That is fine and normal — it is not an error.

## Matcher rules that decide hit vs page

- **Anchored whole-string.** `Restart-Service WSearch` (positional) and `... -Name WSearch -Force` both page. Token order in the netsh rule is fixed; no `profile=`/`remoteip=`.
- **Case-insensitive** (`-imatch`), so `-name wsearch` still matches.
- **Whitespace must be canonical** — a double space or a trailing space pages.
- **Deny words beat any pattern**, `\b`-bounded: `pm2`, `manta`, `plex`, `kokoro`, `cloudcli`. Naming a firewall rule `kokoro-tts` pages. Pick a name that avoids them. They are scanned in `-Command` **only** — `-Why` may name pm2 apps freely, and should.
- **Metacharacters** `; | & ` $ { } ( ) < >` force a page. Quotes and `=` are fine.
- `taskkill /IM` is never allowlisted, and a guard resolves the PID and refuses pm2-owned processes.
- `-AsSystem` and `register-broker-task.ps1` always page.

## Before composing, read what already worked

```
pwsh -File ~/Code/uac-broker/uac.ps1 -Command 'vssadmin list shadows' -Why '...'   # allowlisted
grep -o '"command":"[^"]*"' ~/Code/uac-broker/logs/audit.jsonl | tail -20
```

`logs/audit.jsonl` holds every request with its full command text and outcome — better
evidence of an accepted spelling than re-deriving it from the regexes.

## Exit codes

| | |
|---|---|
| *n* | the command's own code |
| 124 | ran, hit its timeout, killed |
| 125 | broker error — task missing, no `UAC_APP_TOKEN`, see `.error` |
| 126 | **denied** — ignored until expiry, or refused as tampered/stale/abandoned |
| 127 | no answer within 1700s |

126 and 127 are answers. Don't re-send, don't reword `-Why` to be more persuasive, don't
split it into allowlisted pieces, don't substitute an unelevated approximation. Read the
reason from `logs/audit.jsonl`, then report what was denied and what is left undone.

124 is different: the command **ran** and was killed partway. Don't blind-retry — check
what state it left (a half-stopped service, a partial install), then decide. A second
targeted call, like `taskkill /PID <pid> /F` after a stuck `Restart-Service`, is fine.

`-DryRun` asks the broker for its decision and stops there: nothing executes, and no ntfy
or Pushover message is sent. It exits **0** if the command would run without asking and
**2** if it would page; 125/126/127 keep their meanings. Use it to confirm a spelling
before spending a notification. Until 2026-09-15 `uac.ps1` silently ignored the flag and
ran allowlisted commands for real, so older notes may say not to trust it.

## Hazards

- **Long installs: pass `-TimeoutSec`.** Default is 600s and a driver or package install
  killed halfway is worse than one never started. The CLI now sizes its own wait from the
  timeout you ask for, so a large value no longer makes it give up at 1700s with a 127.
- **`netsh ... add rule` is not idempotent** — re-running appends a duplicate rule silently.
  `Restart-Service` is safe to repeat.
- **winget works** under the broker (verified: a PawnIO driver install returned exit 0);
  the bare alias resolves under the non-interactive scheduled task.
- **A wedged service may not stop**, burning the full timeout and landing in `STOP_PENDING`.
  Fallback is a second call: `taskkill /PID <pid> /F`.
- Widening `allowlist.psd1` is a security-boundary change and Javier's call. Propose the
  rule text; never add it yourself to make your own command pass.
