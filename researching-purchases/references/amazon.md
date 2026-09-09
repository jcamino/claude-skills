# Amazon specifics

Site-specific selectors for Amazon. Read `browser-setup.md` first — this file only fills in
the Amazon-shaped holes in that generic pattern. **None of these selectors exist on other
retailers**; on any other site, go back to the generic strategies.

Product IDs are ASINs, matching `B[0-9A-Z]{9}`.

## Location widget (generic step 2)

```js
await page.click('#nav-global-location-popover-link');
await page.fill('#GLUXZipUpdateInput', POSTCODE);
await page.click('#GLUXZipUpdate');
await page.click('#GLUXConfirmClose');
await ctx.storageState({ path: 'state.json' });
```

Verify it took by reading `#glow-ingress-line2` — it should name the town, not a country.

If the modal offers only a country dropdown (`#GLUXCountryList`), pick the country first;
the postcode field appears afterwards.

## Resolving the child ASIN (generic step 3)

Modern Amazon uses `inline-twister-row-*`; older listings use `#twister` and
`variation_*`. Try all three strategies — listings differ:

```js
const child = await page.evaluate((want) => {
  const grab = s => ((s || '').match(/B[0-9A-Z]{9}/) || [null])[0];

  // a) any <select> whose option text matches
  for (const sel of document.querySelectorAll('select')) {
    const o = [...(sel.options || [])].find(x => new RegExp(`\\b${want}\\b`).test(x.text));
    if (o) { const a = grab(o.value); if (a) return a; }
  }
  // b) twister swatches
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

Then navigate to `/dp/<child>` and read price, stock and delivery there.

## Ratings (generic step 6)

Search cards:

```js
rating: t(c.querySelector('.a-icon-alt')),                        // "4,4 de 5 estrellas"
nrev:   t(c.querySelector('.s-link-style .s-underline-text')),    // "(3.494)"
```

Product page: `#acrPopover` (rating), `#acrCustomerReviewText` (count), `#histogramTable`
rows (star distribution).
