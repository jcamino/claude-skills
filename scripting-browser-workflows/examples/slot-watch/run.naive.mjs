#!/usr/bin/env node
// The obvious script — the one all three baseline agents wrote. Kept as evidence,
// not as an option: it is correct on every case except the one that matters.
// `node ../../harness/bench.mjs . --config bench.naive.json --case drift`
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('C:/Users/jcamino/Code/npb-watch/node_modules/playwright-core');

const browser = await chromium.connectOverCDP(process.env.WF_CDP || 'http://127.0.0.1:9345');
const page = await browser.contexts()[0].newPage();
await page.goto(process.env.WF_URL || 'http://127.0.0.1:8712/slots');
await page.waitForSelector('.slot', { timeout: 5000 }).catch(() => {});   // wait for the GOOD outcome only

const open = await page.$$eval('.slot', (es) => es
  .filter((e) => e.dataset.available === 'true' && !e.disabled)
  .map((e) => e.textContent.trim()));

// Two outcomes. "I found nothing" and "there is nothing" are the same branch,
// which is exactly how a healthy-looking poller goes blind.
const result = { status: open.length ? 'open' : 'none', slots: open };
await page.close(); await browser.close();
console.log(JSON.stringify(result));
