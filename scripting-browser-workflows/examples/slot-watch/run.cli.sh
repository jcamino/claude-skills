#!/usr/bin/env bash
# slot-watch, CLI backend (agent-browser). Prints one JSON object, exits 0.
# Same recipe as run.cdp.mjs — the two must emit identical bytes.
set -uo pipefail

URL="${WF_URL:-http://127.0.0.1:8712/slots}"
SESSION="${WF_SESSION:-slot-watch}"
OUT="$(mktemp)"            # a FILE, never a dir you later rm -rf: agent-browser
trap 'rm -f "$OUT"' EXIT   # parks its live Chrome profile under TMPDIR.

# NEVER out=$(agent-browser ...): a command substitution around a call that
# spawns the daemon inherits the pipe and blocks for the daemon's 1 h idle timeout.
ab() { agent-browser --session "$SESSION" "$@" > "$OUT" 2>&1; }

ab open "$URL" || { echo '{"status":"error","slots":[],"why":"open failed"}'; exit 0; }

# Wait for EITHER outcome. A bare `wait .slot` makes "no slots" look like a crash.
ab eval "new Promise(r => { const t0 = Date.now(); (function p(){
  const ready = document.querySelectorAll('.slot').length > 0
    || (document.getElementById('emptyBanner') && !document.getElementById('emptyBanner').hidden);
  if (ready || Date.now() - t0 > 8000) return r(ready);
  setTimeout(p, 100); })(); })"

ab eval "JSON.stringify((() => {
  const slots = [...document.querySelectorAll('.slot')].map(e => ({
    time: e.textContent.trim(),
    available: e.dataset.available === 'true' && !e.disabled }));
  const b = document.getElementById('emptyBanner');
  const canary = !!document.querySelector('nav a[href=\"/slots\"]');
  const open = slots.filter(s => s.available).map(s => s.time);
  const status = open.length ? 'open' : (slots.length > 0 || (b && !b.hidden)) ? 'none' : 'drift';
  return status === 'drift'
    ? { status, slots: open, why: canary ? 'page loaded, slot markup gone' : 'page did not render' }
    : { status, slots: open };
})())"

# `eval` prints the value as a JSON string literal; unwrap to the bare object.
node -e '
  const raw = require("fs").readFileSync(process.argv[1], "utf8").trim();
  try { console.log(JSON.stringify(JSON.parse(JSON.parse(raw)))); }
  catch { console.log(JSON.stringify({ status: "error", slots: [], why: raw.slice(0, 200) })); }
' "$OUT"

# The session (daemon + its own Chrome) is deliberately left warm for the next
# poll. WF_CLOSE=1 for a one-shot run, or every invocation leaks a browser.
[ "${WF_CLOSE:-0}" = "1" ] && agent-browser --session "$SESSION" close > /dev/null 2>&1
exit 0
