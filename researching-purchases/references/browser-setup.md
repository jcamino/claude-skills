# Browser setup (site-agnostic)

Drive a **real installed Chrome** with `playwright-core` (no browser download). On Windows
this sidesteps the Linux/WSL shared-library problem entirely — WSL's bundled Chromium
typically fails on missing `libnspr4.so` / `libnss3.so`, and installing those needs
interactive sudo.

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
  locale: 'es-ES',                       // match the market you are buying in
  timezoneId: 'Europe/Madrid',
  viewport: { width: 1440, height: 1600 },
  userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
           + '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  extraHTTPHeaders: { 'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8' },
});
```

## 1. Dismiss the consent banner (decline non-essential)

An undismissed banner overlays the page and poisons `innerText` extraction — you scrape
the cookie notice instead of the product.

```js
await page.evaluate(() => {
  const el = [...document.querySelectorAll('input,button,a,span')]
    .find(e => /^(rechazar|reject|decline|solo las necesarias|only essential)$/i
      .test((e.value || e.textContent || '').trim()));
  if (el) el.click();
});
```

Match on **text**, not IDs — banner markup varies between sites and between visits.
Declining is the correct default; accepting is the user's decision, not yours.

## 2. Set the delivery destination, then persist it

Until this is done, every price and date may be a foreign-export figure.

The widget differs per site — a header postcode field, an account address, or a country
dropdown that reveals a postcode field once a country is chosen. Whatever the mechanism:

1. Set it before reading any price or date.
2. **Verify it took** by reading the widget back — it should name the town or postcode,
   not just a country.
3. Persist with `await ctx.storageState({ path: 'state.json' })` and reuse that state for
   every later run, so you set the destination once rather than per script.

## 3. Resolve the variant's own page

**This is the step most often skipped.** The parent URL renders a default variant; its
price, stock and delivery belong to that default, not to the one wanted.

Selector strategies vary by site — a `<select>` whose option text matches, swatch elements
carrying a data attribute with the child ID, or a JSON blob embedded in a page script.
Try more than one; a single strategy is not enough because listings differ even within one
site.

Then **navigate to the child page** and read price, stock and delivery there. If no
strategy resolves the variant, say so rather than falling back to the parent's numbers.

## 4. Read every delivery option

The delivery block routinely contains two or more dates:

```
Entrega GRATIS el lunes, 17 de agosto.  Entrega más rápida mañana, 11 de agosto.
```

Parse **every** date in the block and report the range, not just the first. Expedited
offers usually carry an order-by countdown that expires — record the time you read it.

## 5. Cross-check compatibility specs off-site

For socket, thread, mount, voltage or gauge, fetch the manufacturer's page for the model
number. If the retailer's structured field disagrees, the manufacturer wins, and the
disagreement itself is worth reporting to the user.

## 6. Capture ratings in the FIRST sweep

Grab rating and review count from every search card as you go, so no candidate can reach a
recommendation without them. Retrofitting them later is where they get dropped.

On a product page also look for the star-distribution histogram: a high 1–2★ tail behind a
decent average means polarised quality, which an average alone hides.

## Gotchas

- Search-result cards carry delivery text too, but it reflects the **default** variant
- Autocompletes and dropdowns cap around 10 results, sorted by popularity — small entries
  vanish. Query by product ID rather than concluding absence
- Prices differ **per variant** on the same listing
- A listing whose price swings wildly between reads (€38 → €7) is unreliable; treat
  everything else on it as suspect too
- Anything non-trivial goes in a `script.cjs` file rather than an inline one-liner
