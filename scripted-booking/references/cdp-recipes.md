# CDP recipes for booking work

`playwright-core` lives at
`C:/Users/jcamino/Code/npb-watch/node_modules/playwright-core` (Windows path —
Node will not resolve `/c/...`). CDP endpoint: the live logged-in port from
`bash ~/.claude/skills/agent-browser/preflight.sh`, in `CDP` below. Never hardcode it.

## Read a page cheaply

```js
const { chromium } = require('C:/Users/jcamino/Code/npb-watch/node_modules/playwright-core');
const CDP = process.env.CDP;                      // e.g. 'http://127.0.0.1:9222', from preflight
const browser = await chromium.connectOverCDP(CDP);
const page = await browser.contexts()[0].newPage();
await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(3000);
console.log(await page.evaluate(() => document.body.innerText));
await page.close(); await browser.close();
```

Always `newPage()` — never drive the user's existing tabs — and `page.close()`
before `browser.close()`.

## Read availability out of a calendar

Text is a lie; state is in the DOM.

```js
const days = await page.evaluate(() => [...document.querySelectorAll('button[class*=dateTableDayButton]')]
  .map(b => ({ d: b.textContent.trim(), off: b.disabled })));
```

Scope to a month by walking up from the month heading to the nearest ancestor
that contains day buttons, then query within it. CSS-module class hashes change
between deploys, so match on `[class*=...]` substrings, never the full hash.

## Click something React will believe

```js
// WRONG - React ignores untrusted events, silently
await page.evaluate(() => document.querySelector('button.foo').click());

// RIGHT
await page.locator('div[class*=DateTable_dateTableInner]').nth(0)
  .locator('button[class*=dateTableDayButton]', { hasText: /^25$/ }).first().click();
```

## Mask a payment form before screenshotting

```js
await page.evaluate(() => {
  const hits = [...document.querySelectorAll('input')]
    .filter(e => /card|cvv|cvc|seccoad|security/i.test((e.name||'') + (e.id||'')) && e.value);
  const saved = hits.map(e => [e, e.value]);
  hits.forEach(e => { e.value = '*'.repeat(e.value.length); });
  window.__restore = () => saved.forEach(([e, v]) => { e.value = v; });
  return hits.length;
});
await page.screenshot({ path: 'out/form-masked.png', fullPage: true });
await page.evaluate(() => window.__restore && window.__restore());
```

Masking sets `.value` only — it does not fire `input`/`change`, so React state is
untouched and the restore is exact. Verify the fields are repopulated before
handing the session over. If the form is a PSP iframe you cannot reach into,
do not screenshot it at all.

## Bring the window to the human

```js
const { bringOnScreen } = require('C:/Users/jcamino/Code/npb-watch/src/engine/screen');
await bringOnScreen(page);   // normal window state, 1280x940 at 80,60, bringToFront
```

Use at the 3DS frame, at any funnel step the script cannot solve, and whenever
handing a payment-ready form to the user over RDP.

## Shape of a driver

```js
// stopBefore: 'cart' | 'payment' | 'confirm' | null
// null means money is reachable. Unattended runs: pass it ONLY when ARMED && !dryRun.
// Live in-session buy: pass it after the user said "buy it" to the summary you showed
// and the live checkout re-verified against it. No ARMED file in that case.
async function drive(page, opts) {
  if (opts.stopBefore === undefined) throw new Error('stopBefore is required');
  ...
  if (opts.stopBefore === 'payment') return { state: 'payment-ready' };
  ...
  // POINT OF NO RETURN - the only line in this file that spends money
  if (opts.stopBefore === null) await page.locator(CONFIRM).click();
}
```
