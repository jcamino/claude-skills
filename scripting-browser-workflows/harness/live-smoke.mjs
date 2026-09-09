#!/usr/bin/env node
// Proves the two tiers still work against a real site, not just the fixture.
// Read-only, one request per tier, no login, no polling. Run it after a
// Chrome/agent-browser/playwright upgrade, or when a fixture-only number is
// about to be quoted as if it applied to the open internet.
//
//   node live-smoke.mjs [url] [cdp]
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('C:/Users/jcamino/Code/npb-watch/node_modules/playwright-core');

const URL_ = process.argv[2] || 'https://example.com';
const CDP = process.argv[3] || process.env.WF_CDP || 'http://127.0.0.1:9345';
const ms = (t0) => +(Number(process.hrtime.bigint() - t0) / 1e6).toFixed(0);

const out = { url: URL_ };

{ // Tier 1: no browser at all.
  const t0 = process.hrtime.bigint();
  const html = await fetch(URL_).then((r) => r.text());
  out.http = { ms: ms(t0), bytes: Buffer.byteLength(html), h1: /<h1[^>]*>(.*?)<\/h1>/s.exec(html)?.[1]?.trim() ?? null };
}

{ // Tier 2: the DOM, over an already-running Chrome.
  const t0 = process.hrtime.bigint();
  const browser = await chromium.connectOverCDP(CDP);
  const page = await (browser.contexts()[0] ?? await browser.newContext()).newPage();
  await page.goto(URL_, { waitUntil: 'domcontentloaded' });
  const h1 = await page.textContent('h1').catch(() => null);
  await page.close(); await browser.close();
  out.cdp = { ms: ms(t0), h1: h1?.trim() ?? null };
}

out.agree = out.http.h1 === out.cdp.h1;
console.log(JSON.stringify(out, null, 2));
process.exit(out.agree ? 0 : 1);
