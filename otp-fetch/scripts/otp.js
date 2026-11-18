#!/usr/bin/env node
'use strict';
// otp.js — wait for a one-time code to arrive by mail and print it.
//
// Built after the ticketjam session (2026-09-06), where the failure was not
// reading the mail but *timing*: a human relayed each Google 2FA code by hand,
// and every code had expired by the time PowerShell keystroke automation typed
// it. The fix is structural — hold an IMAP IDLE connection open BEFORE the site
// is asked to send the code, so the code is in hand within a second of Gmail
// receiving it.
//
//   Terminal A:  node otp.js --from booking.com --timeout 180
//   Terminal B:  ...click "send me a code"...
//   Terminal A prints:  483920
//
// The listener is armed at process start and only ever returns mail that
// arrives AFTER that moment (`--since` overrides). A stale code is worse than
// no code: it looks like success and fails at submit.
//
// Deterministic: IMAP + regex, no model in the loop. Exits as soon as it has
// a code, so it is safe to run inline from a booking script:
//
//   CODE=$(node ~/.claude/skills/otp-fetch/scripts/otp.js --from booking.com) || exit 1
//
// ~/Code/otp-fetch is a symlink to this folder, so older callers keep working.
//
// Credentials: a Google *app password*, never the account password. Resolution
// order is env -> ~/.secrets/gmail-imap.env -> ~/Code/takanaka-watch/.env
// (that last one is where these already live; see README).
//
// Exit codes: 0 code found (stdout) | 3 timeout | 2 IMAP/auth failure
//             | 1 bad usage

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const HOST = 'imap.gmail.com';
const PORT = 993;

// ------------------------------------------------------------------ args ---

function usage(msg) {
  if (msg) process.stderr.write('otp: ' + msg + '\n\n');
  process.stderr.write([
    'Usage: node otp.js [options]',
    '',
    '  --from <substr>     Only mail whose From contains this (repeatable).',
    '                      Match is case-insensitive substring, so "booking.com"',
    '                      catches no-reply@mailer.booking.com.',
    '  --subject <regex>   Only mail whose Subject matches this regex.',
    '  --pattern <regex>   Custom code pattern; capture group 1 is the code.',
    '  --since <spec>      Floor for arrival time: "now" (default), an ISO',
    '                      timestamp, or "-90s" / "-5m" for a short look-back.',
    '  --timeout <sec>     Give up after this long (default 180).',
    '  --lookback <n>      How many uids back the --since sweep reaches',
    '                      (default 200). Ignored when --since is "now".',
    '  --mailbox <name>    IMAP mailbox (default INBOX).',
    '  --env-file <path>   Read GMAIL_IMAP_* from this file first.',
    '  --json              Print {code, from, subject, receivedAt} instead of',
    '                      the bare code.',
    '  --verbose           Log every candidate mail to stderr.',
    '',
    'Arm this BEFORE triggering the send-code step, or you will race the clock',
    'the same way the ticketjam run did.',
    '',
  ].join('\n'));
  process.exit(msg ? 1 : 0);
}

function parseArgs(argv) {
  // lookBack is set by --since, not inferred from the clock: connecting can
  // take a couple of seconds, and a "now" run must not sweep history just
  // because the TLS handshake was slow.
  const o = { from: [], timeout: 180, mailbox: 'INBOX', since: 'now', lookback: 200, lookBack: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => {
      const v = argv[++i];
      if (v === undefined) usage('option ' + a + ' needs a value');
      return v;
    };
    if (a === '--since') { o.since = next(); o.lookBack = o.since !== 'now'; }
    else if (a === '--from') o.from.push(next().toLowerCase());
    else if (a === '--subject') o.subject = next();
    else if (a === '--pattern') o.pattern = next();
    else if (a === '--timeout') o.timeout = Number(next());
    else if (a === '--lookback') o.lookback = Number(next());
    else if (a === '--mailbox') o.mailbox = next();
    else if (a === '--env-file') o.envFile = next();
    else if (a === '--json') o.json = true;
    else if (a === '--verbose') o.verbose = true;
    else if (a === '-h' || a === '--help') usage();
    else usage('unknown option ' + a);
  }
  if (!Number.isFinite(o.timeout) || o.timeout <= 0) usage('--timeout must be a positive number of seconds');
  return o;
}

function resolveSince(spec) {
  if (!spec || spec === 'now') return new Date();
  const rel = /^-(\d+)([smh])$/.exec(spec.trim());
  if (rel) {
    const mult = { s: 1e3, m: 6e4, h: 3.6e6 }[rel[2]];
    return new Date(Date.now() - Number(rel[1]) * mult);
  }
  const d = new Date(spec);
  if (Number.isNaN(d.getTime())) usage('could not parse --since ' + JSON.stringify(spec));
  return d;
}

// ------------------------------------------------------------------ creds ---

// Minimal KEY=VALUE reader. Not a dotenv clone: no interpolation, no export
// keyword, quotes stripped. Enough for the two variables this needs.
function readEnvFile(file) {
  const out = {};
  let text;
  try { text = fs.readFileSync(file, 'utf8'); } catch { return out; }
  for (const line of text.split(/\r?\n/)) {
    const m = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/.exec(line);
    if (!m) continue;
    let v = m[2].trim();
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
      v = v.slice(1, -1);
    }
    out[m[1]] = v;
  }
  return out;
}

function credentials(opts) {
  const candidates = [
    opts.envFile,
    path.join(os.homedir(), '.secrets', 'gmail-imap.env'),
    path.join(os.homedir(), 'Code', 'takanaka-watch', '.env'),
  ].filter(Boolean);
  let user = process.env.GMAIL_IMAP_USER || '';
  let pass = process.env.GMAIL_IMAP_APP_PASSWORD || '';
  let source = user && pass ? 'environment' : '';
  for (const file of candidates) {
    if (user && pass) break;
    const e = readEnvFile(file);
    if (e.GMAIL_IMAP_USER && e.GMAIL_IMAP_APP_PASSWORD) {
      user = user || e.GMAIL_IMAP_USER;
      pass = pass || e.GMAIL_IMAP_APP_PASSWORD;
      source = file;
    }
  }
  if (!user || !pass) {
    process.stderr.write(
      'otp: no IMAP credentials. Set GMAIL_IMAP_USER and GMAIL_IMAP_APP_PASSWORD,\n' +
      '     or put them in ~/.secrets/gmail-imap.env. Use a Google app password.\n');
    process.exit(2);
  }
  return { user, pass, source };
}

// ------------------------------------------------------------- extraction ---

// A labelled code is trusted; a bare digit run is only accepted when the mail
// offers exactly one, because order numbers, years and prices all look like
// short digit runs.
//
// The ASCII labels are word-bounded on purpose: an unbounded `pin` matches
// "shipping" and "spin", and an unbounded `otp` matches nothing useful either.
// The Japanese labels are not, because \b is meaningless next to kana.
const LBL =
  '(?:\\b(?:code|código|codigo|passcode|pin|otp|one[- ]?time|verification|' +
  'verify|security)\\b|認証コード|確認コード|コード)';

// Real mail puts words between the label and the digits — "Your verification
// code is 55210", "Tu código de verificación es 604815" — so the gap allows
// letters, but is non-greedy and capped so a stray "security" in a footer
// cannot reach a number forty characters later.
const GAP = '[^0-9]{0,40}?';

// Six digits first: it is what almost every service sends, and trying it before
// the looser 4-8 rule stops a nearby year ("your 2026 statement") from winning.
const PATTERNS = [
  new RegExp(LBL + GAP + '([0-9]{6})\\b', 'i'),
  new RegExp(LBL + GAP + '([0-9]{4,8})\\b', 'i'),
  new RegExp('\\b([0-9]{4,8})[^0-9A-Za-z]{0,20}(?:is your|' + LBL + ')', 'i'),
];

// Alphanumeric codes (Resy, some airlines). Case-insensitive so the label
// matches, then the capture is re-checked: a real code is upper-case and has at
// least one digit, which keeps plain words like "SIGNIN" out.
const LABELLED_ALNUM = new RegExp(LBL + '[^0-9A-Za-z]{0,30}\\b([A-Z0-9]{6,8})\\b', 'i');
const LOOKS_ALNUM_CODE = /^(?=.*[0-9])[A-Z0-9]{6,8}$/;

/**
 * Pull a one-time code out of subject+body. Returns the code or null.
 * `custom` is an optional user-supplied regex whose group 1 is the code.
 */
function extractCode(text, custom) {
  const s = String(text || '');
  if (custom) {
    const m = new RegExp(custom, 'i').exec(s);
    return m ? (m[1] || m[0]) : null;
  }
  for (const re of PATTERNS) {
    const m = re.exec(s);
    if (m) return m[1];
  }
  const alnum = LABELLED_ALNUM.exec(s);
  if (alnum && LOOKS_ALNUM_CODE.test(alnum[1])) return alnum[1];
  // Fallback: a single unambiguous standalone 6-digit run. Anything glued to a
  // letter, a currency symbol or a decimal point is not a code.
  const bare = s.match(/(?<![0-9A-Za-z.,$£€¥])[0-9]{6}(?![0-9A-Za-z.,])/g);
  if (bare) {
    const uniq = [...new Set(bare)];
    if (uniq.length === 1) return uniq[0];
  }
  return null;
}

// ------------------------------------------------------------------- main ---

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const since = resolveSince(opts.since);
  const { user, pass, source } = credentials(opts);
  const subjectRe = opts.subject ? new RegExp(opts.subject, 'i') : null;

  let ImapFlow;
  let simpleParser;
  try {
    ({ ImapFlow } = require('imapflow'));
    ({ simpleParser } = require('mailparser'));
  } catch {
    process.stderr.write('otp: dependencies missing — run `npm install` in ' + __dirname + '\n');
    process.exit(2);
  }

  const log = (m) => process.stderr.write('otp: ' + m + '\n');
  const client = new ImapFlow({
    host: HOST, port: PORT, secure: true,
    auth: { user, pass },
    logger: false,
  });

  let done = false;
  let result = null;

  // Cheap first pass, straight off the IMAP envelope: no body download, no MIME
  // parse. The catch-up sweep leans on this to skip hundreds of mails for the
  // price of their headers.
  function envelopeMatches(envelope, internalDate) {
    const when = internalDate ? new Date(internalDate) : new Date();
    if (when < since) return false;
    const from = ((envelope && envelope.from) || [])
      .map((a) => String((a && a.address) || '').toLowerCase()).join(' ');
    const subject = String((envelope && envelope.subject) || '');
    if (opts.from.length && !opts.from.some((f) => from.includes(f))) {
      if (opts.verbose) log('skip (from) ' + from + ' — ' + subject.slice(0, 60));
      return false;
    }
    if (subjectRe && !subjectRe.test(subject)) {
      if (opts.verbose) log('skip (subject) ' + subject.slice(0, 60));
      return false;
    }
    return true;
  }

  // Second pass: download and parse the body, then look for a code.
  async function consider(msg) {
    if (done || !msg) return;
    if (!envelopeMatches(msg.envelope, msg.internalDate)) return;

    let full = msg;
    if (!full.source) {
      try {
        full = await client.fetchOne(String(msg.uid), FIELDS, { uid: true });
      } catch (e) { log('fetch uid ' + msg.uid + ' failed: ' + e.message); return; }
    }
    if (!full || !full.source) return;

    const when = full.internalDate ? new Date(full.internalDate) : new Date();
    const parsed = await simpleParser(full.source);
    const subject = String(parsed.subject || '');

    const body = [subject, parsed.text || '', parsed.html ? String(parsed.html).replace(/<[^>]+>/g, ' ') : '']
      .join('\n');
    const code = extractCode(body, opts.pattern);
    if (!code) {
      if (opts.verbose) log('matched but no code in: ' + subject.slice(0, 60));
      return;
    }

    done = true;
    result = { code, from: (parsed.from && parsed.from.text) || '', subject, receivedAt: when.toISOString() };
  }

  const deadline = Date.now() + opts.timeout * 1000;
  const FIELDS = { uid: true, envelope: true, internalDate: true, source: true };

  try {
    await client.connect();
    // mailboxOpen, NOT getMailboxLock: a held lock counts as the connection
    // being busy, so imapflow never enters IDLE and no 'exists' ever fires.
    // That is the shape the takanaka-watch listener settled on after the same
    // mistake; see src/engine/gmail-idle.js.
    const box = await client.mailboxOpen(opts.mailbox);
    let lastUid = Number(box && box.uidNext ? box.uidNext - 1 : 0) || 0;
    log('listening as ' + user + ' (creds from ' + source + '), mailbox ' + opts.mailbox +
        ' (' + ((box && box.exists) || 0) + ' msgs, acting on uid > ' + lastUid + '), ' +
        'for mail after ' + since.toISOString() + ', up to ' + opts.timeout + 's');

    let draining = false;
    let again = false;
    async function fetchNew() {
      const from = lastUid + 1;
      // A uid range ending in '*' always returns the last message even when its
      // uid is below `from`, so this guard is load-bearing, not defensive.
      for await (const msg of client.fetch({ uid: from + ':*' }, FIELDS, { uid: true })) {
        if (!msg || !msg.uid || msg.uid < from) continue;
        lastUid = Math.max(lastUid, msg.uid);
        await consider(msg);
        if (done) return;
      }
    }
    async function drain() {
      if (draining) { again = true; return; }
      draining = true;
      try {
        do {
          again = false;
          try { await fetchNew(); } catch (e) { log('fetch failed: ' + e.message); }
        } while (again && !done);
      } finally { draining = false; }
    }

    client.on('exists', () => { drain().catch(() => {}); });
    // A mail can land between mailboxOpen and the first IDLE; look once.
    await drain();

    // Catch-up for an explicit look-back: 'exists' only fires for mail that
    // arrives from now on, so anything already sitting between --since and
    // connect has to be swept.
    //
    // Not with IMAP SEARCH SINCE. Verified against this account on 2026-09-08:
    // SINCE compares whole days in the server's own timezone, and a mail with
    // internalDate 02:24Z *today* came back in zero results. A uid tail is
    // timezone-proof and needs no server-side date handling at all: walk back a
    // fixed number of uids from the head, take the envelopes only, and let
    // envelopeMatches do the date filtering.
    if (!done && opts.lookBack) {
      const from = Math.max(1, lastUid - opts.lookback + 1);
      log('look-back sweep over uid ' + from + ':' + lastUid);
      try {
        const heads = [];
        for await (const m of client.fetch(
          { uid: from + ':' + lastUid },
          { uid: true, envelope: true, internalDate: true },
          { uid: true },
        )) {
          if (m && m.uid && envelopeMatches(m.envelope, m.internalDate)) heads.push(m);
        }
        for (const m of heads.reverse()) {   // newest first: a fresh code wins
          if (done) break;
          await consider(m);
        }
      } catch (e) { log('look-back sweep failed: ' + e.message); }
    }

    while (!done && Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 500));
    }
  } catch (e) {
    log('IMAP error: ' + e.message);
    try { await client.logout(); } catch { /* already down */ }
    process.exit(2);
  }

  try { await client.logout(); } catch { /* already down */ }

  if (!result) {
    log('no matching code within ' + opts.timeout + 's');
    process.exit(3);
  }
  process.stdout.write((opts.json ? JSON.stringify(result) : result.code) + '\n');
  process.exit(0);
}

if (require.main === module) {
  main().catch((e) => { process.stderr.write('otp: ' + (e && e.stack || e) + '\n'); process.exit(2); });
}

module.exports = { extractCode, resolveSince, readEnvFile };
