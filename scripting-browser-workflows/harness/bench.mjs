#!/usr/bin/env node
// Bake-off: run each backend of one workflow N times and report speed,
// correctness and the bytes it would spend in an agent's context.
//
//   node bench.mjs <workflow-dir> [-n 10] [--case many]
//
// <workflow-dir>/bench.json:
//   {
//     "setup":  ["node", "...", "--state", "{case}"],     // optional, run once per case
//     "cases":  { "many": {"expect": {...}}, "none": {"expect": {...}} },
//     "backends": { "cdp": ["node","run.cdp.mjs"], "cli": ["bash","run.cli.sh"] }
//   }
//
// Every backend must print ONE json object on stdout and exit 0. That object is
// compared to the case's `expect`. Anything else counts as a failed run, which
// is the point: a backend that is fast and wrong is worse than useless.
import { spawn } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

const args = process.argv.slice(2);
const dir = resolve(args[0] || '.');
const n = Number(args[args.indexOf('-n') + 1]) || 10;
const onlyCase = args.includes('--case') ? args[args.indexOf('--case') + 1] : null;
const cfgName = args.includes('--config') ? args[args.indexOf('--config') + 1] : 'bench.json';

const cfg = JSON.parse(readFileSync(join(dir, cfgName), 'utf8'));
const cases = Object.entries(cfg.cases ?? { default: {} }).filter(([k]) => !onlyCase || k === onlyCase);

function run(argv, { cwd, env } = {}) {
  return new Promise((res) => {
    const t0 = process.hrtime.bigint();
    const p = spawn(argv[0], argv.slice(1), { cwd, env: { ...process.env, ...env }, shell: false });
    let out = '', err = '';
    p.stdout.on('data', (c) => (out += c));
    p.stderr.on('data', (c) => (err += c));
    p.on('error', (e) => res({ ms: 0, code: -1, out, err: String(e) }));
    p.on('close', (code) => res({ ms: Number(process.hrtime.bigint() - t0) / 1e6, code, out, err }));
  });
}

const deepEq = (a, b) => JSON.stringify(a) === JSON.stringify(b);
// A case may state `expect` (one object, or a list of acceptable ones) and/or
// `forbid` (answers that are wrong even if plausible). Backends that legitimately
// see a different truth — a no-browser backend is immune to DOM drift — override
// via `per: { <backend>: { expect|forbid } }` rather than being marked wrong.
const judge = (parsed, rule) => {
  if (!rule) return true;
  if (rule.forbid && (Array.isArray(rule.forbid) ? rule.forbid : [rule.forbid]).some((f) => deepEq(parsed, f))) return false;
  if (!rule.expect) return true;
  return (Array.isArray(rule.expect) ? rule.expect : [rule.expect]).some((e) => deepEq(parsed, e));
};
const pct = (xs, p) => xs.slice().sort((x, y) => x - y)[Math.min(xs.length - 1, Math.floor(xs.length * p))];

const rows = [];
for (const [caseName, c] of cases) {
  if (cfg.setup) {
    const setup = cfg.setup.map((s) => s.replace('{case}', caseName));
    const r = await run(setup, { cwd: dir });
    if (r.code !== 0) { console.error(`setup failed for case ${caseName}: ${r.err}`); process.exit(1); }
  }
  for (const [backend, argv] of Object.entries(cfg.backends)) {
    const cmd = argv.map((s) => s.replace('{case}', caseName));
    await run(cmd, { cwd: dir });                       // warm-up, not scored
    const times = [], sizes = [];
    let ok = 0, fails = [];
    for (let i = 0; i < n; i++) {
      const r = await run(cmd, { cwd: dir });
      times.push(r.ms);
      sizes.push(Buffer.byteLength(r.out) + Buffer.byteLength(r.err));
      let parsed = null;
      try { parsed = JSON.parse(r.out); } catch { /* not json */ }
      const good = r.code === 0 && parsed !== null && judge(parsed, c.per?.[backend] ?? c);
      if (good) ok++;
      else fails.push({ i, code: r.code, out: r.out.slice(0, 300), err: r.err.slice(0, 300) });
    }
    rows.push({
      case: caseName, backend, n,
      p50: +pct(times, 0.5).toFixed(0), p95: +pct(times, 0.95).toFixed(0),
      bytes: Math.round(sizes.reduce((a, b) => a + b, 0) / n),
      correct: `${ok}/${n}`, fails: fails.slice(0, 2),
    });
    process.stderr.write(`  ${caseName}/${backend}: ${ok}/${n} ok\n`);
  }
}

const w = (s, k) => String(s).padEnd(k);
console.log(`\n| case | backend | p50 ms | p95 ms | stdout bytes | ~tokens | correct |`);
console.log(`|---|---|---|---|---|---|---|`);
for (const r of rows)
  console.log(`| ${w(r.case, 6)} | ${w(r.backend, 8)} | ${w(r.p50, 6)} | ${w(r.p95, 6)} | ${w(r.bytes, 12)} | ${w(Math.round(r.bytes / 4), 7)} | ${r.correct} |`);

const bad = rows.filter((r) => r.fails.length);
if (bad.length) {
  console.log(`\nFAILURES (first 2 per row) — a fast wrong answer is the failure mode this column exists to catch:`);
  for (const r of bad) for (const f of r.fails) console.log(`  ${r.case}/${r.backend} run#${f.i} exit=${f.code} out=${JSON.stringify(f.out)} err=${JSON.stringify(f.err)}`);
}
const resultsFile = join(dir, cfgName.replace(/\.json$/, '') + '-results.json');
writeFileSync(resultsFile, JSON.stringify({ at: new Date().toISOString(), config: cfgName, n, rows }, null, 2));
console.log(`\nwrote ${resultsFile}`);
