# Launch N interactive Claude Code sessions on Windows, each in its own
# PowerShell window, with bypass permissions and Remote Control enabled
# (so they show up in claude.ai/code and the mobile app).
#
#   powershell -ExecutionPolicy Bypass -File launch.ps1 -Count 5
#   powershell -ExecutionPolicy Bypass -File launch.ps1 -Count 3 -Prefix fleet -Dir C:\Users\jcamino\Code\npb-watch
#   powershell -ExecutionPolicy Bypass -File launch.ps1 -Server -Capacity 5   # on-demand server, no per-session windows
#   powershell -ExecutionPolicy Bypass -File launch.ps1 -Count 1 -Prompt 'Read brief.md and do what it says.'
#
# Each session is named "<Prefix>-<n>" in the Remote Control list. Windows
# stay open (-NoExit) so a crashed session leaves its output readable.
# -Prompt is each session's first message. Keep it to one line with no double
# quotes (it rides a -Command string into Windows PowerShell 5.1, which does not
# escape them for native programs); point it at a file for anything longer.
param(
  [int]$Count = 5,
  [string]$Prefix = ("win-" + (Get-Date -Format 'MMdd-HHmm')),
  [string]$Dir = 'C:\Users\jcamino\Code',
  [string]$PermissionMode = 'bypassPermissions',
  [int]$StaggerSec = 2,
  [switch]$Server,
  [int]$Capacity = 5,
  [string]$Prompt = ''
)
if ($Prompt -match '[\r\n"]') { throw '-Prompt must be one line without double quotes; point it at a file instead' }

# This script is usually run from INSIDE a Claude Code session (Bash tool), so
# it inherits that session's identity. Claude Code reads CLAUDE_CODE_CHILD_SESSION
# with Boolean(), so "0" still means "child": the vars have to be ABSENT. A child-
# marked session turns transcript saving off (--resume cannot find it), ignores
# --yes, and hides some tools. Start-Process copies this process's environment,
# so removing them here is enough. Same list Claude Code scrubs when it spawns
# its own fresh sessions, plus the cross-session messaging pipe and telemetry.
# Scope: only sessions launched by THIS script. Subagents run in-process and
# never come through here.
$inherited = @(
  'CLAUDECODE', 'CLAUDE_CODE_CHILD_SESSION', 'CLAUDE_CODE_SESSION_ID', 'CLAUDE_PID',
  'CLAUDE_CODE_BRIDGE_SESSION_ID', 'CLAUDE_CODE_MESSAGING_SOCKET', 'CLAUDE_CODE_MESSAGING_TOKEN',
  'CLAUDE_CODE_CHROME_MCP_ORG_DENIED', 'CLAUDE_CODE_EVAL_INTERVIEW_SESSION',
  'CLAUDE_CODE_ENTRYPOINT', 'CLAUDE_CODE_EXECPATH', 'CLAUDE_EFFORT', 'AI_AGENT', 'TRACEPARENT'
)
$cleared = @()
foreach ($v in $inherited) {
  if (Test-Path "Env:\$v") { Remove-Item "Env:\$v"; $cleared += $v }
}
if ($cleared.Count) { Write-Host ("cleared inherited parent-session vars: {0}" -f ($cleared -join ', ')) }
foreach ($v in 'CLAUDE_CODE_CHILD_SESSION', 'CLAUDECODE') {
  if ([Environment]::GetEnvironmentVariable($v)) { throw "$v is still set; refusing to launch child-marked sessions" }
}
# Belt and braces (Javier, 2026-09-05: every Claude launched by another Claude gets
# this): Claude Code skips the transcript suppression on this flag regardless of
# how a marker might arrive. Inherited by everything these sessions launch too.
$env:CLAUDE_CODE_FORCE_SESSION_PERSISTENCE = '1'

if ($Server) {
  $cmd = "claude remote-control --permission-mode $PermissionMode --spawn same-dir --capacity $Capacity"
  $p = Start-Process powershell -ArgumentList '-NoExit', '-Command', $cmd -WorkingDirectory $Dir -PassThru
  Write-Host ("started remote-control server (window pid {0}), capacity {1}, in {2}" -f $p.Id, $Capacity, $Dir)
  Write-Host 'Sessions spawn on demand from claude.ai/code. Stop: close the window or taskkill /PID <pid> /T /F (never /IM node.exe).'
  return
}

$launched = @()
for ($i = 1; $i -le $Count; $i++) {
  $name = "$Prefix-$i"
  $cmd = "claude --remote-control '$name' --permission-mode $PermissionMode"
  if ($Prompt) { $cmd += " '" + $Prompt.Replace("'", "''") + "'" }
  $p = Start-Process powershell -ArgumentList '-NoExit', '-Command', $cmd -WorkingDirectory $Dir -PassThru
  $launched += [pscustomobject]@{ n = $i; name = $name; windowPid = $p.Id }
  Write-Host ("started {0}  (window pid {1})  in {2}" -f $name, $p.Id, $Dir)
  if ($i -lt $Count) { Start-Sleep -Seconds $StaggerSec }
}
Write-Host ''
Write-Host ("{0} sessions launched with --permission-mode {1}. They appear as {2}-1..{3} at claude.ai/code within ~30 s." -f $Count, $PermissionMode, $Prefix, $Count)
Write-Host 'Stop one: close its window, or taskkill /PID <windowPid> /T /F (never /IM node.exe).'
$launched | Format-Table -AutoSize
