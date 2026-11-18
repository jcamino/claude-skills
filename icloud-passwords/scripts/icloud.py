"""Drive the iCloud Passwords extension in the main (logged-in) Chrome with no human.

usage:
  python icloud.py status [--title PART]          what state is it in; clicks nothing
  python icloud.py unlock [--title PART]          open the popup, read the code, type it
  python icloud.py pick USERNAME [--title PART]   fill a saved login into the page

The six-digit code iCloud shows when the extension locks or needs pairing appears in a
small iCloudPasswordsExtensionHelper window that is excluded from screen capture
(screenshots are black), but UI Automation reads its text. If the helper has no code,
the Windows notification database is checked too ("iCloud for Windows sent you a
notification with a verification code").

Exit codes: 0 ok / already unlocked, 1 no Chrome window with the extension button,
2 popup did not open, 3 no code found, 4 screen locked, 5 session disconnected
(run `reconnect`, see SKILL.md), 6 typed but still locked, 7 login not in the list.
"""
import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time

import uiautomation as auto

HERE = os.path.dirname(os.path.abspath(__file__))
auto.SetGlobalSearchTimeout(3)
sys.stdout.reconfigure(line_buffering=True)  # keep our lines in order with ostype.ps1's


def walk(ctrl, maxDepth):
    """auto.WalkControl as a list, retried: a page that changes mid-walk raises COMError."""
    for attempt in range(5):
        try:
            return list(auto.WalkControl(ctrl, maxDepth=maxDepth))
        except Exception as e:  # _ctypes.COMError, LookupError on a vanished element
            last = e
            time.sleep(0.4)
    raise last


class DesktopLock:
    """One driver of mouse and keyboard at a time across sessions sharing this desktop."""
    def __enter__(self):
        import msvcrt
        path = os.path.join(os.environ['TEMP'], 'icloud-passwords-skill.lock')
        self.f = open(path, 'a+')
        deadline = time.time() + 60
        while True:
            try:
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
                return self
            except OSError:
                if time.time() > deadline:
                    raise SystemExit('another icloud.py run has held the desktop for 60 s')
                time.sleep(0.5)

    def __exit__(self, *exc):
        import msvcrt
        self.f.seek(0)
        msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
        self.f.close()


# --- desktop state -----------------------------------------------------------

def session_state():
    """'Active', 'Disc' or something else, for the session this process runs in."""
    sid = None
    try:
        import ctypes
        pid = os.getpid()
        out = ctypes.c_ulong()
        if ctypes.windll.kernel32.ProcessIdToSessionId(pid, ctypes.byref(out)):
            sid = out.value
    except Exception:
        pass
    q = subprocess.run(['query', 'session'], capture_output=True, text=True).stdout
    for line in q.splitlines()[1:]:
        cols = line.lstrip('>').split()
        nums = [c for c in cols if c.isdigit()]
        if nums and int(nums[0]) == sid:
            i = cols.index(nums[0])
            return sid, (cols[i + 1] if i + 1 < len(cols) else '?')
    return sid, '?'


def screen_locked():
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq LogonUI.exe', '/FO', 'CSV', '/NH'],
                         capture_output=True, text=True).stdout
    return 'LogonUI.exe' in out


def check_desktop():
    """Return an exit code if nothing can be typed on this desktop, else None."""
    sid, state = session_state()
    if state.lower().startswith('disc'):
        print(f'SESSION {sid} DISCONNECTED: nothing can be clicked or typed until it is back on the console.')
        print(f'fix: python {os.path.join(HERE, "icloud.py")} reconnect   (one broker tap, no RDP)')
        return 5
    if screen_locked():
        print('SCREEN LOCKED (LogonUI is up): Windows needs the PIN at the lock screen; nothing here can type it.')
        return 4
    return None


# --- Chrome / popup ----------------------------------------------------------

def toolbar_button(w):
    for c, _ in walk(w, maxDepth=12):
        if c.ControlTypeName == 'ButtonControl' and (c.Name or '').startswith('iCloud Passwords'):
            return c
    return None


def chrome_window(title_part=None):
    """The Chrome window to use: --title match, else the foreground one, else any with the button."""
    wins = [w for w in auto.GetRootControl().GetChildren() if w.ClassName == 'Chrome_WidgetWin_1']
    if title_part:
        wins = [w for w in wins if title_part.lower() in (w.Name or '').lower()]
    fg = auto.GetForegroundControl()
    fg_handle = fg.NativeWindowHandle if fg else None
    wins.sort(key=lambda w: w.NativeWindowHandle != fg_handle)
    for w in wins:
        btn = toolbar_button(w)
        if btn:
            return w, btn
    return None, None


def popup(w):
    """(document, code boxes left to right, visible texts) of the open popup, or (None, [], [])."""
    for c, _ in walk(w, maxDepth=25):
        if c.ControlTypeName == 'DocumentControl' and c.Name == 'iCloud Passwords':
            kids = [k for k, _ in walk(c, maxDepth=25)]
            edits = [k for k in kids if k.ControlTypeName == 'EditControl']
            texts = [k.Name for k in kids if k.Name]
            return c, sorted(edits, key=lambda e: e.BoundingRectangle.left), texts
    return None, [], []


def click(ctrl):
    r = ctrl.BoundingRectangle
    auto.Click((r.left + r.right) // 2, (r.top + r.bottom) // 2)


def open_popup(w, btn, ready=lambda doc, boxes, texts: True):
    doc, boxes, texts = popup(w)
    if doc and ready(doc, boxes, texts):
        return doc, boxes, texts
    if not doc:
        click(btn)
    for _ in range(20):
        time.sleep(0.5)
        doc, boxes, texts = popup(w)
        if doc and ready(doc, boxes, texts):
            break
    return doc, boxes, texts


# --- the code ----------------------------------------------------------------

CODE_RE = re.compile(r'\b(\d{3})\s?(\d{3})\b')


def helper_code():
    out = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True).stdout
    pids = set()
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) > 1 and parts[0].lower().startswith('icloudpasswords'):
            pids.add(int(parts[1]))
    for w in auto.GetRootControl().GetChildren():
        if w.ProcessId in pids:
            text = ' '.join((c.Name or '') for c, _ in walk(w, maxDepth=12))
            m = CODE_RE.search(text)
            if m:
                return m.group(1) + m.group(2)
    return None


def toast_code(max_age_s=180):
    """Newest 6-digit code in an iCloud toast from the last few minutes, from a copy of the WPN db."""
    src = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Windows', 'Notifications', 'wpndatabase.db')
    if not os.path.exists(src):
        return None
    dst_dir = os.path.join(os.environ['TEMP'], 'icloud-passwords-skill')
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, 'wpn.db')
    for ext in ('', '-wal', '-shm'):
        if os.path.exists(src + ext):
            shutil.copy2(src + ext, dst + ext)
    con = sqlite3.connect(dst)
    try:
        rows = con.execute(
            'SELECT n.ArrivalTime, h.PrimaryId, n.Payload FROM Notification n '
            'LEFT JOIN NotificationHandler h ON n.HandlerId = h.RecordId '
            'ORDER BY n.ArrivalTime DESC LIMIT 40').fetchall()
    finally:
        con.close()
    now_ft = (time.time() + 11644473600) * 10_000_000
    for at, app, payload in rows:
        if at is None or now_ft - at > max_age_s * 10_000_000:
            continue
        if 'icloud' not in (app or '').lower():
            continue
        text = payload.decode('utf-8', 'replace') if isinstance(payload, bytes) else str(payload)
        body = ' '.join(re.findall(r'<text[^>]*>(.*?)</text>', text, re.S))
        m = CODE_RE.search(body)
        if m:
            return m.group(1) + m.group(2)
    return None


def find_code(wait_s=15):
    deadline = time.time() + wait_s
    while time.time() < deadline:
        code = helper_code()
        if code:
            return code, 'helper window'
        time.sleep(0.5)
    code = toast_code()
    return (code, 'notification') if code else (None, None)


def os_type(text):
    # uiautomation's SendKeys leaves the code boxes empty; Windows Forms SendKeys lands.
    subprocess.run(['pwsh', '-NoProfile', '-File', os.path.join(HERE, 'ostype.ps1'), '-Text', text], check=True)


# --- commands ----------------------------------------------------------------

def cmd_status(a):
    sid, state = session_state()
    print(f'session {sid}: {state}; screen locked: {screen_locked()}')
    w, btn = chrome_window(a.title)
    if not w:
        print('no Chrome window with the iCloud Passwords button'); return 1
    print(f'window: {w.Name!r}; toolbar button: {btn.Name!r}')
    doc, boxes, texts = popup(w)
    if not doc:
        print('popup: closed')
    else:
        print(f'popup: open, {"LOCKED (" + str(len(boxes)) + " code boxes)" if boxes else "unlocked"}; texts {texts[:10]}')
    code = helper_code()
    print(f'helper window code: {code or "none showing"}')
    return 0


def cmd_unlock(a):
    rc = check_desktop()
    if rc:
        return rc
    w, btn = chrome_window(a.title)
    if not w:
        print('NO CHROME WINDOW WITH THE iCLOUD PASSWORDS BUTTON (is the main Chrome profile open?)'); return 1
    doc, boxes, texts = open_popup(w, btn)
    if not doc:
        print('POPUP DID NOT OPEN'); return 2
    if not boxes:
        print('ALREADY UNLOCKED'); print('popup texts', texts[:12])
        if not a.keep_open:
            auto.SendKeys('{Esc}', waitTime=0.2)  # leave the page as it was
        return 0
    return enter_code(w, boxes, texts)


def enter_code(w, boxes, texts):
    """The popup is open and locked: read the code, type it, confirm the boxes are gone."""
    print('locked; popup says', texts[:6])
    code, source = find_code()
    if not code:
        print('NO CODE: neither the helper window nor a recent iCloud notification has one'); return 3
    print(f'code {code} (from {source})')
    click(boxes[0])
    time.sleep(0.3)
    os_type(code)
    for _ in range(10):
        time.sleep(0.5)
        doc, boxes, texts = popup(w)
        if not boxes:
            break
    if boxes:
        print('STILL LOCKED after typing; popup texts', texts[:12]); return 6
    print('UNLOCKED'); print('popup texts', texts[:12])
    return 0


def cmd_pick(a):
    rc = check_desktop()
    if rc:
        return rc
    w, btn = chrome_window(a.title)
    if not w:
        print('NO CHROME WINDOW WITH THE iCLOUD PASSWORDS BUTTON'); return 1
    has_user = lambda doc, boxes, texts: bool(boxes) or a.username in texts
    doc, boxes, texts = open_popup(w, btn, ready=has_user)
    if not doc:
        print('POPUP DID NOT OPEN'); return 2
    if boxes:  # it relocks often (seen within a minute); unlock on the spot
        rc = enter_code(w, boxes, texts)
        if rc:
            return rc
        doc, boxes, texts = open_popup(w, btn, ready=has_user)
        if not doc:
            print('POPUP CLOSED AFTER UNLOCK'); return 2
    item = next((c for c, _ in walk(doc, maxDepth=25)
                 if c.ControlTypeName == 'TextControl' and c.Name == a.username), None)
    if not item:
        print('LOGIN NOT IN THE LIST; popup texts', texts[:12]); return 7
    click(item)
    time.sleep(2)
    # Report what landed without ever printing the password.
    for c, _ in walk(w, maxDepth=25):
        if c.ControlTypeName == 'EditControl' and c.Name:
            try:
                v = c.GetValuePattern().Value
            except Exception:
                continue
            if 'pass' in c.Name.lower():
                print(c.Name, '=', f'<filled, {len(v)} chars>' if v else '<empty>')
            elif v:
                print(c.Name, '=', v)
    return 0


def cmd_reconnect(a):
    """Put a disconnected session back on the console (after an RDP disconnect), via the UAC broker."""
    sid, state = session_state()
    if not state.lower().startswith('disc'):
        print(f'session {sid} is {state}, nothing to do'); return 0
    broker = os.path.expanduser(r'~\Code\uac-broker\uac.ps1')
    why = ('iCloud Passwords needs its code typed into Chrome, and the desktop was left '
           'disconnected after an RDP session. This moves it back to the console so nothing '
           'needs RDP. The screen will be unlocked on the physical monitor.')
    r = subprocess.run(['pwsh', '-NoProfile', '-File', broker,
                        '-Command', f'tscon {sid} /dest:console', '-Why', why])
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('status', 'unlock', 'reconnect'):
        p = sub.add_parser(name)
        p.add_argument('--title')
        p.add_argument('--keep-open', action='store_true', help='unlock: leave the popup open')
    p = sub.add_parser('pick')
    p.add_argument('username')
    p.add_argument('--title')
    a = ap.parse_args()
    fn = {'status': cmd_status, 'unlock': cmd_unlock, 'pick': cmd_pick, 'reconnect': cmd_reconnect}[a.cmd]
    if a.cmd in ('unlock', 'pick'):
        with DesktopLock():
            sys.exit(fn(a))
    sys.exit(fn(a))


if __name__ == '__main__':
    main()
