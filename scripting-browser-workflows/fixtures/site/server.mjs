#!/usr/bin/env node
// Deterministic fixture site for testing browser-workflow scripting.
// Zero dependencies. node server.mjs [port]
//
// Every trap here was seen in the wild (see ../README.md for the map).
import { createServer } from 'node:http';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.argv[2] || 8712);
// Per-port, so two sessions running the fixture on different ports do not read
// each other's money line as their own.
const ORDERS = join(HERE, `orders-${PORT}.json`);

// ---- server state -----------------------------------------------------
const state = {
  slots: 'none',   // none | one | many
  variant: 'v1',   // v1 | v2  (v2 = the site "changed": renamed classes, no empty banner)
  latencyMs: 400,  // slots render after this delay, client-side
  gadgetPrice: '34.50', // /admin/state?gadgetPrice=29.99
};
const tokens = new Set();     // one-shot tokens minted per page render
let tokenSeq = 0;

const SLOT_TIMES = ['09:00', '10:30', '13:00', '15:30', '17:00'];
function slotsFor(mode) {
  // Availability is DOM state, never text: every time renders, only some are open.
  const open = mode === 'none' ? [] : mode === 'one' ? [2] : [1, 2, 4];
  return SLOT_TIMES.map((t, i) => ({ id: `s${i}`, time: t, available: open.includes(i) }));
}

// ---- html -------------------------------------------------------------
const CSS = `body{font:14px system-ui;margin:2rem;max-width:52rem}
button{padding:.4rem .8rem;margin:.2rem;font:inherit}
button[disabled]{opacity:.45}
.slot,.slot-card{display:inline-block;border:1px solid #ccc;padding:.3rem .6rem;margin:.2rem}
nav a{margin-right:1rem}`;

const page = (title, body) => `<!doctype html><html lang="en"><head>
<meta charset="utf-8"><title>${title}</title><style>${CSS}</style></head><body>
<nav><a href="/">home</a><a href="/shop">shop</a><a href="/slots">slots</a></nav>
${body}</body></html>`;

function homePage() {
  return page('Fixture home', `<h1>Fixture site</h1>
<p>Deterministic target for workflow-scripting tests.</p>
<ul><li><a href="/shop">Shop</a> &rarr; cart &rarr; checkout (never charges unless POSTed)</li>
<li><a href="/slots">Slot availability</a> (state: <b id="stateNow">${state.slots}</b>, variant ${state.variant})</li></ul>`);
}

function shopPage() {
  // v2 renames the row and price classes — same drift shape as /slots.
  const v2 = state.variant === 'v2';
  const rowCls = v2 ? 'item' : 'product';
  const priceCls = v2 ? 'amount' : 'price';
  return page('Shop', `<h1>Shop</h1>
<div id="products">
  ${[['p1', 'Widget', '12.00'], ['p2', 'Gadget', state.gadgetPrice], ['p3', 'Doohickey', '7.25']]
    .map(([id, name, price]) => `<div class="${rowCls}" data-sku="${id}">
    <span class="name">${name}</span> <span class="${priceCls}" data-price="${price}">$${price}</span>
    <button class="js-action add" data-sku="${id}">Add to cart</button></div>`).join('\n  ')}
</div>
<p><a href="/cart" id="toCart">Go to cart</a> (<span id="count">0</span> items)</p>
<script>
// TRAP 1: only trusted events count. page.evaluate(el => el.click()) silently no-ops.
let n = 0;
document.querySelectorAll('button.add').forEach(b => b.addEventListener('click', e => {
  if (!e.isTrusted) return;
  n++; document.getElementById('count').textContent = String(n);
  document.cookie = 'cart=' + n + ';path=/';
}));
</script>`);
}

function cartPage(count) {
  return page('Cart', `<h1>Cart</h1>
<p id="cartCount">${count} item(s)</p>
<!-- TRAP 2: Reset and Proceed share a class, Reset is FIRST in the DOM. -->
<button class="js-action btn" id="reset">Reset basket</button>
<button class="js-action btn" id="proceed" ${count > 0 ? '' : 'disabled'}>Proceed to checkout</button>
<script>
document.getElementById('reset').addEventListener('click', () => {
  document.cookie = 'cart=0;path=/'; location.href = '/cart';
});
document.getElementById('proceed').addEventListener('click', () => { location.href = '/checkout'; });
</script>`);
}

function checkoutPage(count) {
  // TRAP 4: duplicate ids, one block per guest.
  const guest = (i) => `<fieldset class="guest"><legend>Guest ${i + 1}</legend>
    <label>Name <input id="guestName" name="guestName" type="text"></label>
    <label>Age <input id="age" name="age" type="number"></label></fieldset>`;
  return page('Checkout', `<h1>Checkout</h1>
<form id="checkout" method="POST" action="/order">
  ${[0, 1].map(guest).join('\n  ')}
  <label>Email <input id="email" name="email" type="email"></label><br>
  <!-- TRAP 3: bare attribute selectors grab the wrong control.
       input[name*=card i] matches this radio; input[name*=security i] matches the hidden token. -->
  <label><input type="radio" name="cardOnFile" value="yes" checked> Use card on file</label>
  <input type="hidden" name="securityToken" value="psp_tok_${++tokenSeq}">
  <label>Card number <input id="pan" name="pan" type="text" inputmode="numeric"></label>
  <label>CVV <input id="cvv" name="cvv" type="text"></label><br>
  <p>Total: <b id="total">$${(count * 12).toFixed(2)}</b></p>
  <p class="policy">Free cancellation until 24h before. Changes: none after purchase.
     If the operator cancels, you are refunded in full within 14 days.</p>
  <button type="submit" id="placeOrder">Place order &mdash; charges the card</button>
</form>`);
}

function slotsPage() {
  const v2 = state.variant === 'v2';
  const token = `tok_${++tokenSeq}`;
  tokens.add(token);
  return page('Slot availability', `<h1>Availability</h1>
<meta name="slot-token" content="${token}">
<div id="slots">loading&hellip;</div>
${v2 ? '' : '<p id="emptyBanner" hidden>No slots available today.</p>'}
<script>
// TRAP 8: slots arrive late; a read at t=0 sees "loading".
// TRAP 6: the API needs the one-shot token from the meta tag.
setTimeout(async () => {
  const tok = document.querySelector('meta[name=slot-token]').content;
  const r = await fetch('/api/slots', { headers: { 'x-slot-token': tok } });
  const { slots } = await r.json();
  const cls = ${v2 ? "'slot-card'" : "'slot'"};
  document.getElementById('slots').innerHTML = slots.map(s =>
    // TRAP 5: the time text is identical whether or not it is bookable.
    '<button class="' + cls + '" data-slot="' + s.id + '" data-available="' + s.available + '"'
    + (s.available ? '' : ' disabled') + '>' + s.time + '</button>').join('');
  const banner = document.getElementById('emptyBanner');
  if (banner) banner.hidden = slots.some(s => s.available);
}, ${state.latencyMs});
</script>`);
}

// ---- routing ----------------------------------------------------------
const cartOf = (req) => Number(/(?:^|;\s*)cart=(\d+)/.exec(req.headers.cookie || '')?.[1] || 0);
const send = (res, code, body, type = 'text/html; charset=utf-8') =>
  res.writeHead(code, { 'content-type': type, 'cache-control': 'no-store' }).end(body);

const server = createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const p = url.pathname;

  if (p === '/') return send(res, 200, homePage());
  if (p === '/shop') return send(res, 200, shopPage());
  if (p === '/cart') return send(res, 200, cartPage(cartOf(req)));
  if (p === '/checkout') return send(res, 200, checkoutPage(cartOf(req)));
  if (p === '/slots') {
    if (url.searchParams.has('state')) state.slots = url.searchParams.get('state');
    if (url.searchParams.has('variant')) state.variant = url.searchParams.get('variant');
    return send(res, 200, slotsPage());
  }

  if (p === '/api/slots') {
    const tok = req.headers['x-slot-token'];
    if (!tok || !tokens.has(tok)) return send(res, 403, JSON.stringify({ error: 'bad or reused token' }), 'application/json');
    tokens.delete(tok);   // one-shot: a naive replay of the captured call 403s
    return send(res, 200, JSON.stringify({ slots: slotsFor(state.slots) }), 'application/json');
  }

  // The money line. Nothing here should ever run in a test.
  if (p === '/order' && req.method === 'POST') {
    let body = '';
    req.on('data', (c) => (body += c));
    req.on('end', () => {
      const prev = existsSync(ORDERS) ? JSON.parse(readFileSync(ORDERS, 'utf8')) : [];
      prev.push({ at: new Date().toISOString(), fields: [...new URLSearchParams(body).keys()] });
      writeFileSync(ORDERS, JSON.stringify(prev, null, 2));   // field NAMES only, never values
      send(res, 200, page('Charged', '<h1>Order placed</h1><p id="orderOk">Your card was charged.</p>'));
    });
    return;
  }

  // Test control plane.
  if (p === '/admin/state') {
    for (const k of ['slots', 'variant', 'gadgetPrice']) if (url.searchParams.has(k)) state[k] = url.searchParams.get(k);
    if (url.searchParams.has('latencyMs')) state.latencyMs = Number(url.searchParams.get('latencyMs'));
    return send(res, 200, JSON.stringify(state), 'application/json');
  }
  if (p === '/admin/orders') {
    const prev = existsSync(ORDERS) ? JSON.parse(readFileSync(ORDERS, 'utf8')) : [];
    return send(res, 200, JSON.stringify(prev), 'application/json');
  }

  send(res, 404, page('404', '<h1>404</h1>'));
});

server.listen(PORT, '127.0.0.1', () => console.log(`fixture site on http://127.0.0.1:${PORT}`));
