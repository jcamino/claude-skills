# Headless Browser Recipe

Drive a **real installed Chrome** with `playwright-core` (no browser download). On Windows this avoids the Linux/WSL shared-library problem entirely — WSL's bundled Chromium typically fails with missing `libnspr4.so` / `libnss3.so`, and installing them needs interactive sudo.

```bash
npm install playwright-core        # in a scratch dir; do NOT install `playwright`
```

```js
const { chromium } = require('playwright-core');
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const browser = await chromium.launch({
  executablePath: CHROME,
  headless: true,
  args: ['--no-sandbox', '--disable-blink-features=AutomationControlled'],
});
const ctx = await browser.newContext({
  storageState: 'state.json',            // omit on first run, write it after step 2
  locale: 'es-ES',
  timezoneId: 'Europe/Madrid',
  viewport: { width: 1440, height: 1600 },
  userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
           + '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  extraHTTPHeaders: { 'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8' },
});
```

## 1. Dismiss the consent banner (decline non-essential)

An undismissed banner overlays the page and poisons `innerText` extraction — you end up scraping the cookie notice instead of the product.

```js
await page.evaluate(() => {
  const el = [...document.querySelectorAll('input,button,a,span')]
    .find(e => /^(rechazar|reject|solo las necesarias)$/i.test((e.value || e.textContent || '').trim()));
  if (el) el.click();
});
```

Match on **text**, not IDs — banner markup varies. Decline is the correct default; accepting is a user decision.

## 2. Set the delivery destination, then persist it

Until this is done every price and date may be foreign-export figures.

```js
await page.click('#nav-global-location-popover-link');
await page.fill('#GLUXZipUpdateInput', POSTCODE);
await page.click('#GLUXZipUpdate');
await page.click('#GLUXConfirmClose');
await ctx.storageState({ path: 'state.json' });   // reuse for every later run
```

Verify it took by reading `#glow-ingress-line2` — it should name the town, not a country.

If a modal offers only a country dropdown (`#GLUXCountryList`), pick the country first, then the postcode field appears.

## 3. Resolve the variant's own child page

**This is the step most often skipped.** The parent URL renders a default variant; its price, stock and delivery belong to that default, not to the one wanted.

```js
const child = await page.evaluate((want) => {
  const grab = s => ((s || '').match(/B[0-9A-Z]{9}/) || [null])[0];

  // a) any <select> whose option text matches
  for (const sel of document.querySelectorAll('select')) {
    const o = [...(sel.options || [])].find(x => new RegExp(`\\b${want}\\b`).test(x.text));
    if (o) { const a = grab(o.value); if (a) return a; }
  }
  // b) twister swatches (modern Amazon uses inline-twister-row-*)
  for (const box of document.querySelectorAll('[id*="size_name"],[id^="variation_"],#twister')) {
    for (const li of box.querySelectorAll('li,button,[data-asin]')) {
      if (!new RegExp(`\\b${want}\\b`).test(li.innerText || '')) continue;
      const a = li.getAttribute('data-defaultasin') || li.getAttribute('data-asin')
             || grab(li.getAttribute('data-dp-url'));
      if (a) return a;
    }
  }
  // c) fallback: twister JSON embedded in page scripts
  const m = document.documentElement.innerHTML
    .match(new RegExp(`"(B[0-9A-Z]{9})"\\s*:\\s*\\[\\s*"[^"]*\\b${want}\\b`));
  return m ? m[1] : null;
}, '42');
```

Then **navigate to the child** and read price/stock/delivery there. Do not read them from the parent.

A single selector strategy is not enough — listings differ. Try all three, and if none resolves, say so rather than falling back to the parent's numbers.

## 4. Read both delivery options

The delivery block routinely contains two dates:

```
Entrega GRATIS el lunes, 17 de agosto.  Entrega más rápida mañana, 11 de agosto.
```

Parse **every** date in the block and report the range, not just the first. Note that expedited offers carry an order-by countdown that expires — record when you read it.

## 5. Cross-check compatibility specs off-site

For socket / thread / mount / voltage / gauge, fetch the manufacturer's page for the model number. If the retailer's structured field disagrees, the manufacturer wins and the disagreement itself is worth reporting.

## 6. Capture ratings in the FIRST sweep

Grab rating and review count on every search card, so no candidate ever reaches a
recommendation without them:

```js
rating: t(c.querySelector('.a-icon-alt')),                        // "4,4 de 5 estrellas"
nrev:   t(c.querySelector('.s-link-style .s-underline-text')),    // "(3.494)"
```

On a product page: `#acrPopover` (rating), `#acrCustomerReviewText` (count),
`#histogramTable` rows (star distribution — a high 1–2★ tail at a decent average
means polarised quality).

## Gotchas

- Search-result cards carry delivery text too, but it reflects the **default** variant
- Autocompletes cap around 10 results sorted by popularity; small entries vanish. Query by station/product ID instead of concluding absence
- Prices differ **per size** on the same listing
- A listing whose price swings wildly between reads (€38 → €7) is unreliable — treat everything else on it as suspect too
- **Run scripts via Git Bash, not PowerShell.** PowerShell mangles quoting in `bash -c` strings and `node -e` one-liners (backtick escapes, `$` expansion, nested quotes), and 5.1 lacks `&&`. Bash heredocs and single-quotes pass through cleanly. Either way, anything non-trivial goes in a `script.cjs` file — never inline
