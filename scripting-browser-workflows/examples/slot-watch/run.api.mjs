#!/usr/bin/env node
// slot-watch, no-browser backend: the page's own JSON call, replayed.
// Same output contract as run.cdp.mjs — one result, one console.log, no early exits.
// Reach for this tier first: it is ~8x cheaper than the DOM. Keep it only if the
// drift checks below still tell you when the site moves underneath you.
const SITE = process.env.WF_SITE || 'http://127.0.0.1:8712';

let result;
try {
  // The token is one-shot and minted per page render, so a captured request
  // replayed verbatim 403s on run 2. Re-mint every run; never cache it.
  const html = await fetch(`${SITE}/slots`).then((r) => r.text());
  const token = /name="slot-token"\s+content="([^"]+)"/.exec(html)?.[1];
  const res = token && await fetch(`${SITE}/api/slots`, { headers: { 'x-slot-token': token } });
  const body = res?.ok ? await res.json() : null;

  // Shape checks ARE the drift check when there is no DOM to look at: an API that
  // starts returning {} would otherwise read as "no slots available".
  if (!token) result = { status: 'drift', slots: [], why: 'token meta gone from /slots' };
  else if (!res.ok) result = { status: 'drift', slots: [], why: `api ${res.status}` };
  else if (!Array.isArray(body.slots) || (body.slots.length && !('available' in body.slots[0])))
    result = { status: 'drift', slots: [], why: 'api shape changed' };
  else {
    const open = body.slots.filter((s) => s.available === true).map((s) => s.time);
    result = { status: open.length ? 'open' : 'none', slots: open };
  }
} catch (e) {
  result = { status: 'error', slots: [], why: String(e.message || e).slice(0, 200) };
}

console.log(JSON.stringify(result));
