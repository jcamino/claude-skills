#!/usr/bin/env node
// slot-watch, CDP backend. Prints one JSON object, exits 0.
// Emitted from recipe.json — regenerate rather than hand-patching both backends.
//
// Shape: compute one result -> close -> one console.log -> fall off the end.
// No branch prints, no branch exits. Closing is what lets the process end:
// measured 2026-09-09, a script that skips browser.close() was still running at
// the 10 s kill, and the same script with it exits 0 on its own.

// playwright-core is not installed globally; borrow it from a stack that has it.
// ESM `import` of a bare Windows path throws ERR_UNSUPPORTED_ESM_URL_SCHEME —
// createRequire takes the path as-is, and it must be a Windows path, not /c/...
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('C:/Users/jcamino/Code/npb-watch/node_modules/playwright-core');

const CDP = process.env.WF_CDP || 'http://127.0.0.1:9345';
const URL_ = process.env.WF_URL || 'http://127.0.0.1:8712/slots';
const TIMEOUT = Number(process.env.WF_TIMEOUT || 8000);

let browser, page, result;
try {
  browser = await chromium.connectOverCDP(CDP);
  page = await (browser.contexts()[0] ?? await browser.newContext()).newPage();
  await page.goto(URL_, { waitUntil: 'domcontentloaded', timeout: TIMEOUT });

  // Wait for EITHER outcome, never for the good one alone: waiting only for
  // ".slot" turns "no slots" into a timeout, and a timeout into a crash loop.
  await page.waitForFunction(
    () => document.querySelectorAll('.slot').length > 0 ||
          !document.getElementById('emptyBanner')?.hidden,
    null, { timeout: TIMEOUT },
  ).catch(() => {});

  const seen = await page.evaluate(() => ({
    // Availability is DOM state. The time text is identical either way.
    slots: [...document.querySelectorAll('.slot')].map((e) => ({
      time: e.textContent.trim(),
      available: e.dataset.available === 'true' && !e.disabled,
    })),
    emptyBanner: document.getElementById('emptyBanner') ? !document.getElementById('emptyBanner').hidden : false,
    canary: !!document.querySelector('nav a[href="/slots"]'),   // page rendered at all
  }));

  const open = seen.slots.filter((s) => s.available).map((s) => s.time);
  // Three outcomes, not two. "I found nothing" is not "there is nothing".
  const status = open.length ? 'open'
    : (seen.slots.length > 0 || seen.emptyBanner) ? 'none'
    : 'drift';
  result = { status, slots: open };
  if (status === 'drift') result.why = seen.canary ? 'page loaded, slot markup gone' : 'page did not render';
} catch (e) {
  // An error is a status, not an exit code: a non-zero exit gets retried by the
  // scheduler with the reason thrown away.
  result = { status: 'error', slots: [], why: String(e.message || e).slice(0, 200) };
} finally {
  await page?.close().catch(() => {});
  await browser?.close().catch(() => {});
}

console.log(JSON.stringify(result));
