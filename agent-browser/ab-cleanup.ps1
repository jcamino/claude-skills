<#
.SYNOPSIS
  Status and cleanup for agent-browser, which does not clean up after itself.

.DESCRIPTION
  Works around two agent-browser 0.36.0 bugs found 2026-09-08:
    1. `close` prints "Browser closed" but the session stays in `session list`.
    2. A killed script orphans its daemon AND its Chrome processes; leftover
       ~/.agent-browser/<session>.* files make `session list` / `doctor` respawn them.

  Chrome processes are matched ONLY by the agent-browser private profile pattern
    --user-data-dir=<temp>\agent-browser-chrome-<uuid>
  so the user's own Chrome, the .chrome-cdp-yunnan CDP profile and the
  takanaka-watch watcher can never be hit.

.EXAMPLE
  pwsh ab-cleanup.ps1                      # status only (default, read-only)
  pwsh ab-cleanup.ps1 -Session eval-ab-1   # clean one session
  pwsh ab-cleanup.ps1 -All                 # nuke every agent-browser daemon/browser/state
  pwsh ab-cleanup.ps1 -All -DryRun         # show what -All would do
#>
[CmdletBinding()]
param(
  [string]$Session,
  [switch]$All,
  [switch]$DryRun,
  [switch]$Force,
  # Sessions whose state files -All must never delete. These are long-lived bindings
  # belonging to the user / other sessions; killing the process is fine, but deleting
  # their remembered-tab state loses information this tool did not create.
  [string[]]$Keep = @('default','happy-cf'),
  [switch]$PurgeKept
)

$StateDir    = Join-Path $HOME '.agent-browser'
$ProfileGlob = 'agent-browser-chrome-'

function Get-AbDaemons {
  Get-Process -Name 'agent-browser*' -ErrorAction SilentlyContinue
}

function Get-AbChromes {
  Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -match [regex]::Escape($ProfileGlob) }
}

function Get-AbSessions {
  if (-not (Test-Path $StateDir)) { return @() }
  Get-ChildItem $StateDir -File -ErrorAction SilentlyContinue |
    ForEach-Object { $_.BaseName } | Sort-Object -Unique
}

function Show-Status {
  $d = @(Get-AbDaemons); $c = @(Get-AbChromes); $s = @(Get-AbSessions)
  Write-Host ""
  Write-Host "agent-browser status" -ForegroundColor Cyan
  Write-Host "  daemons          : $($d.Count)"
  Write-Host "  chrome processes : $($c.Count)"
  $sList = if ($s.Count) { $s -join ', ' } else { '(none)' }
  Write-Host "  session state    : $($s.Count) -> $sList"
  if ($d.Count) { $d | ForEach-Object { Write-Host "    daemon pid $($_.Id)" -ForegroundColor DarkGray } }
  Write-Host ""
  # A session with state files but no daemon will be respawned by `session list`.
  $stale = $s | Where-Object { $_ -ne 'default' -and $_ -ne 'happy-cf' }
  if ($stale -and -not $d.Count -and $c.Count) {
    Write-Host "  NOTE: chrome processes alive with no daemon = orphans. Run with -All." -ForegroundColor Yellow
  }
}

function Stop-Things {
  param([object[]]$Daemons, [object[]]$Chromes, [string[]]$Files)

  if ($DryRun) {
    Write-Host "DRY RUN — nothing will be killed or deleted" -ForegroundColor Yellow
    $Daemons | ForEach-Object { Write-Host "  would kill daemon pid $($_.Id)" }
    $Chromes | ForEach-Object { Write-Host "  would kill chrome pid $($_.ProcessId)" }
    $Files   | ForEach-Object { Write-Host "  would delete $_" }
    return
  }

  foreach ($p in $Daemons) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
  foreach ($p in $Chromes) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Seconds 2
  foreach ($f in $Files) { Remove-Item $f -Force -ErrorAction SilentlyContinue }

  Write-Host "killed $($Daemons.Count) daemon(s), $($Chromes.Count) chrome proc(s), removed $($Files.Count) state file(s)" -ForegroundColor Green
}

if ($All) {
  $d = @(Get-AbDaemons); $c = @(Get-AbChromes)
  $f = @()
  $skipped = @()
  if (Test-Path $StateDir) {
    foreach ($item in Get-ChildItem $StateDir -File -ErrorAction SilentlyContinue) {
      if (-not $PurgeKept -and $Keep -contains $item.BaseName) { $skipped += $item.Name; continue }
      $f += $item.FullName
    }
  }
  if ($skipped.Count) {
    Write-Host "protected (not deleted): $($skipped -join ', ')  [use -PurgeKept to override]" -ForegroundColor DarkCyan
  }

  if (-not $DryRun -and -not $Force) {
    Write-Host "About to kill $($d.Count) daemon(s), $($c.Count) chrome proc(s) and delete $($f.Count) state file(s)." -ForegroundColor Yellow
    $ans = Read-Host "Proceed? (y/N)"
    if ($ans -ne 'y') { Write-Host "aborted"; exit 1 }
  }
  Stop-Things -Daemons $d -Chromes $c -Files $f
  Show-Status
  exit 0
}

if ($Session) {
  # Graceful first: let the CLI try, then take the state file out so nothing respawns.
  & agent-browser --session $Session close *> $null
  $pidFile = Join-Path $StateDir "$Session.pid"
  $d = @()
  if (Test-Path $pidFile) {
    $sessionPid = (Get-Content $pidFile -Raw).Trim()
    if ($sessionPid -match '^\d+$') {
      $p = Get-Process -Id ([int]$sessionPid) -ErrorAction SilentlyContinue
      if ($p) { $d = @($p) }
    }
  }
  $f = @()
  if (Test-Path $StateDir) {
    $f = @(Get-ChildItem $StateDir -File -Filter "$Session.*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
  }
  # Session-scoped: kill only this session's daemon. Its Chrome cannot be attributed
  # by command line (the profile dir is a random uuid), so orphaned browsers are left
  # for -All. Report them rather than guessing.
  Stop-Things -Daemons $d -Chromes @() -Files $f
  $c = @(Get-AbChromes)
  if ($c.Count) {
    Write-Host "note: $($c.Count) agent-browser chrome proc(s) still running; they cannot be mapped to a session. Use -All to clear." -ForegroundColor Yellow
  }
  Show-Status
  exit 0
}

Show-Status
Write-Host "usage: ab-cleanup.ps1 [-Session <name>] [-All] [-DryRun] [-Force]" -ForegroundColor DarkGray
