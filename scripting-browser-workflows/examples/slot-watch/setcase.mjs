// Put the fixture into a known state before a bench case.
const BASE = process.env.WF_SITE || 'http://127.0.0.1:8712';
const cases = {
  many:  { slots: 'many', variant: 'v1' },
  one:   { slots: 'one',  variant: 'v1' },
  none:  { slots: 'none', variant: 'v1' },
  drift: { slots: 'many', variant: 'v2' },   // slots ARE open; the markup moved
};
const c = cases[process.argv[2]];
if (!c) { console.error(`unknown case ${process.argv[2]}`); process.exit(1); }
const r = await fetch(`${BASE}/admin/state?slots=${c.slots}&variant=${c.variant}`);
console.error(await r.text());
