# otp-fetch

Wait on IMAP for a one-time code and print it to stdout.

```
node ~/.claude/skills/otp-fetch/scripts/otp.js --from booking.com --timeout 180
```

## Why this exists

The ticketjam run on 2026-09-06 did not fail because the mail was unreadable.
It failed on **timing**: a human relayed each Google 2FA code by hand, and every
code had expired before PowerShell keystroke automation could type it. Reading
the mail after the fact is always a race you lose.

So the listener is armed *before* the site is asked to send anything. It holds
an IMAP IDLE connection open, and the code is in hand within a second or two of
Gmail receiving it.

```
Terminal A:  node otp.js --from booking.com --timeout 180
Terminal B:  ...click "send me a code"...
Terminal A prints:  483920
```

Or inline from a booking script:

```bash
CODE=$(node ~/.claude/skills/otp-fetch/scripts/otp.js --from booking.com) || exit 1
```

## Arming order matters

`--since` defaults to `now`, meaning process start. Mail that was already in the
inbox is **ignored**. This is deliberate: a stale code is worse than no code,
because it looks like success and fails at submit.

Use `--since -5m` only when you know the code was sent moments ago and you are
recovering from a crashed run.

## Options

| Option | Meaning |
|---|---|
| `--from <substr>` | Only mail whose From contains this (repeatable, case-insensitive substring, so `booking.com` catches `no-reply@mailer.booking.com`) |
| `--subject <regex>` | Only mail whose Subject matches |
| `--pattern <regex>` | Custom code pattern; capture group 1 is the code |
| `--since <spec>` | `now` (default), an ISO timestamp, or `-90s` / `-5m` |
| `--timeout <sec>` | Give up after this long (default 180) |
| `--lookback <n>` | How many uids back the `--since` sweep reaches (default 200) |
| `--mailbox <name>` | IMAP mailbox (default INBOX) |
| `--env-file <path>` | Read `GMAIL_IMAP_*` from this file first |
| `--json` | Print `{code, from, subject, receivedAt}` instead of the bare code |
| `--verbose` | Log every candidate mail to stderr |

Exit codes: `0` code on stdout · `3` timeout · `2` IMAP/auth failure · `1` bad usage.

Logs go to stderr, the code to stdout, so `$(...)` capture stays clean.

## Credentials

A Google **app password**, never the account password. Resolution order:

1. `GMAIL_IMAP_USER` / `GMAIL_IMAP_APP_PASSWORD` in the environment
2. `~/.secrets/gmail-imap.env`
3. `~/Code/takanaka-watch/.env` — where these already live today

Everything routable lands in this one mailbox: the personal domain is a catch-all
forwarding to it, so per-service addresses like `booking@<personal-domain>` arrive
here too.

## Layout

The code lives in `scripts/` (`otp.js`, `package.json`, `test/`). `node_modules` is
not committed: run `npm ci` in `scripts/` on a fresh checkout. `~/Code/otp-fetch` is a
symlink to `scripts/`, so callers that use the old path keep working.

Tests: `node scripts/test/extract.test.js`.

## Code extraction

Ordered, most-specific first:

1. A **labelled** six-digit run — `code`, `código`, `passcode`, `pin`, `otp`,
   `one-time`, `verification`, `verify`, `security`, `認証コード`, `確認コード`,
   `コード` — allowing words in between, so *"Your verification code is 55210"*
   and *"Tu código de verificación es 604815"* both work.
2. The same, relaxed to 4–8 digits.
3. Digits *before* the label: *"773311 is your verification code"*.
4. A labelled alphanumeric code (`A4F9K2`), required to be upper-case with at
   least one digit.
5. Fallback: a single unambiguous standalone six-digit run, only when the mail
   contains exactly one. Two runs means it is a reference number, not a code.

ASCII labels are word-bounded, so `pin` does not fire on "shipping". Digit runs
touching a letter, a currency symbol or a decimal point are never codes.

`--pattern` overrides all of it when a service does something strange.

## Two things that bit during the build

**Never hold a mailbox lock.** `getMailboxLock()` counts as the connection being
busy, so imapflow never enters IDLE and no `exists` event ever fires — the
listener sits there and times out while mail lands. Use `mailboxOpen()` and
react to `exists`, which is the shape `takanaka-watch/src/engine/gmail-idle.js`
settled on after the same mistake.

**IMAP `SEARCH SINCE` is not usable here.** It compares whole days in the
server's timezone. Verified on this account 2026-09-08: a mail with internalDate
`02:24Z` *today* came back in zero results. The `--since` sweep walks a uid tail
backwards instead and filters on `internalDate` client-side.

## Tests

```
npm test
```

Covers the extractor against real mail shapes (Booking.com, Google, Amazon,
iHerb, ticketjam, Spanish), the false-positive cases (prices, years, order
numbers, two-reference mails), and `--since` parsing. No network.

The IMAP path is verified by hand: arm the listener, send a mail to yourself,
confirm it prints the code and exits 0.
