---
name: otp-fetch
description: Use when a flow needs a one-time code, 2FA code, OTP, verification code or email confirmation code that arrives by email - logging into a site, confirming a booking, verifying a new account. Arms an IMAP listener before the code is sent so it never expires in transit. Triggers include "it wants a code", "check my email for the code", "2FA", "verification code", "enter the OTP".
---

# Fetching a one-time code from email

## The rule

**Arm the listener BEFORE clicking "send me a code".** Not after.

This is the whole point. On 2026-09-06 the ticketjam run collapsed because codes
were relayed by hand and every one had expired by the time it was typed. Reading
the mail after the fact is a race you lose.

## Do this

```bash
# 1. Arm it in the background FIRST
node ~/.claude/skills/otp-fetch/scripts/otp.js --from booking.com --timeout 180 > /tmp/otp.txt &

# 2. Now trigger the send-code step in the browser

# 3. Read it
cat /tmp/otp.txt
```

Or, when the browser step is scripted and can wait:

```bash
CODE=$(node ~/.claude/skills/otp-fetch/scripts/otp.js --from booking.com) || exit 1
```

Full options, credentials and extraction rules: `README.md` in this skill.
Bare code on stdout, logs on stderr. Exit `0` found · `3` timeout · `2` IMAP
failure · `1` bad usage.

## Narrowing the match

Always pass `--from` when you know the sender — it is a case-insensitive
substring of the From address, so `booking.com` catches
`no-reply@mailer.booking.com`. Add `--subject` when one sender mails about
several things at once (ticketjam sends listing alerts and 2FA from the same
domain).

If nothing matches, re-run with `--verbose` to see what arrived and was skipped,
then loosen the filter — do not widen `--since` first.

## Do not

- **Do not use `--since` to go fishing for an older code.** Default is `now`,
  and that is correct. A stale code looks like success and fails at submit. Use
  `--since -5m` only to recover from a crashed run where you know the code was
  just sent.
- **Do not poll the Gmail MCP in a loop** for this. It is slower, it burns
  context on every check, and it will hand you an old code from the thread.
  IDLE is push; the code arrives in about a second.
- **Do not paste the code into a shell command that gets logged.** Capture it in
  a variable and type it into the page.

## When it will not help

If the code goes to SMS, an authenticator app, or a native OAuth popup, this
tool cannot see it — no email is involved. Say so early and ask Javier to hand
the code over, rather than burning fifty turns on keystroke automation. That was
the other half of the ticketjam failure.

## Credentials

Reads a Google app password from `GMAIL_IMAP_USER` / `GMAIL_IMAP_APP_PASSWORD`,
then `~/.secrets/gmail-imap.env`, then `~/Code/takanaka-watch/.env`. Nothing to
set up; it already works. `<personal-domain>` is a catch-all onto that mailbox, so
per-service addresses like `booking@<personal-domain>` arrive there too.
