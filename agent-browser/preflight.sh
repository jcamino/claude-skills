#!/usr/bin/env bash
# Reports what is ACTUALLY usable for browser work on this machine, right now.
# SKILL.md names ports and tools that drift; this does not.
# Usage:  bash ~/.claude/skills/agent-browser/preflight.sh
#
# It does NOT just check that a port answers. A CDP browser whose Chrome has
# auto-updated underneath it answers /json/version perfectly and then crashes
# every renderer you open. That has happened here. So each live port gets a real
# tab opened, `1+1` evaluated in it, and the tab closed again.
set -u

echo "=== Chrome-owned listening ports ==="
pwsh -NoProfile -c "
  \$conns = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue
  \$rows = foreach (\$c in \$conns) {
    \$p = Get-Process -Id \$c.OwningProcess -ErrorAction SilentlyContinue
    if (\$p -and \$p.ProcessName -match 'chrome|msedge') {
      \$cl  = (Get-CimInstance Win32_Process -Filter \"ProcessId=\$(\$c.OwningProcess)\" -ErrorAction SilentlyContinue).CommandLine
      \$udd = [regex]::Match(\$cl,'user-data-dir=\"?([^\" ]+)').Groups[1].Value
      \$dbg = [regex]::Match(\$cl,'remote-debugging-port=(\d+)').Groups[1].Value
      if (\$dbg -and \$dbg -ne '0') { '{0}|{1}' -f \$dbg, \$udd }
    }
  }
  \$rows | Sort-Object -Unique
" 2>/dev/null | while IFS='|' read -r port udd; do
  [ -n "${port:-}" ] || continue
  printf '  %-6s %s\n' "$port" "${udd:-<unknown profile>}"
done
echo "  (a port here is only a candidate — usability is tested below)"

echo
echo "=== CDP health (open a tab, eval 1+1, close it) ==="
python - <<'PY'
import json, urllib.request, time
try:
    from websocket import create_connection
except ImportError:
    create_connection = None

def http(base, path, method="GET"):
    req = urllib.request.Request(base + path, method=method)
    return json.load(urllib.request.urlopen(req, timeout=6))

for port in (9222, 9333, 9334, 9345, 9351, 9352, 9353):
    base = "http://127.0.0.1:%d" % port
    try:
        ver = http(base, "/json/version")
    except Exception:
        continue
    running = ver.get("Browser", "?")
    note = "  watcher - do not drive" if port == 9334 else ""
    if create_connection is None:
        print("  %-5d %-28s ? (install websocket-client to health-check)%s" % (port, running, note))
        continue
    if port == 9334:
        print("  %-5d %-28s skipped (watcher)" % (port, running))
        continue
    tid = None
    try:
        t = http(base, "/json/new?about:blank", "PUT")
        tid = t["id"]
        w = create_connection(t["webSocketDebuggerUrl"], timeout=10, suppress_origin=True)
        w.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                           "params": {"expression": "1+1", "returnByValue": True}}))
        verdict, deadline = "no reply", time.time() + 10
        while time.time() < deadline:
            m = json.loads(w.recv())
            if m.get("method") == "Inspector.targetCrashed":
                verdict = "BROKEN - renderer crashes"; break
            if m.get("id") == 1:
                verdict = "USABLE" if m.get("result", {}).get("result", {}).get("value") == 2 else "odd reply"
                break
        w.close()
    except Exception as e:
        verdict = "BROKEN - %s" % type(e).__name__
    finally:
        if tid:
            try: http(base, "/json/close/" + tid, "PUT")
            except Exception: pass
    print("  %-5d %-28s %s%s" % (port, running, verdict, note))
PY

echo
echo "=== Chrome version skew (the silent killer) ==="
pwsh -NoProfile -c "
  \$disk = (Get-Item 'C:\Program Files\Google\Chrome\Application\chrome.exe' -EA SilentlyContinue).VersionInfo.ProductVersion
  if (-not \$disk) { \$disk = (Get-Item \"\$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe\" -EA SilentlyContinue).VersionInfo.ProductVersion }
  'on disk: ' + \$disk
" 2>/dev/null | sed 's/^/  /'
echo "  If a browser above reports an older build than this, Chrome auto-updated"
echo "  underneath it. New renderers die on launch. Fix = restart that browser."

echo
echo "=== no-browser fetch ==="
python -c "import curl_cffi; print('  curl_cffi     OK  -> requests.get(url, impersonate=\"chrome\")')" 2>/dev/null \
  || echo "  curl_cffi     MISSING  (pip install curl_cffi)"

echo
echo "=== own-browser drivers ==="
python -c "import playwright,os; print('  py playwright OK  ->', os.path.dirname(playwright.__file__))" 2>/dev/null \
  || echo "  py playwright MISSING"
python -c "import websocket; print('  websocket-cli OK  -> create_connection(url, suppress_origin=True)')" 2>/dev/null \
  || echo "  websocket-cli MISSING  (pip install websocket-client) - needed for raw CDP"
node -e "require.resolve('playwright');console.log('  node playwright OK  (NODE_PATH resolves from any cwd)')" 2>/dev/null \
  || { echo "  node playwright NOT resolvable from this process's cwd."
       npset=$(pwsh -NoProfile -c "[Environment]::GetEnvironmentVariable('NODE_PATH','User')" 2>/dev/null)
       if [ -n "${npset:-}" ]; then
         echo "    NODE_PATH IS set at User scope ($npset) - this process started before"
         echo "    that took effect. Prefix this run: NODE_PATH=\"\$(npm root -g)\""
       else
         echo "    NODE_PATH is unset at User scope. Fix once:"
         echo "    pwsh -c \"[Environment]::SetEnvironmentVariable('NODE_PATH',(npm root -g),'User')\""
       fi; }
printf '  agent-browser  %s\n' "$(agent-browser --version 2>/dev/null || echo MISSING)"
printf '  playwright-cli %s\n' "$(playwright-cli --version 2>/dev/null || echo MISSING)"

echo
echo "=== agent-browser leftovers (may be another session's - never -All) ==="
pwsh -NoProfile -File "$HOME/.claude/skills/agent-browser/ab-cleanup.ps1" 2>/dev/null \
  | grep -iE 'daemon|chrome proc|session state' | sed 's/^/  /'
