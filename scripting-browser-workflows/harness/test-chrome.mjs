#!/usr/bin/env node
// Disposable Chrome on a debug port, with its own profile. `stop` matches on the
// profile directory it created, so it can only ever kill its own browser — never
// the user's Chrome, a logged-in profile, or the watcher.
//   node test-chrome.mjs start [port]   -> launches, prints the ws endpoint
//   node test-chrome.mjs stop  [port]   -> kills only the Chrome using that profile
import { spawn, execSync } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const cmd = process.argv[2] || 'start';
const port = Number(process.argv[3] || 9345);
const pidFile = join(tmpdir(), `wf-chrome-${port}.json`);

async function version() {
  const r = await fetch(`http://127.0.0.1:${port}/json/version`).catch(() => null);
  return r?.ok ? r.json() : null;
}

if (cmd === 'start') {
  if (await version()) { console.log(JSON.stringify(await version())); process.exit(0); }
  const profile = mkdtempSync(join(tmpdir(), `wf-chrome-${port}-`));
  const child = spawn(CHROME, [
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check', '--disable-features=Translate',
    '--headless=new', 'about:blank',
  ], { detached: true, stdio: 'ignore' });
  child.unref();
  writeFileSync(pidFile, JSON.stringify({ pid: child.pid, profile, port }));
  for (let i = 0; i < 60; i++) {
    const v = await version();
    if (v) { console.log(JSON.stringify(v)); process.exit(0); }
    await new Promise((r) => setTimeout(r, 200));
  }
  console.error('chrome did not open a debug port'); process.exit(1);
}

if (cmd === 'stop') {
  if (!existsSync(pidFile)) { console.log('nothing to stop'); process.exit(0); }
  const { profile } = JSON.parse(readFileSync(pidFile, 'utf8'));
  // Match on the private profile dir only, exactly like ab-cleanup.ps1 does.
  const esc = profile.replace(/\\/g, '\\\\');
  try {
    execSync(`pwsh -NoProfile -Command "Get-CimInstance Win32_Process -Filter \\"Name='chrome.exe'\\" | Where-Object { $_.CommandLine -like '*${esc.split('\\').pop()}*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"`, { stdio: 'ignore' });
  } catch { /* already gone */ }
  try { rmSync(profile, { recursive: true, force: true }); } catch { /* locked */ }
  rmSync(pidFile, { force: true });
  console.log('stopped');
}
