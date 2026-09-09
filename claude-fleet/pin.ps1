# Pin background Claude sessions so the daemon never idle-retires them.
#
# The Claude Code background daemon sweeps every 60s and kills any `claude --bg`
# / daemon-spawned worker whose job has been idle past a compiled-in threshold:
# 8h for remote-control/bridged sessions, 1h for plain ones, or 60s whenever
# free RAM drops under 1 GB. Those thresholds live inside claude.exe and are not
# configurable. Pinning a session's short id in ~/.claude/jobs/pins.json exempts
# it from the idle rules (the low-memory last resort can still retire a pinned
# session only if RAM stays under 1 GB after every non-pinned worker is shed).
#
# Interactive window-mode sessions (what launch.ps1 spawns by default) are NOT
# daemon jobs and are already immune; this only matters for --bg and -Server.
#
#   powershell -ExecutionPolicy Bypass -File pin.ps1            # pin all live bg sessions
#   powershell -ExecutionPolicy Bypass -File pin.ps1 -Id a1b2c3d4,e5f6a7b8
#   powershell -ExecutionPolicy Bypass -File pin.ps1 -List      # show current pins
#   powershell -ExecutionPolicy Bypass -File pin.ps1 -Unpin -Id a1b2c3d4
param(
  [string[]]$Id,
  [switch]$Unpin,
  [switch]$List
)

$pinsFile = Join-Path $env:USERPROFILE '.claude\jobs\pins.json'
New-Item -ItemType Directory -Force -Path (Split-Path $pinsFile) | Out-Null

function Read-Pins {
  if (-not (Test-Path $pinsFile)) { return ,@() }
  try { $v = Get-Content -Raw $pinsFile | ConvertFrom-Json } catch { return ,@() }
  # PS turns a JSON array into an object[]; a single string stays a string.
  if ($null -eq $v) { return ,@() }
  # Leading comma forces an array return even for 0/1 element (PS unwraps otherwise).
  return ,@(@($v) | Where-Object { $_ -is [string] })
}

# -File passes "a,b" as one literal token and does NOT split [string[]] on commas,
# so split every element ourselves and drop blanks.
function Split-Ids($items) {
  return @($items | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

function Write-Pins($ids) {
  $arr = @($ids | Sort-Object -Unique)
  # Always emit a JSON array, even for 0 or 1 element (ConvertTo-Json unwraps those).
  $json = if ($arr.Count -eq 0) { '[]' } else { '[' + (($arr | ForEach-Object { '"' + $_ + '"' }) -join ',') + ']' }
  # LF endings, no trailing newline surprises — matches how the daemon seeds it.
  [IO.File]::WriteAllText($pinsFile, $json, [Text.UTF8Encoding]::new($false))
}

$current = Read-Pins

if ($List) {
  if ($current.Count) { $current | ForEach-Object { Write-Host "  $_" } } else { Write-Host '(no pins)' }
  return
}

# Resolve target ids: explicit -Id (comma-split), else every live background session.
if ($Id) {
  $Id = Split-Ids $Id
} else {
  $agents = claude agents --json 2>$null | ConvertFrom-Json
  $Id = @($agents | Where-Object { $_.kind -eq 'background' -and $_.state -notin @('done','failed','stopped') } | ForEach-Object { $_.id })
  if (-not $Id) { Write-Host 'No live background sessions to pin. (Window-mode sessions are already immune.)'; return }
}

if ($Unpin) {
  $next = @(@($current) | Where-Object { $Id -notcontains $_ })
  Write-Pins $next
  Write-Host ("unpinned: {0}" -f ($Id -join ', '))
} else {
  $next = @(@($current) + @($Id))
  Write-Pins $next
  Write-Host ("pinned {0} session(s): {1}" -f @($Id).Count, ($Id -join ', '))
}
Write-Host ("pins.json now: {0}" -f ((Read-Pins) -join ', '))
