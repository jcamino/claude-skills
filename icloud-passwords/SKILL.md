---
name: icloud-passwords
description: Use when the iCloud Passwords extension in the main Chrome is locked or asks for a code ("iCloud for Windows sent you a notification with a verification code", "Enter the code", "Enable Password AutoFill", six empty boxes), when it needs re-pairing, when a saved password or TOTP code from iCloud Keychain has to be filled into a login page, or whenever you are about to ask Javier to RDP in, look at the screen, or read a code off the PC. Unlocks and fills with no human, through UI Automation.
---

# iCloud Passwords: unlock and fill with no human

**Never ask Javier to RDP in to read the iCloud code.** The code is on this PC, and this
skill reads it and types it. The only things that need him are a locked Windows screen and
a broker tap after an RDP disconnect, both below.

```
python ~/.claude/skills/icloud-passwords/scripts/icloud.py status            # clicks nothing
python ~/.claude/skills/icloud-passwords/scripts/icloud.py unlock [--title PART]
python ~/.claude/skills/icloud-passwords/scripts/icloud.py pick USERNAME [--title PART]
python ~/.claude/skills/icloud-passwords/scripts/icloud.py reconnect         # after exit 5 only
```

`--title` is a case-insensitive part of the Chrome window title (the page title). Without
it the script uses the foreground Chrome window, else the first one that has the iCloud
Passwords toolbar button. Pass it whenever another session may be using Chrome, so you act
on your own window and not theirs. `unlock` takes 15 to 25 s.

## How it works

The extension lives only in the **main** Chrome profile (Default), not in Patchright/pb
profiles or the CDP profiles. When it locks or loses its pairing, the popup shows six code
boxes, and iCloud shows the code in a small `iCloudPasswordsExtensionHelper` window, bottom
right. That window is **excluded from screen capture** (screenshots come out black), which
is why it looked like a human had to read it. UI Automation reads its text fine.

`unlock`: opens the popup from the toolbar button, reads the code from the helper window
(falls back to the Windows notification database for the last 3 minutes), clicks the first
box, types the code with Windows Forms SendKeys (`scripts/ostype.ps1`), and checks the boxes
are gone. Already unlocked: it says so, presses Escape and exits 0 (`--keep-open` keeps
the popup up).

**It relocks often**: on 2026-11-18 it was locked again within a minute of an unlock, after
the window it was unlocked in closed. So never assume an earlier unlock still holds.

`pick USERNAME`: unlocks first if the popup is locked, then clicks that saved login so the
extension fills the page, and reports the filled fields. Password fields are reported as a length only, never the value.
TOTP codes saved in an entry are offered inline by the extension on the site's code step.

Traps already paid for:
- **uiautomation's own SendKeys leaves the boxes empty.** Only the Forms SendKeys lands.
- **Calling `SetActive()` on the Chrome window closes the popup** and the code with it.
- **Click the first box before typing**, or the keystrokes go nowhere.
- A page that changes mid-walk raises `COMError`; the script retries the walk.
- Two sessions typing at once corrupt each other: `unlock` and `pick` hold a lock file in
  `%TEMP%`, so a second run waits up to 60 s.
- Playwright's extension attach (`playwright-cli attach --extension`) drops its tab when the
  iCloud popup opens. Drive the popup with this script, then go back to the page.

## Exit codes and what to do

| Code | Meaning | Do |
|---|---|---|
| 0 | unlocked (or already was), or login filled | carry on |
| 1 | no Chrome window with the iCloud button | main Chrome is not open: start it (`chrome.exe --profile-directory=Default --new-window URL`) and retry |
| 2 | popup did not open | retry once; check the toolbar button with `status` |
| 3 | no code found | the helper may have restarted mid-request: press Escape to close the popup and run `unlock` again. Still nothing: `status`, and check `iCloudPasswordsExtensionHelper.exe` is running |
| 4 | Windows screen locked (LogonUI up) | the one real human step: Javier unlocks the PC with his PIN. Say exactly that, not "RDP in" |
| 5 | session disconnected (left behind by an RDP disconnect) | run `reconnect` (below) |
| 6 | typed the code but still locked | run the same command again (a code can expire mid-type) |
| 7 | that login is not in the popup list | the site has no saved entry under that username: say which entries the popup listed |

### `reconnect`: a disconnected session, no RDP

When an RDP client disconnects, the console session stays **Disc** with no display, and
nothing can click or type in it (UIA reads, input fails). `reconnect` asks the UAC broker to
run `tscon <session> /dest:console`, which moves the session back onto the physical console,
unlocked. That needs admin, so Javier gets **one Pushover tap** (it is not allowlisted on
purpose: it leaves the physical monitor showing an unlocked desktop). Exit 126 = denied,
127 = no answer; both are answers, do not retry. After a 0, run `unlock` again.

## Related

- `~/Code/finances/tools/icloud_unlock.py` and `icloud_pick.py` are the originals this was
  built from (2026-11-16). This skill's copy is the maintained one.
- Codes that arrive by email: the `otp-fetch` skill. By SMS: Google Voice into Gmail.
