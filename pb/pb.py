#!/usr/bin/env python
"""pb: a persistent Patchright browser for agents. One file = daemon + thin client.

The browser stays alive between calls. Each call is one short command over a local socket and
returns a compact observation: what changed, never the whole page.

  pb start [--profile NAME|DIR] [--secrets FILE] [--headless] [--window WxH] [URL]   launch (or reuse) the browser.
                              The window is at least 1366 wide, so sites serve their desktop layout
  pb open URL                 navigate, then print the view
  pb view [--all] [--grep RE] interactive elements of the page (all frames), with refs e1, e2...
  pb find TEXT                elements whose text/label matches, with refs (a link also shows its address: -> URL)
  pb click TARGET             TARGET = ref (e12) | visible text ("Add to Cart") | css=SELECTOR
                              add --near TEXT when many elements share the text: click Select --near "196 Main St"
                              (also for check, fill, select). --nth N: the Nth of equal matches, in page order (three
                              Delete buttons side by side). --right: a right-click, --double: a double-click.
                              Plain text that reacts to clicks (a sortable table header) is clicked when no control matches
  pb fill TARGET VALUE        TARGET = ref | label/placeholder/name text | css=SELECTOR. Also sliders (a range input, or
                              role=slider moved by keyboard: says the closest value it reached), and date / time / month
                              / color fields, in their own format or a human one ("12/25/2026", "Dec 25, 2026", "3:30 PM")
  pb fill TARGET VALUE --pick [TEXT]   a field with a suggestion list (autocomplete): types VALUE, waits for the list,
                              picks the entry that matches TEXT (default VALUE; --pick 1 = the first) and reads the field
                              back. Lists the suggestions and fails when none matches
  pb select TARGET OPTION     <select> and custom dropdowns (click, type, pick). pb select TARGET "A" "B" picks several
                              options of a <select multiple>
  pb check TARGET | pb uncheck TARGET   TARGET may be the text of a row or list item that holds one checkbox
  pb press KEY                keyboard key on the focused element (Enter, Tab, Escape, ctrl+a, shift+tab, esc...)
  pb type TEXT                type into the focused element with real key events
  pb text [REGEX]             page text (capped at 4000 characters), or only lines matching REGEX, in page order, each
                              with the line before and after (a line repeated right next to itself once, xN). Every
                              frame that shows is read, marked [frame NAME]. Pieces shown side by side are joined by
                              " | ", dates carry the year ("13 Nov (2026-11-13)"). A JSON, text or XML page is printed
                              as it is; a PDF tab is saved and read with pdftotext
     --from N                 continue a capped print at character N (the capped answer gives the exact command)
     --section HEADING        the text under that heading, to the next heading of the same or a higher level (6000 max).
                              Of several headings by that name the higher level comes first; --nth K takes another.
                              A heading in a collapsed part of the page is read from its hidden text, and says so
     --headings               the page's outline: every heading with its level (also: pb outline)
     --of TARGET              one element's whole text, then its href, value, datetime, title, aria-label, alt, src
     --context N              with REGEX: N lines before and after each match (default 1, at most 5)
  pb items [REGEX]            the page's repeated cards or rows (search results, listings) as records #1, #2...: their
                              text pieces joined by " | ", then -> the ref and address of the main link (pb click eN
                              opens it). First line: how many, which group,
                              and the other groups. REGEX keeps matching items (ads keep their "Sponsored")
     --n N | --from K         how many (default 10) and from which item number
     --in TARGET              another group: one named in the first line (a.nav-link), or the group holding a ref,
                              css=SELECTOR or a text
                              (text, links, table and items first wait for a page that is still loading, 6 s at most)
  pb wait TEXT | pb wait --gone TEXT | pb wait --ms N       rarely needed: every command waits for the page, and
                              for its target while the page is still loading. --timeout SECONDS (default 20);
                              --in TARGET: the text inside that one element (wait "75%" --in id=progressBar)
  pb do 'cmd; cmd; cmd'       several commands in one call, one observation at the end. Steps may span page loads.
                              Also pb do 'cmd' 'cmd'. A failed step (a find with no match too) stops the batch;
                              `try STEP` makes a step optional
  pb review                   what the page says about the order: final button, pickup/shipping, money, checkboxes,
                              filled fields, problems. Shown unasked after an action when the final button is enabled
  pb expect 'TEXT'...         check the page against the request, in code: each TEXT must be in the page text or
                              a visible field (whole words where TEXT starts/ends with a letter or digit).
     --in 'SECTION' 'TEXT'    ...in the block under that heading or label   --not 'TEXT'   must be absent
                              (--unchecked / --disabled pass when there is no such box / button at all)
     --unchecked 'LABEL' | --checked 'LABEL' | --enabled 'BUTTON' | --disabled 'BUTTON'
                              Prints PASS/FAIL per check plus the review; exit code 1 when a check fails.
                              Single-quote texts with a $ in them ("Total $29.79" loses "$29" to the shell)
  pb card [SECTION]           find the card fields (payment iframes included) and type the card from the
                              secrets file (SECTION: a card section of that file, default card1; month and year
                              dropdowns included). Prints ok/missing flags only, never the values. Fails (exit 1,
                              "CARD INCOMPLETE") when the number, expiry or security code is not in its field
  pb secret TARGET KEY        fill TARGET from the secrets file (card.number, card.cvc, card.exp, card.name,
                              buyer.email, buyer.phone, buyer.name). Value never printed
  pb eval JS                  evaluate JS in the page (main world), prints the result as JSON. Objects and arrays need
                              no JSON.stringify (that would encode them twice)
  pb eval -r JS               the same, but a string result is printed as it is
  pb py FILE | pb py -c CODE  run async Python against the live page (names: page, ctx, S). The API is async: await
                              its calls (`return await page.title()`; a returned coroutine is awaited for you)
  pb shot [--full] [TARGET] [PATH.png]   screenshot to a PNG, prints the path: the window, the whole page (--full) or
                              one element. Card fields and card numbers are painted over
  pb tabs | pb tab N | pb tab new [URL] | pb tab close [N] | pb back | pb forward | pb reload | pb status | pb stop
  pb window [WxH]             the window's size, or set it (pb window 420x900 to see a phone layout)
  pb recover                  the page froze (a command says so): reopen the same URL in a new tab
Browsing (a TARGET here may also be plain text on the page, an image's alt text or a title):
  pb scroll down|up [N]       N screens (default 1); the answer says where the page is and what is in view
  pb scroll top|bottom        bottom keeps going while an endless list loads more (15 rounds max), says how much came
  pb scroll TARGET            bring an element or a text into view, also inside a box with its own scrollbar
  pb hover TARGET             move the mouse over it: menus, tooltips and captions it opens are in the answer, and stay
                              open for the next step: pb do 'hover Products; hover More; click Archive'
  pb drag SOURCE TARGET       drag and drop (HTML5 drag events and pages that follow the mouse)
  pb upload TARGET FILE...    TARGET = the file field, or the button / label that opens the file chooser. Relative
                              FILE paths start in your directory. Says which files the field holds
  pb download TARGET|URL [PATH]  save what a link or image points to (a PDF, a file) with the browser's cookies.
                              Downloads any action starts are saved too: "DOWNLOAD saved PATH (N bytes)" in its answer,
                              into your directory, never over a file (name-1.ext)
  pb links [REGEX]            links with their addresses (text or address matching REGEX), count first, 40 at most
  pb table [N|TEXT] [--rows A-B]  no argument: one line per table. N or TEXT (caption, header, heading above, or a
                              cell): its rows as cells joined by " | ", header first, 40 rows unless --rows. Div grids too
  pb dialog accept [TEXT] | pb dialog dismiss   what to do with the NEXT JS alert / confirm / prompt (default: accept),
                              if it comes during the rest of the batch (pb do 'dialog dismiss; click Delete'), or, given
                              as a command of its own, during the next command. Every dialog is reported in a NOTE
Global option: -s SESSION (default: one session per working directory).

Card data never appears in anything pb prints or logs: card numbers (from the secrets file or not), and the CVV and
expiry where a field value shows, are replaced before the text leaves the daemon.
Timing of every request goes to ~/.pb/SESSION.timing.jsonl (tools/timing_dump.py reads it).
"""
import contextlib
import json
import os
import re
import socket
import sys
import time

# The client must start fast, so what only the daemon needs is imported only there (asyncio alone costs 0.17 s a call).
if __name__ != "__main__" or sys.argv[1:2] == ["__serve"]:
    import asyncio
    import io
    import shlex
    import textwrap

STATE_DIR = os.path.join(os.path.expanduser("~"), ".pb")
DEFAULT_SECRETS = os.path.join(os.path.expanduser("~"), "Code", "payments.env")
MAX_LINES = 70
MAX_CHARS = 7000
TRACE = bool(os.environ.get("PB_TRACE"))       # the daemon was started with PB_TRACE=1: more notes in the timing log

# ----------------------------------------------------------------------------------------- client


def default_session():
    """One session per working directory. The name is the lowercased path with every other character turned into "_"
    (last 70 characters), so that the bash client (tools/pb) can work it out with builtins alone. Keep the two in step."""
    return os.environ.get("PB_SESSION") or "cwd-" + re.sub(r"[^a-z0-9]", "_", os.getcwd().lower().replace("\\", "/"))[-70:]


def local_path(p, cwd=None):
    """A file path given on a pb command line, as this process must open it. The bash client passes arguments
    untouched, so a Git Bash path (/c/Users/x, /tmp/x) arrives as typed, and relative paths are relative to the
    caller's directory, not the daemon's."""
    if os.name == "nt":
        m = re.match(r"^/([a-zA-Z])/(.*)$", p)
        if m:
            p = f"{m.group(1).upper()}:/{m.group(2)}"
        elif p.startswith("/tmp/"):
            import tempfile
            p = os.path.join(tempfile.gettempdir(), p[5:])
        if cwd:
            m = re.match(r"^/([a-zA-Z])(/.*)?$", cwd)
            if m:
                cwd = f"{m.group(1).upper()}:{m.group(2) or '/'}"
    return os.path.abspath(os.path.join(cwd, p) if cwd and not os.path.isabs(p) else p)


def state_path(session):
    return os.path.join(STATE_DIR, session + ".json")


def load_state(session):
    try:
        with open(state_path(session), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def alive(st):
    try:
        socket.create_connection(("127.0.0.1", st["port"]), timeout=1).close()
        return True
    except Exception:
        return False


def rpc(session, args, timeout=300):
    st = load_state(session)
    if not st or not alive(st):
        return "ERR no browser running for this session. Run: pb start [URL]"
    s = socket.create_connection(("127.0.0.1", st["port"]), timeout=3)
    s.settimeout(timeout)
    s.sendall((json.dumps({"args": args, "cwd": os.getcwd()}) + "\n").encode("utf-8"))
    chunks = []
    while True:
        b = s.recv(65536)
        if not b:
            break
        chunks.append(b)
    s.close()
    return b"".join(chunks).decode("utf-8", "replace")


def client_start(session, args):
    opts, url, i = {}, None, 0
    while i < len(args):
        a = args[i]
        if a == "--profile":
            opts["profile"] = args[i + 1]
            i += 2
        elif a == "--secrets":
            opts["secrets"] = os.path.abspath(args[i + 1])
            i += 2
        elif a == "--headless":
            opts["headless"] = True
            i += 1
        elif a == "--window":
            if i + 1 >= len(args) or not re.fullmatch(r"\d{3,5}x\d{3,5}", args[i + 1]):
                print("ERR usage: pb start --window WIDTHxHEIGHT (for example 1366x900)")
                sys.exit(1)
            opts["window"] = args[i + 1]
            i += 2
        else:
            url = a
            i += 1
    st = load_state(session)
    if st and alive(st):
        print(f"already running (profile {st.get('profile')})")
    else:
        os.makedirs(STATE_DIR, exist_ok=True)
        with contextlib.suppress(Exception):
            os.remove(state_path(session))
        import subprocess
        log = open(os.path.join(STATE_DIR, session + ".log"), "ab")
        cmd = [sys.executable, "-I", os.path.abspath(__file__), "__serve", session, json.dumps(opts)]
        flags = (0x08000000 | 0x00000200) if os.name == "nt" else 0   # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=flags, close_fds=True)
        t0 = time.time()
        while time.time() - t0 < 40:
            st = load_state(session)
            if st and alive(st):
                break
            time.sleep(0.03)
        else:
            print("ERR browser did not start; see " + os.path.join(STATE_DIR, session + ".log"))
            sys.exit(1)
        print(f"ready in {time.time() - t0:.1f}s (profile {st.get('profile')})")
    if url:
        print(rpc(session, ["open", url]), end="")


def client_main():
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")
    argv = sys.argv[1:]
    session = None
    if argv[:1] == ["-s"] and len(argv) >= 2:
        session, argv = argv[1], argv[2:]
    session = session or default_session()
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return
    if argv[0] == "start":
        client_start(session, argv[1:])
        return
    out = rpc(session, argv)
    sys.stdout.write(out if out.endswith("\n") else out + "\n")
    if out.startswith("ERR") or "\nERR at step `" in out or out.startswith("EXPECT FAILED") or "\nEXPECT FAILED" in out:
        sys.exit(1)


# ----------------------------------------------------------------------------------------- page JS

COLLECT_JS = r"""
(arg) => {
  const t_start = performance.now();
  let n = arg.next;
  const T = (s, m) => { s = (s == null ? '' : String(s)).replace(/[\u200b-\u200f\u2060\ufeff]/g, '').replace(/\s+/g, ' ').trim(); return (m && s.length > m) ? s.slice(0, m - 1) + '…' : s; };
  // Pages wider than the window (aliexpress: Add to cart sits right of it) can be scrolled sideways, so what lies within
  // the page's width counts. Off-canvas menus parked beyond that edge are fixed boxes, which do not widen the page.
  const W = Math.max(window.innerWidth || 0, document.documentElement ? document.documentElement.scrollWidth : 0) || 1e6;
  const rendered = (el) => {
    if (el.checkVisibility && !el.checkVisibility({ checkVisibilityCSS: true })) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    // Past the right edge: a drawer parked there and marked hidden is not shown (clinicaltrials.gov's glossary), but a
    // calendar wider than a narrow window still is (Google Flights: the Thursday to Saturday days of its dialog lay past
    // the edge, and `click "January 15, 2027"` found no such day)
    if (r.right <= 0) return false;
    if (r.left >= W - 1) {
      if (el.closest('[aria-hidden="true"]')) return false;
      // part of a box that starts inside the window and runs past its edge (that calendar): shown; a drawer whose own
      // box lies past the edge: not
      for (let p = el.parentElement, i = 0; p && p !== document.body && i < 25; p = p.parentElement, i++) {
        const ps = getComputedStyle(p).position;
        if (ps === 'fixed' || ps === 'absolute' || p.matches('[role=dialog],dialog')) { const q = p.getBoundingClientRect(); return q.left < W - 1 && q.width > 0; }
      }
      return r.left <= W + 40;
    }
    return true;
  };
  // Open dialogs. Besides the marked ones, a box that sits on top of the page counts: shops build add-to-cart sheets,
  // sign-in prompts and cookie notices as fixed boxes over a backdrop with no role at all (lowes, shein, hm). Two cheap
  // looks: what lies at the middle of the window, and the visible boxes whose class says modal / popup / drawer (those
  // are noted during the one walk over the page, see visit; a selector search of its own cost 8 ms on ebay). Runs after
  // that walk; the region of what it found is set then.
  const DLG = '[role=dialog],[role=alertdialog],[aria-modal="true"],dialog[open]';
  const DLGCLS = /modal|dialog|popup|drawer|overlay/i, DLGID = /modal|popup/i;
  const dlgRoots = [], dlgCands = [];
  const items = [], els = [];           // els[i]: the element behind items[i]
  // a layer over the whole window at a point beside the box: its wrapper, or a backdrop with no text of its own
  const scrimBeside = (el, r) => {
    const VW = window.innerWidth || 1, VH = window.innerHeight || 1, VA = VW * VH;
    const left = Math.max(0, r.left), right = Math.max(0, VW - r.right);
    if (left < 20 && right < 20) return false;
    const x = left >= right ? left / 2 : (r.right + VW) / 2, y = VH / 2;
    for (let p = document.elementFromPoint(x, y); p && p !== document.body && p !== document.documentElement; p = p.parentElement) {
      // (fixed only: an app shell drawn absolute over the whole page holds everything, youtube's ytd-app)
      if (getComputedStyle(p).position !== 'fixed') continue;
      const q = p.getBoundingClientRect();
      if (q.width * q.height >= 0.9 * VA && (p.contains(el) || T(p.innerText).length < 40)) return true;
    }
    return false;
  };
  const findDialogs = () => {
    if (!arg.text || !document.body) return;
    const VW = window.innerWidth || 1, VH = window.innerHeight || 1, VA = VW * VH;
    const hasCtl = (el) => !!el.querySelector('button,a[href],input,select,textarea,iframe,[role=button],[role=link]');
    const zi = (cs) => parseInt(cs.zIndex) || 0;
    const layer = (el) => { const cs = getComputedStyle(el); return (cs.position === 'fixed' && zi(cs) >= 1) || (cs.position === 'absolute' && zi(cs) >= 100); };
    const area = (r) => Math.max(0, Math.min(r.right, VW) - Math.max(r.left, 0)) * Math.max(0, Math.min(r.bottom, VH) - Math.max(r.top, 0));
    const boxy = (r) => r.width >= 160 && r.height >= 60 && area(r) > 0 && area(r) < 0.9 * VA;
    const onTop = (el, r) => { const t = document.elementFromPoint(Math.min(Math.max(r.left + r.width / 2, 1), VW - 1), Math.min(Math.max(r.top + r.height / 2, 1), VH - 1));
                               return !!t && (t === el || el.contains(t)); };
    const add = (el) => { if (!el.closest(DLG) && !dlgRoots.some(d => d.contains(el) || el.contains(d))) dlgRoots.push(el); };
    // youtube's guide: a drawer (class "...-drawer", fixed, the window's full height, at its left edge, role=navigation)
    // that sits beside the page and blocks none of it. A navigation panel is a dialog only with a backdrop over the
    // rest of the window (the same drawer in a narrow window comes with one). A shop's mini-cart drawer, which an
    // action opens, is not navigation and still counts.
    const isNav = (el) => !!(el.closest('nav,[role=navigation]') || el.querySelector(':scope > nav, :scope > [role=navigation]'));
    const nonModalPanel = (el, r) => el.getAttribute('aria-modal') !== 'true' && isNav(el) && !scrimBeside(el, r);
    try {
      const top = document.elementFromPoint(VW / 2, VH / 2);
      if (top && !top.closest(DLG)) {
        const chain = [];
        for (let p = top; p && p !== document.body && p !== document.documentElement && chain.length < 40; p = p.parentElement) chain.push(p);
        const li = chain.findIndex(layer);
        if (li >= 0) {
          const L = chain[li], lr = L.getBoundingClientRect();
          // a layer that fills the window is a wrapper (backdrop + box) or an app shell: only a box inside it counts,
          // and only when the wrapper is stacked high, as overlays are and app shells are not
          const full = area(lr) >= 0.9 * VA;
          if (!full || zi(getComputedStyle(L)) >= 10) {
            let box = null;
            for (let i = li; i >= 0; i--) { const r = chain[i].getBoundingClientRect(); if (boxy(r) && (!full || area(r) < 0.7 * VA) && hasCtl(chain[i])) { box = chain[i]; break; } }
            // the middle of a wide window can fall on the backdrop below a box that sits higher up (react.html's sheet
            // at 1366 wide): the box is then a stacked sibling of the backdrop
            if (!box && full && li === 0) {
              for (const s of [L.nextElementSibling, L.previousElementSibling, L.nextElementSibling && L.nextElementSibling.nextElementSibling]) {
                if (!s || !layer(s)) continue;
                const r = s.getBoundingClientRect();
                if (boxy(r) && area(r) < 0.7 * VA && hasCtl(s) && onTop(s, r)) { box = s; break; }
              }
            }
            if (box && !nonModalPanel(box, box.getBoundingClientRect())) add(box);
          }
        }
      }
      let k = 0;
      for (const el of dlgCands) {
        if (++k > 80) break;
        if (el === document.body || el === document.documentElement || dlgRoots.some(d => d.contains(el))) continue;
        const r = el.getBoundingClientRect();
        if (!boxy(r) || hiddenBox(el)) continue;
        let p = el, lay = false;
        for (let i = 0; i < 4 && p && p !== document.body; i++, p = p.parentElement) if (layer(p)) { lay = true; break; }
        if (lay && hasCtl(el) && onTop(el, r) && !nonModalPanel(el, r)) add(el);
      }
    } catch (e) {}
    if (dlgRoots.length) for (let i = 0; i < items.length; i++) if (dlgRoots.some(d => d.contains(els[i]))) items[i].reg = 'dialog';
  };
  const inDlg = (el) => !!realDlg(el) || (dlgRoots.length > 0 && dlgRoots.some(d => d.contains(el)));
  // A box marked as a dialog that does not cover or block the page is part of the page: finance.yahoo.com's side dock
  // (role=dialog aria-modal=true, sticky in the page's flow, taller than the window) and linkedin's "Open the app" box
  // (fixed in a corner, no aria-modal, no backdrop). Their controls are listed with the page's. Asked of marked
  // dialogs only, a handful per page.
  const dockSet = new Set();
  const docked = (el) => {
    try { if (el.tagName === 'DIALOG' && el.matches(':modal')) return false; } catch (e) {}
    const VW = window.innerWidth || 1, VH = window.innerHeight || 1;
    let pos = '';
    for (let p = el, i = 0; p && i < 60; i++) {
      const ps = getComputedStyle(p).position;
      if (ps === 'fixed' || ps === 'absolute') { pos = ps; break; }
      p = p.parentElement || (p.parentNode && p.parentNode.host) || null;
    }
    const r = el.getBoundingClientRect();
    // in the page's flow (a wrapper of no size may hold a fixed box: not judged here)
    if (!pos) return r.width >= 2 && r.height >= 2 && (r.height > 0.9 * VH || !!el.closest('main,[role=main]'));
    if (pos !== 'fixed' || el.getAttribute('aria-modal') === 'true') return false;
    // a navigation panel the window's height, at its left or right edge, with no backdrop beside it (a guide drawer)
    if (r.height >= 0.7 * VH && r.width <= 0.45 * VW && (r.left <= 40 || r.right >= VW - 40) && el.closest('nav,[role=navigation]')
        && !scrimBeside(el, r)) return true;
    return r.width < 0.5 * VW && r.height < 0.5 * VH && (r.left < 40 || r.right > VW - 40) && (r.top < 40 || r.bottom > VH - 40);
  };
  // the nearest marked dialog around el that is a real one
  const realDlg = (el) => { let d = el.closest(DLG); while (d && dockSet.has(d)) d = d.parentElement ? d.parentElement.closest(DLG) : null; return d; };
  // A dialog the page keeps loaded but out of sight (hm.com's cookie settings): aria-hidden, see-through, hidden, or
  // parked beyond the window's left or right edge (or above or below it, for a fixed one). Its controls are no more
  // usable than its title is readable. Asked of dialogs only, a handful per page.
  const hiddenBox = (el) => {
    if (el.getAttribute('aria-hidden') === 'true') return true;
    if (el.checkVisibility && !el.checkVisibility({ checkVisibilityCSS: true, opacityProperty: true })) return true;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;            // a wrapper of no size whose box is a fixed child
    if (r.right <= 0 || r.left >= W) return true;
    return (r.bottom <= 0 || r.top >= (window.innerHeight || 1)) && getComputedStyle(el).position === 'fixed';
  };
  const byId = (el, id) => { const root = el.getRootNode(); return (root.getElementById ? root.getElementById(id) : null) || document.getElementById(id); };
  const labelOf = (el) => {
    let s = el.getAttribute('aria-label');
    if (s && T(s)) return T(s);
    const lb = el.getAttribute('aria-labelledby');
    if (lb) { const t = T(lb.split(/\s+/).map(id => { const e = byId(el, id); return e ? e.textContent : ''; }).join(' ')); if (t) return t; }
    const l0 = labels.get(el); if (l0) { const t = T(l0.textContent); if (t) return t; }
    const wrap = el.closest('label'); if (wrap) { const t = T(wrap.textContent); if (t) return t; }
    if (el.placeholder) return T(el.placeholder);
    if (el.title) return T(el.title);
    return '';
  };
  // control -> its first <label>, filled per document or shadow root by visit. Asking each control for el.labels makes
  // the browser search the document from the top every time: 2 s on a page with 1500 quantity selects.
  const labels = new Map();
  // Card fields and passwords only. Hints are cut into words first (cardCvv -> card cvv), so "csc" inside another word
  // (discsCount) does not count, and autocomplete=new-password, which address boxes use to stop autofill, is ignored.
  const SENS = { test: (s) => /\bcc (number|num|csc|cvv|cvc|exp\w*)\b|\bcard ?(num|number|no)\b|\bcardnumber\b|\bpan\b|\b(cvv|cvc|csc|cvn)\d?\b|\bsecurity ?code\b|\bexpir|\bexp ?(date|month|year|mm|yy)\b|\bmm ?yy\b|\bpassw/.test(
    String(s).replace(/\b(new|current)-password\b/gi, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').replace(/[^A-Za-z0-9]+/g, ' ').toLowerCase()) };
  // (an <a> with no href and an element with an onclick attribute are controls too: uitestingplayground's mouseover link)
  const INTER ='input,textarea,select,button,a[href],a:not([href]):not([name]),[onclick]:not([onclick=""]),summary,[role=button],[role=link],[role=combobox],[role=checkbox],[role=radio],[role=switch],[role=tab],[role=menuitem],[role=option],[role=slider],[contenteditable=""],[contenteditable="true"]';
  // What an element and everything below it inherits, kept as bits while walking: inside a marked dialog, inside the
  // page's header / navigation / footer, inside a control. (Asking each element with closest() cost 12 ms on a page of
  // 1200 controls, and the text of every wrapper was read in full, megabytes on pages that ship their state inline.)
  const F_DLG = 1, F_CHROME = 2, F_INTER = 4, F_PROSE = 8;
  const PROSE = { P: 1, BLOCKQUOTE: 1, DD: 1 };          // running text: its links are counted, not listed, on long articles
  const HEADING = { H1: 1, H2: 1, H3: 1, H4: 1, LEGEND: 1 };
  const CHROME = { HEADER: 1, NAV: 1, FOOTER: 1 }, CHROME_ROLE = { navigation: 1, banner: 1, contentinfo: 1 };
  const NOWALK = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEMPLATE: 1, HEAD: 1 };       // nothing in these is on the page
  const ERRCLS = /(^|[\s_-])(error|invalid|field-error|form-error|alert-danger|errormessage|error-message)([\s_-]|$)/i;
  const shadowRoots = [], frameEls = [];
  let sec = '', lastLink = null;
  // Nothing is written to the page while it is being read: an attribute written between two layout questions makes
  // the browser work out styles again for each (the first scan of a page cost a third more than the next ones).
  // Refs are given out at the end, in document order (see stamp).
  const put = (el, o, at) => {
    if (at == null || at >= items.length) { items.push(o); els.push(el); }
    else { items.splice(at, 0, o); els.splice(at, 0, el); }
  };
  const push = (el, o, fl, at, sc) => {
    o.ref = el.getAttribute('data-pb') || '';
    o.sec = sc == null ? sec : sc;
    o.reg = (fl & F_DLG) ? 'dialog' : ((fl & F_CHROME) ? 'chrome' : 'main');
    if ((fl & F_PROSE) && o.k === 'link') o.pr = 1;
    put(el, o, at);
  };
  // a long name cut at a word boundary, short of m characters (a headline of about 120 stays whole)
  const ELL = String.fromCharCode(8230), unell = (s) => (s.endsWith(ELL) ? s.slice(0, -1) : s);
  const TW = (s, m) => { s = T(s); if (s.length <= m) return s; let c = s.slice(0, m - 1); const i = c.lastIndexOf(' '); if (i > m * 0.6) c = c.slice(0, i); return c.replace(/[\s,;:.-]+$/, '') + ELL; };
  const textOf = (el) => {
    let t = TW(el.innerText, 120);
    if (!t) { const img = el.querySelector('img[alt]'); t = TW(el.getAttribute('aria-label') || el.title || (img ? img.alt : ''), 120); }
    if (!t && el.getAttribute('aria-labelledby')) {
      // a box whose name is printed next to it (the reCAPTCHA tick box: "I'm not a robot")
      t = T(el.getAttribute('aria-labelledby').split(/\s+/).map(id => { const e = byId(el, id); return e ? e.textContent : ''; }).join(' '), 70);
    }
    return t;
  };
  // A control: one line of the view.
  const control = (el, tag, role, fl) => {
    const al = T(el.getAttribute('aria-label'), 40);
    const dis = !!el.disabled || el.getAttribute('aria-disabled') === 'true';
    if (tag === 'INPUT') {
      const it = (el.getAttribute('type') || 'text').toLowerCase();
      if (it === 'hidden') return;
      const lab = labelOf(el);
      if (it === 'checkbox' || it === 'radio') {
        const labEl = labels.get(el) || el.closest('label');
        if (!rendered(el) && !(labEl && rendered(labEl))) return;
        push(el, {k: it, t: T(lab, 70), name: el.name || '', on: !!el.checked, dis}, fl);
      } else if (it === 'submit' || it === 'button' || it === 'reset' || it === 'image') {
        if (!rendered(el)) return;
        push(el, {k: 'button', t: T(el.value || lab || el.alt, 70), dis}, fl);
      } else {
        if (!rendered(el)) return;
        if (el.getAttribute('aria-hidden') === 'true' || (dis && !lab)) return;
        const sens = it === 'password' || el.hasAttribute('data-pb-secret') || SENS.test([el.autocomplete, el.name, el.id, el.placeholder, lab].join(' '));
        let v = el.value || '';
        let itx = it, labx = lab, shows = '';
        if (role === 'combobox' || el.getAttribute('aria-autocomplete')) {
          // custom dropdown / autocomplete: the visible choice lives in a wrapper, not in the input
          itx = 'combobox';
          let p = el, shown = '';
          for (let i = 0; i < 4 && p.parentElement && !shown; i++) { p = p.parentElement; shown = T(p.innerText, 40); }
          if (!v && shown) {
            if (labx) v = shown;
            else {
              labx = shown;
              // no label of its own and a value box showing, no placeholder: the text is the chosen value (demoqa react-select)
              if (!p.querySelector('[class*="placeholder" i]') && p.querySelector('[class*="value" i],[class*="selected" i]')) shows = shown;
            }
          }
        }
        const o = {k: 'input', it: itx, t: T(labx, 70), name: el.name || el.id || '', ph: T(el.placeholder, 60), v: sens ? (v ? '•x' + v.length : '') : T(v, v === el.value ? 300 : 40),
                   dis: dis || !!el.readOnly, req: !!el.required, inv: el.getAttribute('aria-invalid') === 'true', ac: el.getAttribute('autocomplete') || ''};
        if (shows && !sens) o.shows = shows;
        if (!dis && el.readOnly) o.ro = 1;        // printed as read-only: its value is sent with the form, unlike a disabled one's
        if (!el.name && el.id) o.nid = 1;         // the hint printed is its id (pb view says id=, as a selector would need)
        // a search box whose label does not say so (jcpenney: "What can we help you find?"): `fill Search` finds it
        if (it === 'search' || role === 'searchbox' || el.closest('[role=search]')) o.srch = 1;
        push(el, o, fl);
      }
    } else if (tag === 'TEXTAREA') {
      if (!rendered(el)) return;
      // (its line breaks shown as \n: "two lines" read as one line of two words)
      push(el, {k: 'input', it: 'textarea', t: T(labelOf(el), 70), name: el.name || el.id || '', v: T(el.value.replace(/\r?\n/g, '\\n'), 300), dis}, fl);
    } else if (tag === 'SELECT') {
      if (!rendered(el)) return;
      const opts = [...el.options].map(o => T(o.textContent, 28));
      let slab = labelOf(el);
      const own = T(el.textContent);
      if (own && slab.includes(own)) slab = T(slab.replace(own, ''));
      // an expiry month or year pb picked from the secrets file shows as a dot, like any other secret field
      const sv = T(el.selectedOptions[0] ? el.selectedOptions[0].textContent : '', 40);
      push(el, {k: 'select', t: T(slab, 70), name: el.name || el.id || '', v: el.hasAttribute('data-pb-secret') && el.selectedIndex > 0 ? '•' : sv,
                n: opts.length, opts: opts.length <= 12 ? opts : null, dis}, fl);
    } else {
      if (!rendered(el)) return;
      let k = 'button';
      if (tag === 'A' || role === 'link') k = 'link';
      else if (role === 'combobox') k = 'combo';
      else if (role === 'checkbox' || role === 'radio' || role === 'switch') k = role === 'switch' ? 'checkbox' : role;
      else if (role === 'tab' || role === 'menuitem' || role === 'option') k = role;
      else if (role === 'slider' || (el.isContentEditable && tag !== 'BUTTON')) k = 'input';
      const o = {k, t: textOf(el), dis};
      if (al && o.t && !T(el.innerText)) o.ao = 1;      // its name is only its aria-label (pb's score weighs that less)
      // a custom slider is filled like a field (pb fill moves it with the keyboard); its value is aria-valuenow
      if (k === 'input') { o.it = role === 'slider' ? 'slider' : 'editable'; o.v = T(role === 'slider' ? (el.getAttribute('aria-valuetext') || el.getAttribute('aria-valuenow')) : el.innerText, 40); o.t = T(labelOf(el), 70); }
      // an aria-label that says what the text says (both cut short, at different lengths) is not printed twice
      if (al && al !== o.t) { const a0 = unell(al), t0 = unell(o.t || ''); if (t0.length < 20 || a0.length < 20 || !(t0.startsWith(a0) || a0.startsWith(t0))) o.al = al; }
      if (k === 'link' && tag === 'A') {
        // the same link again in the same card (linkedin: a job's title link three times): one line, counted
        const h = el.getAttribute('href') || '';
        if (lastLink && lastLink.h === h && lastLink.o.t === o.t && items.length - lastLink.n <= 3 && items[lastLink.n - 1] === lastLink.o && o.al === lastLink.o.al && h && h !== '#') {
          lastLink.o.rep = (lastLink.o.rep || 1) + 1;
          return;
        }
        lastLink = { h, o, n: items.length + 1 };
      }
      const on = el.getAttribute('aria-checked') || el.getAttribute('aria-selected') || el.getAttribute('aria-pressed');
      if (on != null) o.on = on === 'true';
      const ex = el.getAttribute('aria-expanded'); if (ex != null) o.exp = ex === 'true';
      if (!o.t && !o.al) o.t = '[' + T(el.id || (typeof el.className === 'string' ? el.className.split(' ')[0] : '') || tag.toLowerCase(), 30) + ']';
      // a calendar day ("15"): the date it stands for, from its own label, a date attribute, or the cell around it
      // (Google Flights and amtrak keep "Friday, January 15, 2027" on the cell, not on the button)
      // (a day may show its price too: "22 $753" on Google Flights)
      if (!(o.al && /[a-z]{3}/i.test(o.al) && /\d/.test(o.al))) { const dl = dayLabel(el, o.t); if (dl) o.dl = dl; }
      push(el, o, fl);
    }
  };
  // the date a calendar day ("15", "22 $753") stands for: from its own label, one inside it, a date attribute, or the
  // cell around it (Google Flights keeps "Friday, January 15, 2027" on a box inside the button, amtrak on the cell)
  const dayLabel = (el, t) => {
    if (!/^\d{1,2}(\s[^\s]{1,12})?$/.test(t || '')) return '';
    let dl = '';
    const inner = el.querySelector('[aria-label]');
    for (let p = inner || el, i = 0; p && i < 4 && !dl; p = p === inner ? el : p.parentElement, i++) {
      const a = p.getAttribute('aria-label') || '', dd = p.getAttribute('data-iso') || p.getAttribute('data-date') || p.getAttribute('data-day') || '';
      if (/[a-z]{3}/i.test(a) && /\d/.test(a) && a.length < 60) dl = a; else if (/^\d{4}-\d\d-\d\d/.test(dd)) dl = dd.slice(0, 10);
    }
    return dl ? T(dl, 60) : '';
  };
  // One walk over a document or shadow root, in document order. For every open element a stack keeps what its children
  // inherit (sFl), the length of the text below it so far (sLen), whether a control lies below it (sHas), where its own
  // line would go and under which heading (sAt, sSec), what is still to be decided when its children are done (sKind)
  // and its cursor once somebody asked for it (sCur).
  const visit = (root) => {
    // the few elements that carry a role, a live region or a control are found in one native search each
    const marked = new Set(root.querySelectorAll('[role],[aria-live],[aria-modal]'));
    const inter = new Set(root.querySelectorAll(INTER));
    const tabs = new Set(root.querySelectorAll('[tabindex]:not([tabindex^="-"])'));
    for (const l of root.querySelectorAll('label')) { const c = l.control; if (c && !labels.has(c)) labels.set(c, l); }
    const sEl = [], sFl = [], sLen = [], sHas = [], sAt = [], sSec = [], sKind = [], sCur = [];
    const cursorOf = (i) => { let c = sCur[i]; if (c === undefined) c = sCur[i] = getComputedStyle(sEl[i]).cursor; return c; };
    let d = -1, cur = root.firstChild;
    for (;;) {
      if (!cur) {
        if (d < 0) break;
        const el = sEl[d], kind = sKind[d], len = sLen[d];
        if (kind === 1) {
          // generic clickable: the top of a cursor:pointer chain with short text and no real control inside
          if (len > 0 && len <= 90 && !sHas[d]) {
            const tc = el.textContent || '';
            // or a box a person can Tab to and nothing else says is a control (nordstrom's address finder: a div with
            // tabindex=0 and its prompt as text, no role, no pointer cursor)
            if (T(tc) && ((cursorOf(d) === 'pointer' && (d === 0 ? !(el.parentElement && getComputedStyle(el.parentElement).cursor === 'pointer') : cursorOf(d - 1) !== 'pointer'))
                          || (len <= 60 && tabs.has(el) && el.tabIndex >= 0)) && rendered(el))
            {
              const o = {k: 'click', t: T(el.innerText || tc, 70)}, dl = dayLabel(el, o.t);
              if (dl) o.dl = dl;                    // (amtrak's calendar: the days are clickable cells, the date in their aria-label)
              push(el, o, sFl[d], sAt[d], sSec[d]);
            }
          }
        } else if (kind === 2) {
          if (!el.control && !el.querySelector('input,select,textarea') && cursorOf(d) === 'pointer' && rendered(el) && T(el.textContent))
            push(el, {k: 'click', t: T(el.innerText, 70)}, sFl[d], sAt[d], sSec[d]);
        }
        if (kind && el.childElementCount === 0) {
          // inline error text
          const c = el.className;
          if (typeof c === 'string' && c && ERRCLS.test(c)) {
            const t = T(el.textContent, 160);
            if (t.length >= 3 && rendered(el)) put(el, {k: '!', t});
          }
        }
        const has = sHas[d];
        d--;
        if (d >= 0) { sLen[d] += len; if (has) sHas[d] = true; }
        cur = el.nextSibling;
        continue;
      }
      const nt = cur.nodeType;
      if (nt !== 1) {
        if ((nt === 3 || nt === 4) && d >= 0) sLen[d] += cur.length;
        cur = cur.nextSibling;
        continue;
      }
      const el = cur, tag = el.tagName;
      if (NOWALK[tag]) {
        if (d >= 0 && tag !== 'HEAD') sLen[d] += el.textContent.length;       // script text is part of textContent
        cur = el.nextSibling;
        continue;
      }
      if (el.shadowRoot) { shadowRoots.push(el.shadowRoot); visit(el.shadowRoot); }
      let fl = d >= 0 ? sFl[d] : 0;
      const pin = (fl & F_INTER) !== 0;
      let role = null, live = false;
      if (marked.has(el)) {
        role = el.getAttribute('role');
        live = role === 'alert' || role === 'status' || el.getAttribute('aria-live') === 'assertive';
        if (role === 'dialog' || role === 'alertdialog' || el.getAttribute('aria-modal') === 'true') {
          if (hiddenBox(el)) { cur = el.nextSibling; continue; }       // nothing in it can be seen or used
          if (docked(el)) dockSet.add(el); else fl |= F_DLG;
        }
        if (CHROME_ROLE[role]) fl |= F_CHROME;
      }
      if (PROSE[tag]) fl |= F_PROSE;
      if (CHROME[tag]) fl |= F_CHROME;
      else if (tag === 'DIALOG' && el.hasAttribute('open')) { if (docked(el)) dockSet.add(el); else fl |= F_DLG; }
      if (arg.text) { const c = el.className; if ((typeof c === 'string' && c && DLGCLS.test(c)) || (el.id && DLGID.test(el.id))) dlgCands.push(el); }
      const isInter = inter.has(el);
      let kind = 0;
      if (HEADING[tag] || role === 'heading') {
        if (rendered(el)) { const t = T(el.textContent, 70); if (t) { sec = t; put(el, (fl & F_DLG) ? {k: 'h', t, reg: 'dialog'} : {k: 'h', t}); } }
      } else if (live) {
        if (rendered(el)) { const t = T(el.textContent, 160); if (t) put(el, (fl & F_DLG) ? {k: '!', t, reg: 'dialog'} : {k: '!', t}); }
      } else if (isInter) {
        control(el, tag, role, fl);
      } else if (tag === 'LABEL') {
        kind = 2;
      } else if (tag !== 'HTML' && tag !== 'BODY') {
        // kind 3: only the error-text rule can apply (inside a control, or too many children for a generic clickable)
        kind = (!pin && el.childElementCount <= 4) ? 1 : 3;
      }
      if (isInter) fl |= F_INTER;
      if (tag === 'SELECT' || tag === 'IFRAME' || tag === 'FRAME') {
        // nothing below these is a line of its own: options belong to their select, a frame is scanned by itself
        if (tag !== 'SELECT') frameEls.push(el);
        if (d >= 0) { sLen[d] += el.textContent.length; if (isInter) sHas[d] = true; }
        cur = el.nextSibling;
        continue;
      }
      d++;
      sEl[d] = el; sFl[d] = fl; sLen[d] = 0; sHas[d] = isInter; sAt[d] = items.length; sSec[d] = sec; sKind[d] = kind; sCur[d] = undefined;
      cur = el.firstChild;
    }
  };
  visit(document);
  const t_walk = performance.now();
  findDialogs();
  // Does the dialog around a heading or a password field stand in for the page: a box over most of the window, or one
  // that blocks the page (a modal <dialog>, a backdrop over the rest) and offers no way to close it? booking.com's
  // "Sign in, save money" box covers a fifth of the window, over results it leaves in place, and has a Dismiss button:
  // a sign-in wall is one that covers or replaces the content. Asked for those items only, a few per page.
  if (arg.text) {
    const VW = window.innerWidth || 1, VH = window.innerHeight || 1, VA = VW * VH;
    const CLOSE = /^(close|dismiss|no,? thanks|not now|maybe later|skip|cancel|continue as guest|x|×|✕|✖)\b|\b(close|dismiss)\b/i;
    const closable = (d) => [...d.querySelectorAll('button,a,[role=button]')].slice(0, 40).some(b =>
      CLOSE.test(T(b.getAttribute('aria-label') || '')) || CLOSE.test(T(b.innerText || '')) || CLOSE.test(T(b.getAttribute('title') || '')));
    const blocks = (d) => {
      const r = d.getBoundingClientRect();
      const a = Math.max(0, Math.min(r.right, VW) - Math.max(r.left, 0)) * Math.max(0, Math.min(r.bottom, VH) - Math.max(r.top, 0));
      if (a >= 0.6 * VA) return true;
      if (closable(d)) return false;
      try { if (d.tagName === 'DIALOG' && d.matches(':modal')) return true; } catch (e) {}
      let n = 0, hit = 0;
      for (const [x, y] of [[0.08, 0.5], [0.92, 0.5], [0.5, 0.08], [0.5, 0.92], [0.15, 0.15], [0.85, 0.85]]) {
        const px = x * VW, py = y * VH;
        if (px >= r.left && px <= r.right && py >= r.top && py <= r.bottom) continue;
        n++;
        // what lies there is a layer over the whole window: the dialog's own wrapper, or a backdrop with no text
        for (let p = document.elementFromPoint(px, py); p && p !== document.body && p !== document.documentElement; p = p.parentElement) {
          if (getComputedStyle(p).position !== 'fixed') continue;
          const q = p.getBoundingClientRect();
          if (q.width * q.height >= 0.9 * VA && (p.contains(d) || T(p.innerText).length < 40)) { hit++; break; }
        }
      }
      return n > 0 && hit * 2 >= n;
    };
    const memo = new Map();
    for (let i = 0; i < items.length; i++) {
      const o = items[i];
      if (o.reg !== 'dialog' || !(o.k === 'h' || (o.k === 'input' && o.it === 'password'))) continue;
      const el = els[i], d = realDlg(el) || dlgRoots.find(x => x.contains(el));
      if (!d) continue;
      if (!memo.has(d)) memo.set(d, blocks(d));
      o.cov = memo.get(d) ? 1 : 0;
    }
  }
  const t_dlg = performance.now();
  /*PBLINES*/
  const text = [];
  if (arg.text && document.body) {
    for (const s of pbLines(shadowRoots)) {
      text.push(s.length > 200 ? s.slice(0, 199) + '…' : s);
      if (text.length >= 800) break;
    }
  }
  const t_text = performance.now();
  // The frame elements of this document: which of them show, how big, how much of the window each covers and whether
  // it sits inside a dialog (see flag_human). The daemon looks into the frames that show and leaves the others alone.
  /*PBFRAMES*/
  const frames = pbFrames(frameEls, rendered, arg.text ? inDlg : null);
  // Now the writes. Refs in document order. A ref that a second element carries (the page cloned a node pb had
  // stamped) stays with the first one; the other gets a fresh ref, so a ref always means one element.
  const seen = new Set();
  for (let i = 0; i < items.length; i++) {
    const o = items[i];
    if (!('ref' in o)) continue;
    if (!o.ref || seen.has(o.ref)) { o.ref = 'e' + (n++); els[i].setAttribute('data-pb', o.ref); }
    seen.add(o.ref);
  }
  pbStampFrames(frames);
  const t_end = performance.now();
  // A challenge box drawn in the page itself: PerimeterX's press and hold (#px-captcha, its modal arrives after the first
  // paint and its frame has no telling address: target.com headless), Cloudflare's full-page challenge, DataDome's box
  let hc = '';
  if (arg.text) {
    for (const e of document.querySelectorAll('#px-captcha,[id^="px-captcha"],.px-captcha-container,#challenge-stage,#challenge-running,form#challenge-form,#ddv1-captcha-container,.captcha-delivery')) {
      const r = e.getBoundingClientRect();
      if (r.width >= 100 && r.height >= 40 && (!e.checkVisibility || e.checkVisibility({ checkVisibilityCSS: true }))) { hc = '#' + (e.id || e.className || e.tagName).toString().split(' ')[0]; break; }
    }
  }
  return JSON.stringify({items, next: n, title: document.title, url: location.href, text, frames, hc, ms: Math.round(t_end - t_start),
                         prof: [t_walk - t_start, t_dlg - t_walk, t_text - t_dlg, t_end - t_text].map(Math.round)});
}
"""

# What a document knows about its frame elements, for Session.shown_children: each one's stamp (data-pbf, so that the
# daemon has to ask Chrome only once which frame an element holds), whether it shows, its size, the share of the window
# it covers and whether it is inside a dialog. Asking every frame for its own element and visibility instead cost two
# round trips per frame on every scan: 0.5 to 3 s on pages with 20 to 60 ad and sync frames.
FRAMEINFO_JS = r"""
  const AD_FRAME = /^(google_ads_iframe|aswift_|google_ads_frame|ad_iframe)/i;
  const AD_HOST = /^https?:\/\/[^\/]*(doubleclick\.net|googlesyndication\.com|adnxs\.com|amazon-adsystem\.com|taboola\.com|outbrain\.com|criteo\.(com|net)|adsafeprotected\.com|moatads\.com|pubmatic\.com|rubiconproject\.com|openx\.net)\//i;
  const pbFrames = (list, rendered, inDlg) => {
    const VW = window.innerWidth || 1, VH = window.innerHeight || 1, VA = VW * VH;
    const count = {};
    for (const f of list) { const id = f.getAttribute('data-pbf'); if (id) count[id] = (count[id] || 0) + 1; }
    return list.map((f) => {
      const r = f.getBoundingClientRect();
      const a = Math.max(0, Math.min(r.right, VW) - Math.max(r.left, 0)) * Math.max(0, Math.min(r.bottom, VH) - Math.max(r.top, 0));
      const id = f.getAttribute('data-pbf');
      // a stamp that two frame elements carry (the page cloned one) says nothing about either: both get a new one
      const o = { el: f, id: id && count[id] === 1 ? id : '', vis: rendered(f), w: Math.round(r.width), h: Math.round(r.height), src: f.src || '',
                  cover: Math.round(a / VA * 100) / 100, dlg: inDlg ? inDlg(f) : false };
      // an ad slot (demoqa: about:blank frames the ad script fills, listing [cbb] and [aw0] buttons): never read
      if (AD_FRAME.test(f.id || '') || AD_FRAME.test(f.name || '') || AD_HOST.test(o.src) || (f.closest && f.closest('ins.adsbygoogle'))) o.ad = 1;
      return o;
    });
  };
  const pbStampFrames = (frames) => {
    for (const f of frames) {
      if (!f.id) { f.id = 'f' + Math.random().toString(36).slice(2, 10); f.el.setAttribute('data-pbf', f.id); }
      delete f.el;
    }
  };
"""
COLLECT_JS = COLLECT_JS.replace("/*PBFRAMES*/", FRAMEINFO_JS)

# The same list without a scan of the page, for commands that only need to know which frames show (text, shot, card).
FRAMES_JS = r"""
() => {
  const W = Math.max(window.innerWidth || 0, document.documentElement ? document.documentElement.scrollWidth : 0) || 1e6;
  const rendered = (el) => {
    if (el.checkVisibility && !el.checkVisibility({ checkVisibilityCSS: true })) return false;
    const r = el.getBoundingClientRect();
    return r.width >= 2 && r.height >= 2 && r.right >= 0 && r.left <= W + 40;
  };
  const list = [];
  const walk = (root) => {
    for (const f of root.querySelectorAll('iframe,frame')) list.push(f);
    for (const el of root.querySelectorAll('*')) if (el.shadowRoot) walk(el.shadowRoot);
  };
  walk(document);
  /*PBFRAMES*/
  const frames = pbFrames(list, rendered, null);
  pbStampFrames(frames);
  return JSON.stringify(frames);
}
""".replace("/*PBFRAMES*/", FRAMEINFO_JS)

CARD_JS = r"""
() => {
  const T = (s) => (s == null ? '' : String(s)).replace(/\s+/g, ' ').trim();
  const out = [];
  const seen = new Set();
  let i = 0;
  const visit = (root) => {
    for (const el of root.querySelectorAll('*')) {
      if (el.shadowRoot) visit(el.shadowRoot);
      if (el.tagName !== 'INPUT' && el.tagName !== 'SELECT') continue;
      const it = (el.getAttribute('type') || 'text').toLowerCase();
      if (['hidden', 'checkbox', 'radio', 'submit', 'button', 'file', 'image', 'reset'].includes(it)) continue;
      if (el.checkVisibility && !el.checkVisibility({ checkVisibilityCSS: true })) continue;
      const r = el.getBoundingClientRect();
      const sel = el.tagName === 'SELECT';
      // a disabled expiry select is kept: some shops (macys) enable month and year only once the number field is left
      if (r.width < 2 || r.height < 2 || el.readOnly || (el.disabled && !sel)) continue;
      // Inputs that are there for the browser's autofill only, not for a person: a few pixels wide, inside an aria-hidden
      // block, or out of reach of mouse and Tab key alike (Cybersource puts three of them next to its number field, one
      // with autocomplete=cc-name). Typing into one makes the widget start the card over: the real field is emptied.
      if (!sel && (r.width < 8 || r.height < 8 || el.closest('[aria-hidden="true"]')
                   || (el.tabIndex < 0 && getComputedStyle(el).pointerEvents === 'none'))) continue;
      // A field keeps the stamp an earlier search gave it: pb card searches again when fields show up late, and the
      // fields it has typed into must still be found under their old stamp for the read-back at the end.
      let id = el.getAttribute('data-pbc');
      if (!id || seen.has(id)) { id = 'pbc' + Math.random().toString(36).slice(2, 9) + (i++); el.setAttribute('data-pbc', id); }
      seen.add(id);
      out.push({id, tag: el.tagName, ac: (el.getAttribute('autocomplete') || '').toLowerCase(), name: el.name || '', eid: el.id || '',
                ph: el.placeholder || '', lab: labelOf(el), ml: el.maxLength || 0, cls: typeof el.className === 'string' ? el.className : '',
                dft: el.getAttribute('data-fieldtype') || el.getAttribute('data-elements-stable-field-name') || '',
                dis: !!el.disabled, kind: sel ? selKind(el) : ''});
    }
  };
  visit(document);
  return out;
}
"""

# What a <select> lists, judged by its options: 'month' (twelve months, as numbers or names), 'year' (years from about
# now on, so a birth-year list does not count) or ''. Shared by CARD_JS and PICK_JS.
SELKIND_JS = r"""
  const MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
  const monthName = (t) => { const ws = t.toLowerCase().split(/[^a-z]+/); return MONTHS.findIndex(m => ws.some(w => w.length >= 3 && w.startsWith(m) && (w.length === 3 || 'january february march april may june july august september october november december'.includes(w)))); };
  const selKind = (el) => {
    const yNow = new Date().getFullYear();
    let m = 0, y = 0, past = 0;
    const nums = [];
    for (const o of el.options) {
      const t = (o.textContent || '').replace(/\s+/g, ' ').trim(), v = String(o.value || '').trim();
      if (!t && !v) continue;
      const y4 = (t + ' ' + v).match(/\b(19|20)\d\d\b/);
      if (y4) { if (+y4[0] >= yNow - 1) y++; else past++; continue; }
      if (monthName(t) >= 0) { m++; continue; }
      if (/^\d{1,2}$/.test(t)) nums.push(+t);
      else if (!/\d/.test(t) && /^\d{1,2}$/.test(v)) nums.push(+v);
    }
    if (nums.length >= 12 && nums.every(d => d >= 1 && d <= 12)) m += nums.length;
    else if (nums.length >= 5 && nums.every(d => d >= (yNow % 100) - 1)) y += nums.length;
    if (m >= 12 && m <= 13 && !y) return 'month';
    if (y >= 5 && !past && !m) return 'year';
    return '';
  };
"""

CARD_JS = CARD_JS.replace("  const out = [];", SELKIND_JS + r"""
  const byId = (el, id) => { const root = el.getRootNode(); return (root.getElementById ? root.getElementById(id) : null) || document.getElementById(id); };
  // the field's name as a person reads it: aria-label, aria-labelledby (hobbylobby's cardholder field had only that),
  // its <label>, or a label wrapped around it alone. A select's own options are not part of its name.
  const labelOf = (el) => {
    const parts = [el.getAttribute('aria-label')];
    const lb = el.getAttribute('aria-labelledby');
    if (lb) parts.push(lb.split(/\s+/).map(x => { const e = byId(el, x); return e ? e.textContent : ''; }).join(' '));
    let l = el.labels && el.labels[0];
    if (!l) { const w = el.closest('label'); if (w && w.querySelectorAll('input,select,textarea').length === 1) l = w; }
    if (l) parts.push(el.tagName === 'SELECT' ? l.textContent.replace(el.textContent, '') : l.textContent);
    parts.push(el.title);
    return T(parts.filter(Boolean).join(' ')).slice(0, 120);
  };
  const out = [];""", 1)

# The option of an expiry <select> that means the card's month (1-12) or year (two digits), whatever its value and label
# look like: "4", "04", "04 - April", "April" (with a 0-based value), "Apr", "2030", "30". part '' = judge by the options.
# Answers {kind, i: option index or -1, sel: index selected now, dis}.
PICK_JS = r"""
(e, [part, mm, yy]) => {
""" + SELKIND_JS + r"""
  const kind = part || selKind(e);
  let best = -1, bs = 0;
  [...e.options].forEach((o, i) => {
    const t = (o.textContent || '').replace(/\s+/g, ' ').trim(), v = String(o.value || '').trim();
    let s = 0;
    if (kind === 'month') {
      const n = t.match(/^0?(\d{1,2})\b/), name = monthName(t), nv = v.match(/^0?(\d{1,2})$/);
      if (n) s = +n[1] === mm ? 3 : 0;
      else if (name >= 0) s = name + 1 === mm ? 3 : 0;
      else if (nv && !t) s = +nv[1] === mm ? 1 : 0;
    } else if (kind === 'year') {
      const y4 = (t + ' ' + v).match(/\b20(\d\d)\b/);
      if (y4) s = +y4[1] === yy ? 3 : 0;
      else if (/^\d{2}$/.test(t)) s = +t === yy ? 3 : 0;
      else if (!t && /^\d{2}$/.test(v)) s = +v === yy ? 1 : 0;
    }
    if (s > bs) { bs = s; best = i; }
  });
  return { kind, i: best, sel: e.selectedIndex, dis: !!e.disabled };
}
"""

PSP_HOSTS = re.compile(r"cybersource|stripe|braintree|adyen|squarecdn|squareup|shopifycs|shopify|authorize\.net|checkout\.com|spreedly|"
                       r"worldpay|paymentus|payeezy|firstdata|elavon|globalpay|bluesnap|recurly|chasepaymentech|moneris|paypal|securepay|"
                       r"tokenex|vantiv|heartland|nmi|usaepay|bambora|pci|vault|oppwa|payment", re.I)
NOT_CARD = re.compile(r"gift|promo|coupon|reward|loyalty|voucher|store.?credit|\bpin\b|discount|search|zip|postal|phone|email", re.I)

# Requests that never mean "the page is still working": ad tags, analytics, session replay, consent banners.
# They often stay pending for many seconds, so waiting for them made every click cost the full cap.
TRACKERS = re.compile(
    r"doubleclick|google-analytics|googletagmanager|googleadservices|googlesyndication|analytics\.google|google\.[a-z.]+/(pagead|ads|ccm|gen_204)|"
    r"facebook\.(com|net)|launchdarkly|paypal\.com/xoplatform/logger|grafana|newrelic|nr-data\.net|datadoghq|browser-intake|sentry\.io|"
    r"hotjar|clarity\.ms|tiktok|bat\.bing|criteo|adsrvr\.org|quantummetric|fullstory|segment\.(io|com)|mparticle|optimizely|branch\.io|braze|"
    r"medallia|qualtrics|pinterest|snapchat|ads-twitter|linkedin\.com/(li|px)|adnxs|taboola|outbrain|demdex|omtrdc|everesttech|tealium|tiqcdn|"
    r"go-mpulse|akstat|bzr(cdn)?\.openai|cookielaw|onetrust|trustarc|bazaarvoice|yotpo|powerreviews|monetate|dynamicyield|evergage|amplitude|mixpanel|"
    r"heapanalytics|mouseflow|contentsquare|glassbox|dynatrace|usabilla|pendo\.io|reddit(static)?\.com|sc-static\.net|nextdoor\.com|mgln\.ai|"
    r"rt8x\.net|online-metrix\.net|klarnacdn|gstatic\.com/retail|unbxdanalytics|paypal\.com/(sdk|credit-presentment)", re.I)
BEACON_PATH = re.compile(r"/(collect|beacons?|telemetry|rum|pixel|ping|heartbeat)(/|$)", re.I)
# The shop's own calls for side content. They are often the slowest on the page (2.6 s for the home page's
# recommendations while everything else was there after 1.6 s) and nothing a visitor does next depends on them.
SECONDARY = re.compile(r"recommend|related|upsell|cross.?sell|carousel|banners?|reviews?|ratings?|personali[sz]|similar|recently.?viewed|"
                       r"trending|popular|wish.?list|notifications?|survey|feedback", re.I)
THIRD_PARTY_REPORT = re.compile(r"/(events?|view|track(ing)?|log(ger|s)?|glog|rp|pixels?|config|init|collect|beacons?|ping|metrics|analytics|"
                                r"impressions?|conversions?|tags?)(/|\.js|\.json|$)|pixel|analytics", re.I)
# The shop's own reporting: calls that tell the shop what the visitor did. They go to the shop's own site, often to a
# host made for it (smetrics., analytics., a first-party door to an ad network), so the tracker list does not know
# them. They answer late or never and no page waits for them, yet they were what most capped waits were held by
# (abt.nike.com/ee/.../interact, fbcapig2.mkt.samsung.com, www.chewy.com/api/event, www.nordstrom.com/.../metrics).
REPORT_HOST = re.compile(r"^(s?metrics|sstats|securemetrics|analytics[a-z0-9-]*|clickstream|telemetry|collect(or)?|rum|logs?|logger|tags?|tiqc?|"
                         r"(fb)?capig\d*|(api-)?sgtm|scout|beacons?|pixels?|trk|experimentation|sherlock[a-z0-9-]*|unagi)\.", re.I)
REPORT_PATH = re.compile(r"/(metrics?\d*|analytics|clickstream|log(s|ger|ging)?|impressions?|measurement|com\.snowplowanalytics[a-z.]*|tp2|userevents|"
                         r"event-collection|send-beacon|akam|pagead|tag_path|dthandler)(/|$)|/ee/([a-z0-9]+/)?v\d+/(interact|collect|identity)|"
                         r"/d/(ccm|measurement|pagead)/|/rb_[0-9a-z-]{8,}|/fp/(tags\.js|clear\.png)|trackevent|sponsoredadevent|logpagemetrics|"
                         r"visitorsmetric|logclienterrors|dl-event|ruxitagent|utag[./-]|boomerang", re.I)
# The shop's own calls for things beside the point of an action: recommendation and ad slots, experiments and flags,
# event streams, chat, consent. Some pages do wait for them, so they count, but briefly (see Session.relevance).
BACKGROUND = re.compile(r"/([a-z-]*recs?(-svc)?|recos?|sponsored[a-z-]*|ads?|[a-z-]*display-ads|adserver|experiments?|feature-?flags?|switches|events?|"
                        r"signals?|track(ing|er)?|enticements?|[a-z-]*chat(bot)?[a-z-]*|[a-z-]*consent[a-z-]*|i18n|translations?|locali[sz]ation)(/|$|\.)|"
                        r"getsponsoredads|getrecitem|winning-ads", re.I)
TWO_PART_TLD = {"co.uk", "org.uk", "com.au", "co.nz", "co.jp", "com.br", "com.mx", "co.in", "com.sg", "com.tr", "co.kr", "com.cn", "com.ar", "co.za"}

# One cheap round trip that answers: is the page alive, is it the same document, has its DOM changed, is it animating.
# Lives in the isolated world, so the page's own scripts cannot see it. Attribute stamps written by pb itself are ignored.
PROBE_JS = r"""
() => {
  let q = window.__pbq;
  if (!q) {
    q = window.__pbq = { t0: performance.now(), last: performance.now(), n: 0, nc: 0, ev: 0, slots: [] };
    // Only changes a person could see count: scripts, styles, tracking pixels and hidden frames that ad tags keep
    // adding and removing do not, and neither does anything inside <head>.
    const skip = { SCRIPT: 1, STYLE: 1, LINK: 1, META: 1, NOSCRIPT: 1, TEMPLATE: 1, TITLE: 1, BASE: 1 };
    const text = (nd) => !!(nd.nodeValue && nd.nodeValue.trim());
    const added = (nd) => nd.nodeType === 3 ? text(nd) : nd.nodeType === 1 && !skip[nd.tagName]
      && !((nd.tagName === 'IMG' || nd.tagName === 'IFRAME') && nd.offsetWidth * nd.offsetHeight <= 16);
    const removed = (nd) => nd.nodeType === 3 ? text(nd) : nd.nodeType === 1 && !skip[nd.tagName] && nd.tagName !== 'IMG' && nd.tagName !== 'IFRAME';
    // Loading signs that come or change while pb watches (a "Loading..." line, a loader image, a spinner box): kept as
    // candidates, and each probe says which of them show (ldn). Only what changed is looked at, so this costs nothing
    // on a still page. Settle holds its answer while one shows that did not show before the action.
    q.ldc = [];
    const IND = '[id*="loading" i],[id*="loader" i],[id*="spinner" i],[class*="spinner" i],[class*="loader" i],[class*="loading" i],'
      + 'img[src*="loader" i],img[src*="spinner" i],img[src*="loading" i],progress:not([value]),[role=progressbar]:not([aria-valuenow])';
    const LDTXT = /^(loading|please wait|wait for it|one moment|just a moment|processing|searching|updating)\b/i;
    q.IND = IND; q.LDTXT = LDTXT;
    const keep = (el) => { if (!q.ldc.includes(el)) q.ldc.push(el); };
    const cand = (el, deep) => {
      if (!el || el.nodeType !== 1 || q.ldc.length >= 40 || el === document.body || el === document.documentElement) return;
      try {
        if (el.matches(IND)) return keep(el);
        if (el.childElementCount <= 4) { const t = el.textContent; if (t && t.length <= 40 && LDTXT.test(t.trim())) return keep(el); }
        if (deep && el.firstElementChild) { const f = el.querySelector(IND); if (f) keep(f); }
      } catch (e) {}
    };
    new MutationObserver((recs) => {
      let any = false;
      for (const r of recs) {
        const t = r.target, el = t.nodeType === 1 ? t : t.parentElement;
        if (el && (skip[el.tagName] || el.tagName === 'HEAD' || (el.closest && el.closest('head')))) continue;
        let sig = false;
        if (r.type === 'attributes') sig = !/^data-pb/.test(r.attributeName || '');
        else if (r.type === 'characterData') sig = true;
        else { for (const nd of r.addedNodes) if (added(nd)) { sig = true; break; }
               if (!sig) for (const nd of r.removedNodes) if (removed(nd)) { sig = true; break; } }
        if (!sig) continue;
        if (r.type === 'childList') { cand(el, false); for (const nd of r.addedNodes) if (nd.nodeType === 1) cand(nd, true); }
        else cand(el, false);
        any = true; q.n++;
        if (r.type === 'childList') q.nc++;
      }
      if (!any) return;
      q.last = performance.now();
      const s = Math.floor(q.last / 250);
      if (q.slots[q.slots.length - 1] !== s) { q.slots.push(s); if (q.slots.length > 16) q.slots.shift(); }
    }).observe(document, { subtree: true, childList: true, attributes: true, characterData: true });
    const bump = () => { q.ev++; };
    document.addEventListener('input', bump, true);
    document.addEventListener('change', bump, true);
  }
  // anim: short animations still running (a panel sliding in). ld: visible "still loading" signs: an endlessly
  // repeating animation (a spinner turning, a skeleton shimmering), busy regions, progress bars, loader class names.
  let anim = 0, ld = 0;
  const shown = (el) => {
    if (el.checkVisibility && !el.checkVisibility({ checkVisibilityCSS: true })) return false;
    const r = el.getBoundingClientRect();
    return r.width > 4 && r.height > 4 && r.bottom > 0 && r.top < innerHeight;
  };
  try {
    for (const a of document.getAnimations()) {
      if (a.playState !== 'running') continue;
      const tm = a.effect && a.effect.getComputedTiming ? a.effect.getComputedTiming() : null;
      if (!tm) continue;
      if (isFinite(tm.endTime)) { if (tm.endTime - (a.currentTime || 0) < 1500) anim++; }
      else if (ld < 9 && a.effect.target && shown(a.effect.target)) ld++;
    }
  } catch (e) {}
  // The class-name search walks the whole document (16 ms on a large page), and this probe runs many times a second
  // during a wait: that would take a real share of the page's own CPU time. So its result is reused for 300 ms, and
  // for a second while the DOM has not changed since (a loader that comes or goes changes it).
  const t_now = performance.now();
  if (q.ldAt == null || t_now - q.ldAt > (q.ldN === q.n ? 1000 : 300)) {
    let k = 0;
    try {
      for (const el of document.querySelectorAll('[aria-busy="true"],[role=progressbar],[class*="spinner" i],[class*="skeleton" i],[class*="shimmer" i],[class*="loading" i],[class*="loader" i]')) {
        if (el === document.body || el === document.documentElement) continue;
        if (shown(el)) { k++; if (k >= 9) break; }
      }
    } catch (e) {}
    q.ldEl = k; q.ldAt = t_now; q.ldN = q.n;
  }
  ld = Math.min(9, ld + q.ldEl);
  // the candidate loading signs that show now: k identifies one across re-renders, d says it in words, tx: d is its text
  const ldn = [];
  if (q.ldc && q.ldc.length) {
    q.ldc = q.ldc.filter((el) => el.isConnected);
    for (const el of q.ldc) {
      if (ldn.length >= 4) break;
      try {
        if (!shown(el) || (el.checkVisibility && !el.checkVisibility({ checkOpacity: true, opacityProperty: true }))) continue;
        const img = el.tagName === 'IMG';
        let t = ((img && el.parentElement ? el.parentElement : el).innerText || '').replace(/\s+/g, ' ').trim();
        if (t.length > 40) { if (!img) continue; t = ''; }       // a block of content, not a sign
        if (!el.matches(q.IND) && !q.LDTXT.test(t)) continue;      // it was one once and now says something else
        const c = typeof el.className === 'string' ? el.className.trim() : '';
        ldn.push({ k: el.tagName + '#' + el.id + '.' + c.slice(0, 40) + '|' + t.slice(0, 30), tx: !!t,
                   d: t || (el.id ? '#' + el.id : img ? (el.getAttribute('src') || '').split('/').pop().slice(0, 40) : c ? '.' + c.split(/\s+/)[0] : el.tagName.toLowerCase()) });
      } catch (e) {}
    }
  }
  const now = performance.now(), slot = Math.floor(now / 250);
  return { now, t0: q.t0, last: q.last, n: q.n, nc: q.nc, ev: q.ev, rs: document.readyState, anim, ld, ldn, href: location.href.split('#')[0],
           rec: q.slots.map(s => slot - s).filter(d => d < 12) };
}
"""


def site_of(url):
    """Registrable domain, roughly: enough to tell the shop's own API from somebody else's."""
    h = host_of(url).lower()
    if re.fullmatch(r"[\d.]+", h):
        return h
    parts = h.split(".")
    if len(parts) <= 2:
        return h
    return ".".join(parts[-3:]) if ".".join(parts[-2:]) in TWO_PART_TLD else ".".join(parts[-2:])


def sensor_path(path):
    """Is this a path made of random-looking parts only, as bot-protection scripts use for what they post after every
    click and for the script itself (/G0mQLT/w39NGc3X3DuE4m/ADJc/TiVrdjx/LAwQ on lowes; kohls, macys, ebay, gap, cvs
    alike)? Those calls are answered late and say nothing about the page. Judged by how often the kind of character
    changes (upper, lower, digit): often in random text, seldom in words, camelCase included."""
    segs = [s for s in path.strip("/").split("/") if s]
    if not segs or len(segs) > 8 or not all(re.fullmatch(r"[A-Za-z0-9_-]+", s) for s in segs):
        return False
    # random text mixes capitals with small letters or digits; an id (digits, hex, a uuid) and a word do not
    mixed = [s for s in segs if any(c.isupper() for c in s) and any(c.islower() or c.isdigit() for c in s)]
    if any(len(s) > 4 for s in segs if s not in mixed):
        return False                           # a word or an id in it (api, items, 5013767101): an address somebody named
    if len(mixed) < 3 and not (len(mixed) == 1 and len(segs) == 1 and len(segs[0]) >= 30):
        return False
    total = sum(len(s) for s in mixed)
    kind = lambda c: 0 if c.islower() else 1 if c.isupper() else 2 if c.isdigit() else 3
    changes = sum(1 for s in mixed for a, b in zip(s, s[1:]) if kind(a) != kind(b))
    # in names (GetCart, forUser) a capital is followed by a small letter and digits are rare
    odd = sum(1 for s in mixed for a, b in zip(s, s[1:]) if (a.isupper() and not b.islower()) or (a.isdigit() != b.isdigit()))
    return total >= 20 and changes / total >= 0.35 and odd >= 4

# ----------------------------------------------------------------------------------------- daemon


def parse_secrets(path):
    """payments.env format: [section] headers, 'Key: value' lines. Returns {section: {key: value}} (keys lowercased)."""
    out, cur = {}, None
    with open(path, encoding="utf-8-sig") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^\[([^\]]+)\]$", line)
            if m:
                cur = m.group(1).strip().lower()
                out.setdefault(cur, {})
                continue
            m = re.match(r"^([^:=]+)[:=]\s*(.*)$", line)
            if cur and m:
                out[cur].setdefault(m.group(1).strip().lower(), m.group(2).strip())
    return out


def host_of(url):
    # (a login in the address, https://user:pw@host/, is not part of the host: read as one, the site's own calls
    # counted as another site's)
    m = re.match(r"^[a-z]+://(?:[^/?#@]*@)?([^/:?#]+)", url or "")
    return m.group(1) if m else (url or "")[:30]


# ----------------------------------------------------------------------------------------- read-back

# The button that commits: an order, a booking, a payment. The second kind of wording ("Buy now") is also what shops
# put on banners and product tiles, so it only counts as a button on a page that has payment fields.
SUBMIT_RX = re.compile(r"^(place|submit|complete|confirm|finish|finali[sz]e)\b.{0,14}\b(order|purchase|booking|reservation|payment|checkout)\b|"
                       r"^pay\s*[$€£]|^(complete|confirm)\s+(and|&)\s+pay", re.I)
SUBMIT_WEAK_RX = re.compile(r"^(pay|buy|book|order|reserve)\s+now\b|^purchase$|^pay$", re.I)
PAYING_RX = re.compile(r"card.?n|cvv|cvc|security.?code|expir", re.I)
# Where an order is being built (see review_lines): a cart or checkout by its address or title, or one product's page.
CART_RX = re.compile(r"\b(cart|bag|basket|checkout|trolley)\b|/(p|ip|dp|product|products|item|itm)/", re.I)
ADD_RX = re.compile(r"^(add to (cart|bag|basket|trolley)|buy now|add item)\b", re.I)

ZERO_WIDTH = re.compile("[\u200b-\u200f\u2060\ufeff]")       # bot-check pages pad their text with these

# Links in the page header or footer are hidden from the default view, except the ones a shopper acts on.
ACTION_RX = re.compile(r"check\s?out|\bcart\b|\bbag\b|basket|continue|proceed|guest|sign.?in|log.?in|\bpay\b|place|apply|add to", re.I)

# A page that asks for proof of being human, or refuses outright. pb cannot and should not get past these.
HUMAN_RX = re.compile(r"press\s*(&|and)\s*hold|verify (that )?you(.re| are) (a )?human|are you a (human|robot)|i.?m not a robot|"
                      r"unusual (\w+ )?(traffic|activity)|\bi am (a )?human\b|prove your humanity|confirm (that )?you(.re| are) (a )?human|"
                      r"access (to this page has been )?denied|checking (if the site connection is secure|your browser)|pardon our interruption|"
                      r"enable javascript and cookies to continue|complete the security check|robot or human|human verification|"
                      r"verifying (that )?you(.re| are) (a )?human|^just a moment\.\.\.|click the button below to continue shopping|"
                      r"noticing unusual", re.I | re.M)
# A browser check that may pass by itself: it says it is checking, and asks nothing of a person (see Session.collect)
SOFT_CHECK_RX = re.compile(r"checking (if the site connection is secure|your browser)|just a moment|verifying (that )?you(.re| are)|one moment, please|"
                           r"ddos protection|browser check|please wait while", re.I)
CAPTCHA_ANY = re.compile(r"recaptcha|hcaptcha|challenges\.cloudflare\.com|captcha-delivery|arkoselabs|funcaptcha|px-captcha", re.I)
HUMAN_FRAMES = re.compile(r"px-captcha|captcha-delivery\.com|challenges\.cloudflare\.com|/recaptcha/(api2|enterprise)/bframe|hcaptcha\.com/captcha|arkoselabs|funcaptcha", re.I)


def final_buttons(items):
    """The controls that would commit an order on this page."""
    paying = any(it["k"] == "input" and (str(it.get("v", "")).startswith("•") or PAYING_RX.search(it.get("t", "") + " " + it.get("name", ""))) for it in items)
    return [x for x in items if x["k"] in ("button", "link", "click")
            and (SUBMIT_RX.search(x.get("t", "")) or (paying and x["k"] == "button" and SUBMIT_WEAK_RX.search(x.get("t", ""))))]

# What an order review says, read from the page text: the lines under headings that matter (pickup, shipping, billing,
# summary...), address-like lines, and every line with an amount of money (an amount alone on its line is joined with
# the label above it). With arg.section it returns the block under that heading or label instead.
REVIEW_JS = r"""
(arg) => {
  const T = (s) => (s == null ? '' : String(s)).replace(/\s+/g, ' ').trim();
  /*PBLINES*/
  const lines = pbLines();
  const shown = (el) => { if (el.checkVisibility && !el.checkVisibility({ checkVisibilityCSS: true })) return false; const r = el.getBoundingClientRect(); return r.width > 2 && r.height > 2; };
  const heads = new Set();
  for (const el of document.querySelectorAll('h1,h2,h3,h4,h5,h6,legend,[role=heading]')) {
    if (!shown(el)) continue;
    const t = T(el.innerText || el.textContent);
    if (t && t.length <= 80) heads.add(t);
  }
  const sections = [];
  let cur = null;
  for (const l of lines) {
    if (heads.has(l)) { cur = { title: l, lines: [] }; sections.push(cur); continue; }
    if (cur && cur.lines.length < 14) cur.lines.push(l);
  }
  if (arg && arg.section != null) {
    // The blocks for a section name. Headings and labels are ranked by how they match the name: saying exactly that
    // (4) beats starting with it (3: "Pickup Information", "1. Delivery details"), which beats having it as a word
    // (2: "ALTERNATE PICKUP PERSON", "Select a delivery date"), which beats having it inside a word (1). Only the best
    // rank counts, and the caller checks every block of it. (Taking the smallest block of any rank made advance's
    // --in Pickup read the alternate pickup person block.) A step number in front ("1.", "Step 2:") is not part of it.
    const q = T(arg.section).toLowerCase();
    const clean = (t) => t.toLowerCase().replace(/^\s*(step\s*)?\d{1,2}\s*[.:)-]?\s+/, '').replace(/[\s:*]+$/, '');
    const esc = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const word = new RegExp('(^|[^a-z0-9])' + esc + '($|[^a-z0-9])');
    const rank = (t) => { const c = clean(t); return c === q ? 4 : c.startsWith(q) ? 3 : word.test(c) ? 2 : c.includes(q) ? 1 : 0; };
    const same = (t) => rank(t) === 4;
    const textOf = (el) => T(pbDropOptions(String(el.innerText || '').split('\n').map(T).filter(Boolean), el).join(' '));
    const cands = sections.filter(s => s.lines.length && s.title.toLowerCase().includes(q))
      .map(s => ({ title: s.title, text: s.lines.join(' | '), eq: same(s.title), rank: rank(s.title) }));
    if (!cands.some(c => c.eq)) {
      // no heading says exactly that: look at short labels too, with the smallest block around each
      let n = 0;
      for (const el of document.querySelectorAll('strong,b,th,dt,label,summary,span,div,p,td,li,legend')) {
        if (n >= 6) break;
        if (el.childElementCount > 2 || !(el.textContent || '').toLowerCase().includes(q)) continue;
        const t = textOf(el);
        if (!t || t.length > 80 || !t.toLowerCase().includes(q) || !shown(el)) continue;
        let p = el, block = '';
        // a label around its own field is the whole block: "Country United States"
        const own = el.querySelector('select,input,textarea') && t.length > q.length + 1;
        for (let i = 0; i < 6 && p.parentElement && !own; i++) { p = p.parentElement; block = textOf(p); if (block.length > t.length + 8) break; }
        if (own) block = t;
        if ((own || block.length > t.length + 8) && !cands.some(h => h.text === block)) {
          n++;
          const at = Math.max(0, block.indexOf(t));
          cands.push({ title: t, text: block.length > 4000 ? block.slice(at, at + 4000) : block, eq: same(t), size: block.length, rank: rank(t) });
        }
      }
    }
    const best = Math.max(0, ...cands.map(c => c.rank));
    const pool = cands.filter(c => c.rank === best);
    pool.sort((a, b) => (a.size || a.text.length) - (b.size || b.text.length));
    return { blocks: pool.slice(0, 5) };
  }
  const VOC = /pick.?up|store|ship|deliver|billing|address|contact|payment|summary|review|your order|items?\b|cart|guest|travell?er|passenger|booking|reservation|appointment|date|time/i;
  const sect = sections.filter(s => VOC.test(s.title) && s.lines.length).slice(0, 8)
    .map(s => s.title + ': ' + s.lines.slice(0, 4).map(x => x.slice(0, 120)).join(' | '));
  const AMT = /(?:[$€£¥]\s?[\d.,]*\d|\b[\d.,]*\d\s?(?:USD|EUR|GBP|CAD)\b)/;
  const ONLY = new RegExp('^[-−(]?\\s?' + AMT.source + '\\)?$');
  const KEY = /total|subtotal|tax|shipping|delivery|discount|promo|coupon|saving|fee|tip|deposit|due|balance|credit|pickup|qty|quantity/i;
  const money = [];
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (!AMT.test(l) || l.length > 120) continue;
    const s = (ONLY.test(l) && i > 0 && !AMT.test(lines[i - 1]) && lines[i - 1].length <= 80) ? lines[i - 1] + ' ' + l : l;
    if (!money.includes(s)) money.push(s);
  }
  const keyed = money.filter(m => KEY.test(m)), rest = money.filter(m => !KEY.test(m));
  const STREET = /\b\d{1,6}\s+[A-Za-z0-9.' -]{2,40}\b(st|street|ave|avenue|rd|road|blvd|boulevard|dr|drive|ln|lane|way|pl|place|ct|court|hwy|highway|pkwy|parkway|sq|square|ter|terrace|cir|circle)\b\.?/i;
  const ZIP = /\b[A-Z]{2}\s+\d{5}(-\d{4})?\b/;
  const places = [];
  for (const l of lines) {
    if (places.length >= 8) break;
    if (l.length <= 140 && (STREET.test(l) || ZIP.test(l) || /^(pick.?up|ship|deliver|bill)\w*\s+(at|to|from|information|address|details)\b/i.test(l)) && !places.includes(l)) places.push(l);
  }
  // what an open dialog is about, for a page that has nothing order-like on it
  const dialogs = [];
  // only one a person can see: hm.com keeps its cookie settings loaded off screen ("open dialog" that was not there)
  const seen = (d) => {
    if (!shown(d) || d.closest('[aria-hidden="true"]') || (d.checkVisibility && !d.checkVisibility({ opacityProperty: true }))) return false;
    const r = d.getBoundingClientRect();
    return r.right > 0 && r.bottom > 0 && r.left < (window.innerWidth || 1) && r.top < (window.innerHeight || 1);
  };
  for (const d of document.querySelectorAll('[role=dialog],[role=alertdialog],[aria-modal="true"],dialog[open]')) {
    if (dialogs.length >= 3 || !seen(d)) continue;
    const h = d.querySelector('h1,h2,h3,h4,[role=heading],legend');
    const t = T((h && T(h.innerText)) || d.getAttribute('aria-label') || String(d.innerText || '').split('\n').map(T).filter(Boolean)[0] || '');
    if (t && !dialogs.includes(t)) dialogs.push(t.slice(0, 120));
  }
  return { sections: sect, money: keyed.slice(0, 12), loose: rest.slice(0, 6), places, title: T(document.title), dialogs };
}
"""

# The visible text of a document as clean lines. Three things a plain body.innerText gets wrong on real shops:
# text inside open shadow roots (web components) is missing, bot-check pages pad lines with zero-width characters,
# and an amount drawn one element per character ("$", "5", ".", "6", "3") comes out as one line per character.
LINES_JS = r"""
  // innerText lists every option of a <select>, one per line: keep only the chosen one. Otherwise a country list
  // becomes a "section" of the review and a check for any country name passes.
  const pbDropOptions = (lines, scope) => {
    const N = (s) => String(s || '').replace(/\s+/g, ' ').trim();
    // Selects come in document order and so do their lines: each search goes on from where the last one ended, and
    // only looks back when that finds nothing (searching from the top for each of 400 selects was most of the cost).
    let from = 0;
    for (const sel of scope.querySelectorAll('select')) {
      const opts = [...sel.options].map(o => N(o.textContent)).filter(Boolean);
      if (opts.length < 2) continue;
      let at = -1;
      for (let k = from; k < lines.length - 1; k++) if (lines[k] === opts[0] && lines[k + 1] === opts[1]) { at = k; break; }
      if (at < 0) for (let k = 0; k < from && k < lines.length - 1; k++) if (lines[k] === opts[0] && lines[k + 1] === opts[1]) { at = k; break; }
      if (at < 0) continue;
      const set = new Set(opts);
      let j = at;
      while (j < lines.length && set.has(lines[j])) j++;
      // an expiry month or year pb picked from the secrets file shows as a dot, as in the view (chewy: "+ text "2029"")
      const chosen = sel.hasAttribute('data-pb-secret') && sel.selectedIndex > 0 ? '•' : sel.selectedOptions[0] ? N(sel.selectedOptions[0].textContent) : '';
      lines.splice(at, j - at, ...(chosen ? [chosen] : []));
      from = at + (chosen ? 1 : 0);
    }
    return lines;
  };
  // roots: the open shadow roots of the document in document order, when the caller has walked it already
  // body: the body's text as pb text reads it (pbReadBody), instead of its innerText
  const pbLines = (roots, body) => {
    const out = [];
    const add = (t) => { for (const l of String(t || '').split('\n')) { const s = l.replace(/[\u200b-\u200f\u2060\ufeff]/g, '').replace(/\s+/g, ' ').trim(); if (s) out.push(s); } };
    if (document.body) add(body != null ? body : document.body.innerText);
    const shadowText = (sr) => {
      for (const c of sr.children) {
        if (c.tagName === 'STYLE' || c.tagName === 'SCRIPT' || c.tagName === 'LINK') continue;
        // innerText of an element that is not displayed is its whole textContent: hidden text would read as shown
        const cs = getComputedStyle(c);
        if (cs.display === 'none' || cs.visibility === 'hidden') continue;
        add(c.innerText);
      }
    };
    const walk = (root) => {
      for (const el of root.querySelectorAll('*')) {
        if (!el.shadowRoot) continue;
        shadowText(el.shadowRoot);
        walk(el.shadowRoot);
      }
    };
    if (roots) roots.forEach(shadowText); else walk(document);
    pbDropOptions(out, document);
    const bit = /^[$€£]$|^[\d.,]{1,2}$/, merged = [];
    for (let i = 0; i < out.length; i++) {
      if (bit.test(out[i])) {
        let j = i, s = '';
        while (j < out.length && bit.test(out[j]) && s.length < 14) s += out[j++];
        // "$" "9" "97": a sale price drawn as dollars and raised cents, no dot anywhere
        if (j - i >= 3 && /^[$€£]$/.test(out[i]) && /^\d\d$/.test(out[j - 1]) && !/[.,]/.test(s)) s = s.slice(0, -2) + '.' + s.slice(-2);
        if (j - i >= 3 && /^[$€£]?\d[\d,]*(\.\d\d)?$/.test(s)) { merged.push(s); i = j - 1; continue; }
      }
      // "$9" then "97" (and maybe the struck-through old price on the same line): the same, drawn as two parts
      if (/^[$€£]\d{1,5}$/.test(out[i]) && i + 1 < out.length) {
        const m = /^(\d\d)(?:\s+([$€£].*))?$/.exec(out[i + 1]);
        if (m) { merged.push(out[i] + '.' + m[1]); if (m[2]) merged.push(m[2]); i++; continue; }
      }
      merged.push(out[i]);
    }
    return merged;
  };
"""
COLLECT_JS = COLLECT_JS.replace("/*PBLINES*/", LINES_JS)
REVIEW_JS = REVIEW_JS.replace("/*PBLINES*/", LINES_JS)
# pb text: the body's innerText with what innerText loses put back where a visitor sees it. A separator between
# pieces shown apart that innerText runs together (list items side by side: "Lana WachowskiLilly Wachowski"), the
# date of a <time datetime> / <relative-time datetime> whose text has no year ("13 Nov" -> "13 Nov (2026-11-13)"),
# and the text of open shadow roots in place (innerText skips them; pbLines would add them at the end). Each addition
# is found in the text by the words just before it, in document order; one that is not found is left out.
# Returns [text, the shadow roots placed].
READ_JS = r"""
  const pbReadBody = () => {
    const body = document.body;
    if (!body) return ['', new Set()];
    let raw = body.innerText;
    const pts = [], placed = new Set(), disp = new Map();
    // A panel parked beyond the window's left or right edge (a closed drawer: clinicaltrials.gov's glossary of 121
    // terms, aria-hidden, fixed past the right edge) is rendered, so innerText has it, but nobody sees it: its text is
    // taken out
    {
      const PW = Math.max(window.innerWidth || 0, document.documentElement ? document.documentElement.scrollWidth : 0);
      const cands = [...body.querySelectorAll('[aria-hidden="true"],[class*="drawer" i],[class*="offcanvas" i],[class*="panel" i],[class*="glossary" i],[class*="sidebar" i]')]
        .slice(0, 300).filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && (r.left >= PW || r.right <= 0); });
      for (const e of cands.filter(e => !cands.some(o => o !== e && o.contains(e)))) {
        const t = e.innerText;
        if (t && t.trim().length >= 40) { const i = raw.indexOf(t); if (i >= 0) raw = raw.slice(0, i) + raw.slice(i + t.length); }
      }
    }
    const D = (el) => { let d = disp.get(el); if (d === undefined) { d = getComputedStyle(el).display; disp.set(el, d); } return d; };
    const N = (s) => s.replace(/\s+/g, ' ').trim();
    const textNode = (el, last) => {
      const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      let found = null;
      for (let n = w.nextNode(), k = 0; n && k < 400; n = w.nextNode(), k++) if (n.nodeValue.trim()) { found = n; if (!last) break; }
      return found;
    };
    const rects = (n) => { const r = document.createRange(); r.selectNodeContents(n); return r.getClientRects(); };
    const SKIP = /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|BR|WBR|IMG|INPUT|SELECT|TEXTAREA|IFRAME|OPTION)$/;
    const dateOf = (el, shown) => {
      const dt = el.getAttribute('datetime') || '', m = /^(\d{4})-(\d\d)-(\d\d)(?:[T ](\d\d:\d\d))?/.exec(dt);
      if (!m || !shown || shown.includes(m[1])) return '';
      return ' (' + m[1] + '-' + m[2] + '-' + m[3] + (m[4] && /\d:\d\d/.test(shown) ? ' ' + m[4] + (/Z$/.test(dt) ? ' UTC' : '') : '') + ')';
    };
    const els = body.getElementsByTagName('*');
    for (let i = 0, n = 0; i < els.length; i++) {
      const b = els[i];
      if (b.shadowRoot && D(b) !== 'none' && (!b.checkVisibility || b.checkVisibility({ checkVisibilityCSS: true }))) {
        // an open shadow root: its text goes in after the last text shown before its host
        const parts = [];
        for (const c of b.shadowRoot.childNodes) {
          if (c.nodeType === 3) { if (c.nodeValue.trim()) parts.push(c.nodeValue); continue; }
          if (c.nodeType !== 1 || /^(STYLE|SCRIPT|LINK)$/.test(c.tagName)) continue;
          const cs = getComputedStyle(c);
          if (cs.display === 'none' || cs.visibility === 'hidden') continue;
          parts.push(c.innerText);
        }
        const inl = D(b).startsWith('inline');
        let t = inl ? N(parts.join(' ')) : parts.join('\n').trim();
        if (t && /^(TIME|RELATIVE-TIME)$/.test(b.tagName)) t += dateOf(b, t);
        if (t) {
          const w = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
          w.currentNode = b;
          let prev = '';
          for (let nd = w.previousNode(), k = 0; nd && k < 40; nd = w.previousNode(), k++) {
            const pe = nd.parentElement;
            if (!pe || !nd.nodeValue.trim() || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|OPTION)$/.test(pe.tagName)) continue;
            if (pe.checkVisibility && !pe.checkVisibility({ checkVisibilityCSS: true })) continue;
            prev = N(nd.nodeValue).slice(-30);
            break;
          }
          // The words before it may come up more than once (a table of contents repeats every heading: on MDN the code
          // under "Syntax" went in after the contents entry "Syntax"). Count which time this one is, in the document.
          let occ = null;
          if (prev && raw.indexOf(prev) !== raw.lastIndexOf(prev)) {
            occ = -1;
            const w2 = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
            for (let nd = w2.nextNode(), k = 0; nd && k < 30000; nd = w2.nextNode(), k++) {
              if (b.compareDocumentPosition(nd) & Node.DOCUMENT_POSITION_FOLLOWING) break;
              const pe = nd.parentElement;
              if (!pe || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|OPTION)$/.test(pe.tagName)) continue;
              const v = N(nd.nodeValue);
              if (!v || !v.includes(prev)) continue;
              if (pe.checkVisibility && !pe.checkVisibility({ checkVisibilityCSS: true })) continue;
              occ++;
            }
          }
          pts.push({ node: b, end: false, needle: prev, at: prev.length, add: inl ? ' ' + t + ' ' : '\n' + t + '\n', root: b.shadowRoot, occ });
        }
      } else if (/^(TIME|RELATIVE-TIME)$/.test(b.tagName) && b.hasAttribute('datetime')) {
        const v = N(b.innerText || ''), add = dateOf(b, v);
        if (add) pts.push({ node: b, end: true, needle: v, at: v.length, add });
      }
      {
        // text, an element with no text of its own (an icon, a help button), text: innerText runs the two texts
        // together when they sit apart on the screen (Google Flights: "Ranked based on price and convenience", an
        // info icon, "Prices include required taxes" read as "conveniencePrices")
        const p = b.previousSibling, q = b.nextSibling;
        if (p && q && p.nodeType === 3 && q.nodeType === 3 && /\S$/.test(p.nodeValue) && /^\S/.test(q.nodeValue) && b instanceof HTMLElement
            && !SKIP.test(b.tagName) && D(b).startsWith('inline') && !(b.innerText || '').trim() && n++ < 5000) {
          const rp = rects(p), rq = rects(q);
          if (rp.length && rq.length) {
            const x = rp[rp.length - 1], y = rq[0];
            if (y.top < x.bottom - 1 && y.bottom > x.top + 1 ? y.left - x.right > 4 : y.top >= x.bottom - 1) {
              const tail = N(p.nodeValue).slice(-24);
              pts.push({ node: b, end: false, needle: tail + N(q.nodeValue).slice(0, 24), at: tail.length, add: ' ' });
            }
          }
        }
      }
      let a = b.previousSibling, sep = '';
      if (!a || a.nodeType !== 1 || !(a instanceof HTMLElement) || !(b instanceof HTMLElement) || SKIP.test(a.tagName) || SKIP.test(b.tagName)) continue;
      if (++n > 5000) continue;
      // two elements side by side with nothing between them in the markup
      if (!D(a).startsWith('inline') || !D(b).startsWith('inline')) continue;
      // or with only empty inline elements between them: a spacer, or a separator the page draws with CSS (Google
      // Flights: "Tap Air Portugal", an empty span whose ::before is "·", "JetBlue", read as "Tap Air PortugalJetBlue")
      for (let k = 0; k < 3 && a && a.nodeType === 1 && !SKIP.test(a.tagName) && D(a).startsWith('inline') && !(a.textContent || '').trim(); k++) {
        if (!sep) for (const ps of ['::before', '::after']) {
          const c = getComputedStyle(a, ps).content;
          // (punctuation only: an icon font's glyph is a private-use character, not a separator)
          if (c && /^".+"$/.test(c) && c.length <= 6) { sep = c.slice(1, -1).trim(); if (!/^[\p{P}|]{1,3}$/u.test(sep)) sep = ''; if (sep) break; }
        }
        a = a.previousSibling;
      }
      if (!a || a.nodeType !== 1 || !(a instanceof HTMLElement) || SKIP.test(a.tagName) || !D(a).startsWith('inline')) continue;
      const ta = a.innerText, tb = b.innerText;
      if (!ta || !tb || /\s$/.test(ta) || /^\s/.test(tb)) continue;
      const na = textNode(a, true), nb = textNode(b, false);
      if (!na || !nb) continue;
      const ra = rects(na), rb = rects(nb);
      if (!ra.length || !rb.length) continue;
      const x = ra[ra.length - 1], y = rb[0];
      const same = y.top < x.bottom - 1 && y.bottom > x.top + 1, gap = same ? y.left - x.right : 1e9;
      if (same && gap < 2 && /^\d\d$/.test(tb) && /^[\d,]{1,7}$/.test(ta) && y.height < x.height * 0.8) {
        // "$" "19" "99": dollars, then cents drawn smaller, with no point between them (amazon.com search results)
        const before = a.previousSibling ? (a.previousSibling.textContent || '').trim() : '';
        if (/\p{Sc}$/u.test(before)) pts.push({ node: b, end: false, needle: ta.slice(-24) + tb.slice(0, 24), at: ta.slice(-24).length, add: '.' });
        continue;
      }
      if (same && gap < 2 && !sep) continue;  // drawn touching: parts of one word or one amount ("$" "19" ".99")
      const tail = ta.slice(-24);
      pts.push({ node: b, end: false, needle: tail + tb.slice(0, 24), at: tail.length,
                 add: sep ? ' ' + sep + ' ' : (a.tagName === 'LI' && b.tagName === 'LI') || gap > 10 ? ' | ' : ' ' });
    }
    // a point at the start of p.node (end false) or at its end (end true): which comes first in the document
    pts.sort((p, q) => {
      if (p.node === q.node) return p.end === q.end ? 0 : p.end ? 1 : -1;
      const c = p.node.compareDocumentPosition(q.node);
      if (c & Node.DOCUMENT_POSITION_CONTAINED_BY) return p.end ? 1 : -1;
      if (c & Node.DOCUMENT_POSITION_CONTAINS) return q.end ? -1 : 1;
      return c & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
    });
    let cur = 0, s = '', last = 0;
    for (const p of pts) {
      let i = -1;
      if (p.occ != null && p.occ >= 0) {
        let j = -1;
        for (let k = 0; k <= p.occ; k++) { j = raw.indexOf(p.needle, j + 1); if (j < 0) break; }
        if (j >= cur) i = j;
      }
      if (i < 0) i = raw.indexOf(p.needle, cur);
      if (i < 0) continue;
      cur = i + p.at;
      s += raw.slice(last, cur) + p.add;
      last = cur;
      if (p.root) placed.add(p.root);
    }
    s += raw.slice(last);
    // table cells: innerText puts a tab between them
    return [s.replace(/(\S)[ ]*\t+(?=[ ]*\S)/g, '$1 | '), placed];
  };
"""
# A frame that loaded a script or JSON file shows it as text: that is source, not something a person reads. The page
# itself may be such a file (a JSON answer, a text or XML file opened by its address): then it is what pb text prints.
TEXT_JS = "(arg) => {" + LINES_JS + READ_JS + r"""
  const ct = document.contentType || 'text/html';
  if (!/html/.test(ct)) {
    const b = document.body, pre = document.querySelector('body > pre');
    let t = pre ? pre.textContent : b ? b.innerText : '';
    // Chrome's XML viewer: the document tree under one line of its own
    if (/xml/.test(ct)) return t.replace(/^This XML file does not appear to have any style information[^\n]*\n*/, '');
    if (!arg || !arg.main) return '';
    if (/json/.test(ct) || /^\s*[\[{]/.test(t)) {
      // a JSON answer on one long line: laid out, so that pb text REGEX finds the lines of it
      try { const v = JSON.parse(t); if (t.split('\n').some(l => l.length > 200)) t = JSON.stringify(v, null, 1); } catch (e) {}
    }
    return t;
  }
  const [body, placed] = pbReadBody();
  const rest = [];
  const walk = (root) => { for (const el of root.querySelectorAll('*')) if (el.shadowRoot) { if (!placed.has(el.shadowRoot)) rest.push(el.shadowRoot); walk(el.shadowRoot); } };
  walk(document);
  return pbLines(rest, body).join('\n');
}"""
# What the page itself is: [content type, characters of its text] (pb open names a JSON, text, XML or PDF document)
DOCKIND_JS = "() => { const e = document.querySelector('body > pre') || document.body; return [document.contentType || '', e ? e.textContent.length : 0]; }"

# pb text --of TARGET: one element's whole text and the attributes that say what it is or holds
OF_JS = r"""
(e) => {
  const tag = e.tagName, out = { tag: tag.toLowerCase(), text: '', attrs: [] };
  const secret = e.hasAttribute('data-pb-secret') || e.type === 'password' || /card|cc-|cvc|cvv|csc|security/i.test(e.autocomplete || '');
  if (tag === 'SELECT') out.text = [...e.selectedOptions].map(o => o.textContent.replace(/\s+/g, ' ').trim()).join(', ');
  else if (!/^(INPUT|TEXTAREA)$/.test(tag)) {
    // as pb text reads it: pieces shown apart are kept apart (imdb's principal credits: "Lana WachowskiLilly Wachowski"
    // from innerText); a line per block
    const D = new Map(), disp = (el) => { let d = D.get(el); if (d === undefined) { d = getComputedStyle(el).display; D.set(el, d); } return d; };
    const blockOf = (el) => { for (let p = el; p && p !== e.parentElement; p = p.parentElement) { const d = disp(p); if (!d.startsWith('inline') && d !== 'contents') return p; } return e; };
    let s = '', pb = null, pli = null, pr = null;
    const w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(), k = 0; n && k < 20000; n = w.nextNode(), k++) {
      const pe = n.parentElement;
      if (!pe || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(pe.tagName) || (pe.checkVisibility && !pe.checkVisibility({ checkVisibilityCSS: true }))) continue;
      const v = n.nodeValue.replace(/\s+/g, ' ');
      if (!v.trim()) { s += ' '; continue; }
      const rg = document.createRange(); rg.selectNodeContents(n); const rs = rg.getClientRects();
      if (!rs.length) continue;
      const b = blockOf(pe), li = pe.closest('li');
      if (pb && b !== pb) s = s.replace(/\s+$/, '') + '\n';
      else if (pb && !/\s$/.test(s) && !/^\s/.test(v) && ((li && pli && li !== pli) || (pr && Math.abs(rs[0].top - pr.top) < 4 && rs[0].left - pr.right > 10))) s += ' | ';
      s += v; pb = b; pli = li; pr = rs[rs.length - 1];
    }
    out.text = s.replace(/[^\S\n]+/g, ' ').replace(/ ?\n\s*/g, '\n').trim() || (e.innerText || e.textContent || '').replace(/[^\S\n]+/g, ' ').replace(/ ?\n[\s]*/g, '\n').trim();
  }
  // "$" "19" "99": dollars, then cents drawn smaller, with no point between them (amazon.com search results)
  let seen = 0;
  for (const b of e.querySelectorAll('*')) {
    if (++seen > 4000) break;
    if (b.children.length) continue;
    const tb = (b.innerText || '').trim(), a = b.previousElementSibling;
    if (!/^\d\d$/.test(tb) || !a) continue;
    const ta = (a.innerText || '').trim(), pre = a.previousSibling ? (a.previousSibling.textContent || '').trim() : '';
    if (!/^[\d,]{1,7}$/.test(ta) || !/\p{Sc}$/u.test(pre)) continue;
    if (parseFloat(getComputedStyle(b).fontSize) >= 0.8 * parseFloat(getComputedStyle(a).fontSize)) continue;
    const cur = pre.slice(-1);
    out.text = out.text.replace(cur + ta + tb, cur + ta + '.' + tb);
  }
  const add = (k, v) => { if (v != null && String(v).trim() !== '') out.attrs.push([k, String(v).trim().slice(0, 500)]); };
  const a = e.closest('a[href],area[href]');
  if (a && !/^javascript:/i.test(a.getAttribute('href'))) add('href', a.href);
  // the text inside a link whose title holds the whole name (books.toscrape: "A Light in the ...")
  if (a && a !== e && !e.hasAttribute('title')) add('title', a.getAttribute('title'));
  if (/^(INPUT|TEXTAREA|SELECT|BUTTON|OPTION|OUTPUT|DATA|METER|PROGRESS|LI)$/.test(tag) && 'value' in e && !(tag === 'LI' && !e.hasAttribute('value')))
    add('value', secret && e.value ? '(' + e.value.length + ' characters, not shown)' : e.value);
  if (/^(checkbox|radio)$/.test(e.type)) add('checked', e.checked ? 'yes' : 'no');
  for (const k of ['datetime', 'title', 'aria-label', 'alt', 'placeholder', 'aria-valuenow', 'aria-valuetext', 'aria-checked', 'aria-selected', 'aria-expanded'])
    add(k, e.getAttribute(k));
  // what says more inside the element or right next to it: a link's title (books.toscrape's h3 holds the link with the
  // whole name), the date of a <time> / <relative-time> (github: "Latest" sits beside the release's relative date)
  const has = (k) => out.attrs.some(x => x[0] === k);
  if (!has('title')) { const t = e.querySelector('a[title],[title]'); if (t) add('title', t.getAttribute('title')); }
  if (!has('datetime')) {
    let d = e.querySelector('time[datetime],relative-time[datetime]');
    for (let p = e, i = 0; !d && p && i < 3; p = p.parentElement, i++) {
      for (const s of [p.previousElementSibling, p.nextElementSibling]) if (!d && s) d = s.matches('time[datetime],relative-time[datetime]') ? s : s.querySelector && s.querySelector('time[datetime],relative-time[datetime]');
    }
    if (d) add('datetime', d.getAttribute('datetime'));
  }
  if (e.currentSrc || e.src) add('src', e.currentSrc || e.src);
  return out;
}
"""

# ---- general browsing: what the commands beyond shop checkouts ask of a page. Each runs only when its command does,
# never in a scan or a wait.

# pb scroll: move the page's scroller (or, when the document does not scroll, as in app shells, the biggest box that
# does) and say where it is. how: down | up (n screens) | top | bottom | measure (no move).
SCROLL_JS = r"""
(arg) => {
  const de = document.scrollingElement || document.documentElement, vh = window.innerHeight;
  let sc = de, box = false;
  if (de.scrollHeight - de.clientHeight < 40) {
    let best = null, area = 0;
    for (const el of document.querySelectorAll('body *')) {
      if (el.scrollHeight - el.clientHeight < 40) continue;
      const oy = getComputedStyle(el).overflowY;
      if (oy !== 'auto' && oy !== 'scroll' && oy !== 'overlay') continue;
      const r = el.getBoundingClientRect(), a = Math.max(0, Math.min(r.bottom, vh) - Math.max(r.top, 0)) * r.width;
      if (a > area) { area = a; best = el; }
    }
    if (best && area > 0.25 * vh * window.innerWidth) { sc = best; box = true; }
  }
  const view = box ? sc.clientHeight : vh, y0 = sc.scrollTop;
  // 'instant': a page that asks for smooth scrolling would still be on its way when the answer is written
  const to = (y) => sc.scrollTo({ top: y, behavior: 'instant' });
  if (arg.how === 'down') to(y0 + arg.n * view * 0.85);
  else if (arg.how === 'up') to(y0 - arg.n * view * 0.85);
  else if (arg.how === 'top') to(0);
  else if (arg.how === 'bottom') to(sc.scrollHeight);
  return { y: Math.round(sc.scrollTop), y0: Math.round(y0), h: sc.scrollHeight, view, box, els: document.getElementsByTagName('*').length };
}
"""

# What a person sees in the window now: headings (marked #) and text, in page order, page header and navigation left out.
INVIEW_JS = r"""
() => {
  const vh = window.innerHeight, out = [], seen = new Set();
  const w = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
  let k = 0;
  for (let nd = w.nextNode(); nd && out.length < 8 && k < 8000; nd = w.nextNode(), k++) {
    const s = nd.nodeValue.replace(/\s+/g, ' ').trim();
    if (s.length < 2) continue;
    const pe = nd.parentElement;
    if (!pe || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|OPTION)$/.test(pe.tagName) || pe.closest('header,nav,footer,[role=navigation],[role=banner]')) continue;
    const r = pe.getBoundingClientRect();
    if (r.bottom <= 0 || r.top >= vh || r.width < 2 || r.height < 2) continue;
    if (pe.checkVisibility && !pe.checkVisibility({ checkVisibilityCSS: true })) continue;
    const t = (pe.closest('h1,h2,h3,h4,h5,h6,[role=heading]') ? '# ' : '') + (s.length > 90 ? s.slice(0, 89) + '…' : s);
    if (!seen.has(t)) { seen.add(t); out.push(t); }
  }
  return out;
}
"""

# pb items: the repeated cards or rows of the page (search results, listings) as records. Groups are sibling elements
# of one tag (and one class, when most of them share it), three or more with text; each is scored by the text and
# the area its members show, and by how many of them have text and a link, less in page headers, menus and footers.
# arg.pick: {ref | css | text | label} of an element the wanted group contains, or null for the best group.
# Returns {score, label, n, items: [[text pieces joined by " | ", main link]], others: [[label, n, score]]}.
ITEMS_JS = r"""
(arg) => {
  const T = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const body = document.body;
  if (!body) return null;
  const SKIP = /^(SCRIPT|STYLE|LINK|META|BR|HR|WBR|OPTION|SOURCE|TEMPLATE|NOSCRIPT|IMG|INPUT|IFRAME|svg|path|g|use|defs|symbol)$/;
  // characters of text and number of links under each element, counted once from the bottom up (shadow roots too)
  const tl = new Map(), nl = new Map(), roots = [body];
  const up = (n, map, k) => { for (let p = n.parentNode; p; p = p.parentNode) { if (p.nodeType === 11) p = p.host; if (!p || p === document.documentElement) break; map.set(p, (map.get(p) || 0) + k); } };
  for (let i = 0; i < roots.length; i++) {
    const w = document.createTreeWalker(roots[i], NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    for (let n = w.nextNode(); n; n = w.nextNode()) {
      if (n.nodeType === 3) {
        const pe = n.parentElement;
        if (pe && /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(pe.tagName)) continue;
        const k = n.nodeValue.trim().length;
        if (k) up(n, tl, k);
      } else {
        if (n.shadowRoot) roots.push(n.shadowRoot);
        if (n.tagName === 'A' && n.hasAttribute('href') && !/^(javascript:|#$)/i.test(n.getAttribute('href'))) { up(n, nl, 1); nl.set(n, (nl.get(n) || 0) + 1); }
      }
    }
  }
  // (beyond the page's left or right edge is not shown either: clinicaltrials.gov keeps its glossary, 121 entries, in a
  // fixed panel parked past the right edge)
  const PW = Math.max(window.innerWidth || 0, document.documentElement ? document.documentElement.scrollWidth : 0) || 1e6;
  const vis = (el) => { if (el.checkVisibility && !el.checkVisibility({ checkVisibilityCSS: true })) return false; const r = el.getBoundingClientRect();
                        return r.width >= 2 && r.height >= 2 && r.right > 0 && r.left < PW; };
  const CHROME = 'header,nav,footer,[role=navigation],[role=banner],[role=contentinfo],[role=menu],[role=menubar],[role=tablist]';
  // What the visitor searched for: the words of the address's search parameters (also in a #/q= route) and of a
  // search box that holds text. A group whose members name those words is the one that answers the search.
  const QK = /^(q|query|search_query|search|keywords?|k|ss|text|term|searchterm|st|kw|wd|p|w|field-keywords|_nkw)$/i;
  const STOPW = /^(the|and|for|with|near|from|this|that|you|your|are|was|www|com|org|http|https|html)$/;
  const qwords = new Set();
  const addQ = (s) => { for (const w of String(s || '').toLowerCase().split(/[^\p{L}\p{N}]+/u)) if (w.length >= 3 && !STOPW.test(w) && !/^\d+$/.test(w)) qwords.add(w); };
  try {
    for (const [k, v] of new URLSearchParams(location.search)) if (QK.test(k)) addQ(v);
    const hs = location.hash.replace(/^#\/?/, '').replace(/^[^?=]*\?/, '');
    if (hs.includes('=')) for (const [k, v] of new URLSearchParams(hs)) if (QK.test(k)) addQ(v);
  } catch (e) {}
  for (const f of document.querySelectorAll('input[type=search],input[name=q],input[name=query],input[name=search_query],input[name=keywords],input[name=ss],input[role=searchbox],[role=search] input'))
    if (f.value && f.type !== 'hidden' && vis(f)) addQ(f.value);
  const qtext = new Map();
  const hasQ = (m) => { let s = qtext.get(m); if (s === undefined) { s = (m.textContent || '').slice(0, 3000).toLowerCase(); qtext.set(m, s); } for (const w of qwords) if (s.includes(w)) return true; return false; };
  // A list the page marks as results (ul.results-list, ol.react-results--main, role=feed): the class, id, label or
  // tag of the parent or the three elements above it, or of the members, say so (camelCase cut into words first)
  const SEM = /(^|[^a-z])(results?|serp|hits|listings?|feed|search ?results?)([^a-z]|$)/i;
  const semWords = (e) => [e.id, typeof e.className === 'string' ? e.className : '', e.getAttribute('aria-label') || '', e.getAttribute('data-testid') || '', e.tagName]
    .join(' ').replace(/([a-z])([A-Z])/g, '$1 $2');
  const semOf = (P, m) => {
    for (let p = P.nodeType === 11 ? P.host : P, i = 0; p && p !== body && i < 4; p = p.parentElement, i++)
      if (p.getAttribute('role') === 'feed' || SEM.test(semWords(p))) return true;
    return !!m && SEM.test(semWords(m));
  };
  // groups of siblings: per parent, per tag, the whole tag and each class most of them carry. Two siblings make a group
  // only when the page marks them as results or both name what was searched for (a search that found two places).
  const groups = [], seen = new Set();
  const parents = [];
  for (const r of roots) { if (r !== body) parents.push(r); for (const el of r.querySelectorAll('*')) if (el.children.length >= 2) parents.push(el); }
  if (body.children.length >= 2) parents.push(body);
  for (const P of parents) {
    const byTag = new Map();
    for (const c of P.children) { if (SKIP.test(c.tagName) || !(tl.get(c) > 0)) continue; let l = byTag.get(c.tagName); if (!l) byTag.set(c.tagName, l = []); l.push(c); }
    for (const [tag, kids] of byTag) {
      if (kids.length < 2) continue;
      if (kids.length === 2) {
        if ((tl.get(kids[0]) || 0) < 20 || (tl.get(kids[1]) || 0) < 20) continue;
        if (!semOf(P, kids[0]) && !(qwords.size && hasQ(kids[0]) && hasQ(kids[1]))) continue;
        groups.push({ P, label: tag.toLowerCase() + ([...kids[0].classList].find(c => kids[1].classList.contains(c)) ? '.' + [...kids[0].classList].find(c => kids[1].classList.contains(c)) : ''), ms: kids, whole: true, pair: true });
        continue;
      }
      const freq = new Map();
      for (const k of kids) for (const c of k.classList) freq.set(c, (freq.get(c) || 0) + 1);
      const cands = [[tag.toLowerCase(), kids]];
      for (const [c, n] of freq) if (n >= 3 && n < kids.length) cands.push([tag.toLowerCase() + '.' + c, kids.filter(k => k.classList.contains(c))]);
      if (kids.length >= 3) { const all = [...freq].filter(([c, n]) => n === kids.length).map(([c]) => c).sort((x, y) => x.length - y.length); if (all.length) cands[0][0] += '.' + all[0]; }
      cands.forEach(([label, ms], ci) => {
        let dup = false;
        for (const g of groups) if (g.P === P && g.ms.length === ms.length && g.ms[0] === ms[0] && g.ms[ms.length - 1] === ms[ms.length - 1]) { dup = true; break; }
        if (!dup) groups.push({ P, label, ms, whole: ci === 0 });
      });
    }
  }
  // One list in pieces. (1) The same kind of list twice, close together (Google Flights: "Top flights" and "Other
  // flights", each a ul.Rk10dc under its own heading): one group in page order. (2) A grid whose cells hold grids of
  // the same cells (bbc.com: the lead story, then a column of three and a row of four): one group of the innermost cells.
  {
    const elP = (g) => (g.P.nodeType === 11 ? null : g.P);
    const near = (a, b) => { for (let p = a.parentElement, i = 0; p && i < 2; p = p.parentElement, i++) if (p.contains(b)) return p; return null; };
    const byKey = new Map();
    for (const g of groups) {
      const P = elP(g);
      if (!P || P === body) continue;
      const k = g.label + '|' + P.tagName + '.' + (typeof P.className === 'string' ? P.className : '');
      let l = byKey.get(k); if (!l) byKey.set(k, l = []); l.push(g);
    }
    const add = [];
    // the parts of two cards of one list (clinicaltrials.gov: each study card holds two blocks of divs) are not one
    // list: two lists that sit in different members of a group of named cards stay apart
    const named = new Map();
    for (const g of groups) if (g.label.includes('.') || g.label.includes('-')) for (const m of g.ms) { let l = named.get(m); if (!l) named.set(m, l = []); l.push(g); }
    const cardsOf = (P) => { const out = new Map(); for (let p = P; p && p !== body; p = p.parentElement) for (const g of named.get(p) || []) if (!out.has(g)) out.set(g, p); return out; };
    const apart = (a, b) => { const ca = cardsOf(a), cb = cardsOf(b); for (const [g, m] of ca) if (cb.has(g) && cb.get(g) !== m) return true; return false; };
    for (const l of byKey.values()) {
      if (l.length < 2) continue;
      l.sort((x, y) => (x.P.compareDocumentPosition(y.P) & Node.DOCUMENT_POSITION_FOLLOWING) ? -1 : 1);
      let run = [l[0]];
      // (a few lists only: the cells of a table's rows, or the parts of every search result, are not one list)
      const flush = () => {
        if (run.length >= 2 && run.length <= 4 && !/^t[dh]\b/.test(run[0].label) && !run.some((g, i) => i && g.P.contains(run[i - 1].P))
            && !run.some((g, i) => i && apart(run[i - 1].P, g.P))) {
          let A = run[0].P;
          for (const g of run.slice(1)) { let p = A; while (p && !p.contains(g.P)) p = p.parentElement; A = p || body; }
          add.push({ P: A, label: run[0].label, ms: run.flatMap(g => g.ms), whole: false, merged: true });
        }
      };
      for (const g of l.slice(1)) { if (near(run[run.length - 1].P, g.P) && near(g.P, run[run.length - 1].P)) run.push(g); else { flush(); run = [g]; } }
      flush();
    }
    groups.push(...add);
  }
  // (2), once the groups are scored: from the groups that count, and only for cells named by a class (tr in tr is a
  // table in a table, Hacker News)
  const flatten = () => {
    const byLabel = new Map(), add = [];
    for (const g of groups) { if (!(g.score > 0) || !g.label.includes('.')) continue; let l = byLabel.get(g.label); if (!l) byLabel.set(g.label, l = []); l.push(g); }
    const leaves = (m, label, depth) => {
      const inner = (byLabel.get(label) || []).filter(h => m.contains(h.P.nodeType === 11 ? h.P.host : h.P) && h.ms.length >= 2);
      // the outermost grid inside this cell
      const top = inner.filter(h => !inner.some(o => o !== h && o.ms.some(x => x.contains(h.P.nodeType === 11 ? h.P.host : h.P))));
      if (!top.length || depth > 3) return [m];
      const h = top.reduce((a, b) => (b.ms.length > a.ms.length ? b : a));
      return h.ms.flatMap(x => leaves(x, label, depth + 1));
    };
    for (const l of byLabel.values()) {
      if (l.length < 2) continue;
      for (const g of l) {
        if (!g.whole || g.ms.length > 12) continue;
        const ms = g.ms.flatMap(m => leaves(m, g.label, 0));
        if (ms.length > g.ms.length) add.push({ P: g.P, label: g.label, ms, whole: false, flat: true });
      }
    }
    return add;
  };
  const VA = 300 * 400;
  // rows that belong to the member before them (Hacker News: the title row, then the points row and a spacer row):
  // the same number of siblings of the same tag between every two members
  const extOf = (g) => {
    if (g.whole || g.merged || g.flat || g.ms.length < 2) return 0;
    const kids = [...g.P.children], idx = g.ms.map(m => kids.indexOf(m)), tag = g.ms[0].tagName;
    const gaps = idx.slice(1).map((v, i) => v - idx[i] - 1);
    if (!(gaps[0] >= 1 && gaps[0] <= 3 && gaps.every(x => x === gaps[0]))) return 0;
    if (!idx.slice(0, -1).every(v => kids.slice(v + 1, v + 1 + gaps[0]).every(k => k.tagName === tag))) return 0;
    // rows shaped like the members, cell for cell (tr.odd, tr.even: a striped table, sec.gov's filings), are records
    // of their own; the rows of one record differ (HN: title row, then the points row and a spacer)
    const shape = (e) => [...e.children].map(c => c.tagName + (c.colSpan > 1 ? c.colSpan : '')).join(',');
    const s0 = shape(g.ms[0]);
    return idx.slice(0, -1).every(v => kids.slice(v + 1, v + 1 + gaps[0]).every(k => shape(k) === s0)) ? 0 : gaps[0];
  };
  const withExt = (g, m) => { const els = [m]; for (let s = m.nextElementSibling, k = 0; k < g.ext && s; k++, s = s.nextElementSibling) els.push(s); return els; };
  // Where the content is: inside <main> when the page has one that holds a good share of its text; not in an aside
  const MAIN = document.querySelector('main,[role=main]');
  const mainOk = !!MAIN && vis(MAIN) && (tl.get(MAIN) || 0) >= 0.25 * (tl.get(body) || 1);
  const VH = window.innerHeight || 800;
  const score = (g) => {
    let s = 0, text = 0, link = 0, n = 0, q = 0, y = null;
    g.ext = extOf(g);
    for (const m of g.ms) {
      if (!vis(m)) continue;
      n++;
      const els = withExt(g, m);
      const t = Math.min(els.reduce((x, e) => x + (tl.get(e) || 0), 0), 400), r = m.getBoundingClientRect();
      if (y === null) y = r.top + window.scrollY;
      if (t > 0) text++;
      if (els.some(e => nl.get(e)) || m.closest('a[href]')) link++;
      if (qwords.size && hasQ(m)) q++;
      s += t + Math.min(r.width * r.height, VA) / 400;
    }
    g.n = n;
    if (n < 3 && !(g.pair && n === 2)) return 0;
    const P = g.P.nodeType === 11 ? g.P.host : g.P;
    // the page's own weights: chrome (header, nav, footer, menus) and asides count little, content outside a <main>
    // that holds the content less, lists far down the page (a sport grid under the news) less than the ones on top;
    // a list the page marks as results, and one whose members name what was searched for, more
    const where = P.closest(CHROME) ? 0.3 : P.closest('aside,[role=complementary]') ? 0.6 : (mainOk && !MAIN.contains(P)) ? 0.5 : 1;
    const pos = 1 / (1 + Math.max(0, (y || 0) - VH) / (3 * VH));
    const sem = semOf(g.P, g.ms[0]) ? 1.5 : 1;
    const qf = qwords.size ? 1 + q / n : 1;
    g.why = `w${where} pos${pos.toFixed(2)} sem${sem} q${qf.toFixed(2)} y${Math.round(y || 0)}`;
    return s * (text / n) ** 2 * (0.5 + 0.5 * link / n) * where * pos * sem * qf;
  };
  for (const g of groups) g.score = score(g);
  // a group whose members, with the rows that follow each, cover all the tag's rows stands for them
  for (const g of groups) if (g.ext && g.score > 0) for (const w of groups) if (w.whole && w.P === g.P && w.ms[0].tagName === g.ms[0].tagName) w.score = 0;
  for (const g of flatten()) { g.score = score(g); groups.push(g); }
  // A group whose members hold a list of their own that counts (the page's columns or sections, Google Flights' search
  // panel, results and footer side by side) is layout: the list inside it is what repeats
  {
    const scored = groups.filter(g => g.score > 0), base = new Map(scored.map(g => [g, g.score])), memberOf = new Map(), cont = new Set();
    for (const g of scored) for (const m of g.ms) { let l = memberOf.get(m); if (!l) memberOf.set(m, l = []); l.push(g); }
    for (const h of scored) {
      if (h.n < 3) continue;                  // (two blocks inside a card are its parts, not a list it holds)
      for (let p = h.P.nodeType === 11 ? h.P.host : h.P; p && p !== body; p = p.parentElement)
        // (or a list of the same cards, whatever its score: airbnb's carousel of featured hotels among the listings,
        // most of its cards parked past the edge)
        for (const g of memberOf.get(p) || []) if (g !== h && g.P !== h.P && (base.get(h) >= 0.25 * base.get(g) || h.label === g.label)) cont.add(g);
    }
    for (const g of cont) { g.score *= 0.35; g.why += ' container'; }
  }
  let live =groups.filter(g => g.score > 0).sort((a, b) => b.score - a.score);
  if (arg && arg.debug) {
    const P = (g) => { const p = g.P.nodeType === 11 ? g.P.host : g.P; return p.tagName + (p.id ? '#' + p.id : '') + (typeof p.className === 'string' && p.className ? '.' + p.className.split(' ')[0] : ''); };
    return live.slice(0, arg.debug).map(g => [Math.round(g.score), g.label, g.n, P(g), (g.why || '') + (g.ext ? ' ext' + g.ext : ''), T(g.ms[0].innerText).slice(0, 90)]);
  }
  if (!live.length) return { score: 0, label: '', n: 0, items: [], others: [] };
  // the group asked for: the best one that contains the element named
  let best = live[0];
  // A block at the head or tail of the list that lacks the class every other member carries is not an item
  // (DuckDuckGo: the AI summary before the results, a "more results" box after them): the class's group stands for it
  if (best.whole) {
    const sub = live.find(g => !g.whole && g.P === best.P && g.ms.length >= best.ms.length - 2 && g.ms.length >= 0.75 * best.ms.length && g.score >= 0.6 * best.score
      && (() => { const a = best.ms.indexOf(g.ms[0]), b = best.ms.indexOf(g.ms[g.ms.length - 1]); return a >= 0 && b - a + 1 === g.ms.length; })());
    if (sub) best = sub;
  }
  const pk = arg && arg.pick;
  const byLabel = pk && pk.label ? live.find(g => g.label === pk.label || g.label.startsWith(pk.label + '.')) : null;
  // a text that names a heading: the best group in that heading's section (up to the next heading of its level)
  const HS = 'h1,h2,h3,h4,h5,h6,[role=heading]';
  const lvl = (h) => /^H\d$/.test(h.tagName) ? +h.tagName[1] : (+h.getAttribute('aria-level') || 2);
  let inHead = null;
  if (!byLabel && pk && (pk.text || pk.label)) {
    const q = T(pk.text || pk.label).toLowerCase(), hs = [...document.querySelectorAll(HS)].filter(h => vis(h) && T(h.innerText));
    const h = hs.find(x => T(x.innerText).toLowerCase() === q) || hs.find(x => T(x.innerText).toLowerCase().startsWith(q));
    if (h) {
      const end = hs.slice(hs.indexOf(h) + 1).find(x => lvl(x) <= lvl(h) && !h.contains(x));
      const after = (a, b) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
      inHead = live.find(g => after(h, g.ms[0]) && !g.ms[0].contains(h) && (!end || after(g.ms[g.ms.length - 1], end)));
    }
  }
  if (byLabel) best = byLabel;
  else if (inHead) best = inHead;
  else if (pk) {
    let el = null;
    {
      try {
        if (pk.ref) el = document.querySelector('[data-pb="' + pk.ref + '"]');
        else if (pk.css) el = document.querySelector(pk.css);
        else if (pk.text || pk.label) {
          const q = (pk.text || pk.label).toLowerCase();
          for (const r of roots) {
            const w = document.createTreeWalker(r, NodeFilter.SHOW_TEXT);
            for (let n = w.nextNode(); n; n = w.nextNode()) if (n.nodeValue.toLowerCase().includes(q) && n.parentElement && vis(n.parentElement)) { el = n.parentElement; break; }
            if (el) break;
          }
        }
      } catch (e) { return { error: String(e).slice(0, 200) }; }
      if (!el) return { score: 0, label: '', n: 0, items: [], others: [], missing: true };
      const inG = live.filter(g => g.ms.some(m => m.contains(el)));
      if (!inG.length) return { score: 0, label: '', n: 0, items: [], others: [], outside: true };
      best = inG[0];
      if (pk.text || pk.label) {
        // a text names a record of the list meant, not the buttons inside that record (opentable: --in "Saltie Girl" took
        // the card's row of time buttons): the outermost group around it that is not page layout
        const hostP = (g) => (g.P.nodeType === 11 ? g.P.host : g.P);
        const cand = inG.filter(g => !(g.why || '').includes('container'));
        const outer = cand.filter(g => !cand.some(o => o !== g && o.ms.some(m => m.contains(hostP(g)))));
        if (outer.length) best = outer[0];
      }
    }
  }
  // Not a result list: a few blocks of different kinds (Google Flights after a failed search: the filter bar, the box
  // "Oops, something went wrong. No results returned." and the footer read as records #1 to #3), when the page says it
  // has nothing to list, or when there are only two of them. The page's own words say why
  if (!pk) {
    const cls = (m) => (typeof m.className === 'string' ? m.className.trim() : '');
    const vm = best.ms.filter(vis);
    if (vm.length <= 4 && !best.label.includes('.') && new Set(vm.map(cls)).size === vm.length) {
      const EMPTY = /^(no (results?|matches|items|flights|listings|products)( (were )?(returned|found|available))?|nothing (was )?found|(oops,? )?something went wrong|0 results|your search did not match|we couldn'?t find|sorry,? (no|there are no|nothing))\b/i;
      const said = [];
      for (const r of roots) {
        const w = document.createTreeWalker(r, NodeFilter.SHOW_TEXT);
        for (let n = w.nextNode(); n && said.length < 4; n = w.nextNode()) {
          const s = T(n.nodeValue);
          if (s.length <= 160 && EMPTY.test(s) && n.parentElement && vis(n.parentElement) && !said.includes(s)) said.push(s);
        }
      }
      if (said.length || vm.length === 2) return { score: 0, label: best.label, n: 0, items: [], others: [], noList: vm.length, said };
    }
  }
  const disp = new Map();
  const D = (el) => { let d = disp.get(el); if (d === undefined) { d = getComputedStyle(el).display; disp.set(el, d); } return d; };
  const blockOf = (el, stop) => { for (let p = el; p && p !== stop; p = p.parentElement) if (!D(p).startsWith('inline') && D(p) !== 'contents') return p; return stop; };
  // the text pieces of one record in reading order: text that runs on in one line of one block is one piece
  const pieces = (els) => {
    const out = [];
    let prev = null;
    const visit = (node, stop) => {
      for (const c of (node.shadowRoot ? node.shadowRoot.childNodes : node.childNodes)) {
        if (c.nodeType === 1) {
          if (SKIP.test(c.tagName) && c.tagName !== 'IMG') continue;
          if (D(c) === 'none') continue;
          if (c.tagName === 'IMG') continue;
          const lab = c.getAttribute('role') === 'img' && !T(c.textContent) ? T(c.getAttribute('aria-label')) : '';
          if (lab) { out.push(lab); prev = null; continue; }
          // an empty element that draws a separator with CSS (Google Flights: "·" between two airlines, which ran
          // together as "Tap Air Portugal JetBlue"): the next text on the line goes after that separator
          if (prev && !c.firstElementChild && !T(c.textContent) && D(c).startsWith('inline')) {
            for (const ps of ['::before', '::after']) {
              const cc = getComputedStyle(c, ps).content;
              const s = cc && /^".+"$/.test(cc) && cc.length <= 6 ? cc.slice(1, -1).trim() : '';
              if (/^[\p{P}|]{1,3}$/u.test(s)) { prev.sep = s; break; }
            }
          }
          visit(c, stop);
        } else if (c.nodeType === 3) {
          let s = T(c.nodeValue);
          if (!s) continue;
          const pe = c.parentElement || (c.parentNode && c.parentNode.host);
          // a bare number whose meaning is only in a label around it (semanticscholar: "1" in a box labelled
          // "1 citation"): the label says it
          if (pe && /^[\d.,]+[kKmM]?$/.test(s)) {
            for (let p = pe, i = 0; p && p !== stop && i < 4; p = p.parentElement, i++) {
              const lab = T(p.getAttribute('aria-label') || p.getAttribute('title') || '');
              // (the number itself, not digits of another: Google Flights' "+1" day, under a label "Arrival time: 5:35
              // AM on Saturday, January 16.", became that label)
              const at = lab.indexOf(s), ok = at >= 0 && !/\d/.test(lab[at - 1] || '') && !/\d/.test(lab[at + s.length] || '');
              if (lab && lab.length <= 60 && /\p{L}{3}/u.test(lab) && ok) { s = lab; break; }
            }
          }
          if (!pe || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(pe.tagName)) continue;
          // (opacity too: YouTube cards carry a "Now playing" overlay that shows only on hover)
          if (pe.checkVisibility && !pe.checkVisibility({ checkVisibilityCSS: true, checkOpacity: true, opacityProperty: true })) continue;
          // text drawn in a transparent colour is not seen. ebay puts a reversed "derosnopS" so in every card and draws the
          // word as an image only on ads, whose label (aria-labelledby) then reads Sponsored: that label decides
          if (/rgba\([^)]*,\s*0\)$|^transparent$/.test(getComputedStyle(pe).color)) {
            const lab = pe.closest('[aria-labelledby]');
            if (lab && /^derosnops$/i.test(s)) {
              const t = lab.getAttribute('aria-labelledby').split(/\s+/).map(id => { const e = document.getElementById(id); return e ? e.textContent : ''; }).join(' ');
              if (/\bsponsored\b/i.test(t)) { out.push('Sponsored'); prev = null; }
            }
            continue;
          }
          const rg = document.createRange();
          rg.selectNodeContents(c);
          const rs = rg.getClientRects();
          if (!rs.length) continue;
          const first = rs[0], last = rs[rs.length - 1], blk = blockOf(pe, stop);
          if (prev && prev.blk === blk) {
            const same = first.top < prev.r.bottom - 1 && first.bottom > prev.r.top + 1, gap = first.left - prev.r.right;
            if (same && gap > -2 && (gap < 12 || (prev.sep && gap < 30))) {
              const cur = out[out.length - 1];
              // "$" "19" and raised "99": a price drawn as dollars and cents with no dot
              // (raised above the dollars, or drawn smaller than them: amazon.com's cents are small and shifted up, yet
              // still below the top of the dollars' line, and "$19" "99" came out as $1999)
              const cents = gap < 1.5 && /^\d\d$/.test(s) && /\p{Sc}\d+$/u.test(cur)
                && (first.top < prev.r.top - 1 || first.height < prev.r.height * 0.8);
              out[out.length - 1] = cur + (prev.sep ? ' ' + prev.sep + ' ' : cents ? '.' : gap >= 1.5 || /^\s/.test(c.nodeValue) || prev.ws ? ' ' : '') + s;
              prev = { blk, r: last, ws: /\s$/.test(c.nodeValue) };
              continue;
            }
          }
          out.push(s);
          prev = { blk, r: last, ws: /\s$/.test(c.nodeValue) };
        }
      }
    };
    for (const el of els) { prev = null; visit(el, el); }
    const seenP = new Set(), res = [];
    const titled = els.flatMap(el => [...el.querySelectorAll('a[title],[title]')].slice(0, 20));
    for (let p of out) {
      if (/^[^\p{L}\p{N}\p{Sc}]{1,3}$/u.test(p)) continue;        // a bullet or a comma between pieces
      if (/^\(?(this )?(link )?opens? (in )?(a )?new (browser )?(window|tab)( or tab)?\)?\.?$/i.test(p)) continue;   // screen-reader words (booking.com)
      // a title cut short on screen ("A Light in the ..."): the whole of it, when a title attribute holds it
      const m = /^(.{3,}?)\s*(\.\.\.|\u{2026})$/u.exec(p);
      if (m) { const f = titled.find(e => (e.getAttribute('title') || '').startsWith(m[1])); if (f) p = T(f.getAttribute('title')); }
      p = p.length > 200 ? p.slice(0, 199) + '...' : p;
      const k = p.toLowerCase();
      if (seenP.has(k)) continue;
      seenP.add(k);
      res.push(p);
    }
    return res;
  };
  const mainLink = (els) => {
    const ls = [];
    for (const el of els) { const up = el.closest('a[href]'); if (up) ls.push(up); ls.push(...el.querySelectorAll('a[href]')); }
    let ok = ls.filter(a => !/^(javascript:|#)/i.test(a.getAttribute('href') || '') && a.href);
    if (!ok.length) return null;
    // a tracking redirect (Amazon's sponsored /sspa/click) when the card also has a plain link of the site's own
    const RED = /\/(sspa|aclk|redirect|click)\b|[?&](url|dest|redirect|redirect_url|adurl)=/i;
    const own = ok.filter(a => !RED.test(a.href) && a.host === location.host);
    if (own.length && ok.some(a => RED.test(a.href))) ok = own;
    const H = 'h1,h2,h3,h4,h5,h6,[role=heading]';
    // the record's title is its first heading: the link that is that heading, or holds it, or reads the same (linkedin:
    // the job's link covers the card and repeats the title for screen readers; the company link sits in a lower heading)
    const th = els.map(el => el.matches(H) ? el : el.querySelector(H)).find(Boolean);
    if (th) {
      const tt = T(th.innerText || th.textContent).toLowerCase();
      const t1 = ok.find(a => a.contains(th) || th.contains(a)) || (tt && ok.find(a => T(a.innerText || a.textContent).toLowerCase() === tt));
      if (t1) return t1;
    }
    const h = ok.find(a => a.querySelector(H) || a.closest(H));
    if (h) return h;
    let b = ok[0], bl = -1;
    for (const a of ok) { const l = T(a.innerText).length; if (l > bl) { b = a; bl = l; } }
    return b;
  };
  const items = [];
  for (const m of best.ms.slice(0, 400)) {
    if (!vis(m)) continue;
    const els = withExt(best, m);
    const ps = pieces(els);
    // a long record loses words from its longest pieces, not its end: the short pieces after a long summary (a
    // citation count, a date, a price) stay (semanticscholar: the count after a TLDR was cut off)
    let pcs = ps.slice();
    for (let k = 0; k < 20 && pcs.join(' | ').length > 600; k++) {
      let li = 0; pcs.forEach((x, i) => { if (x.length > pcs[li].length) li = i; });
      const over = pcs.join(' | ').length - 600, keep = Math.max(60, pcs[li].length - over - 3);
      if (keep >= pcs[li].length) break;
      pcs[li] = pcs[li].slice(0, keep) + '...';
    }
    let t = pcs.join(' | ');
    if (!t) { const im = m.querySelector('img[alt]'); t = im ? T(im.alt) : ''; }
    // a card the page builds as an ad (youtube's ytd-search-pyv-renderer, ad-slot boxes) says so, as ads that print it do
    if (t && /(^|[-_\s])(ads?|pyv|promoted|sponsored)([-_\s]|$)|ad-slot|ad-renderer/i.test(m.tagName.toLowerCase() + ' ' + (typeof m.className === 'string' ? m.className : ''))
        && !/(^|\| )(sponsored|ad|promoted)( \||$)/i.test(t)) t = 'Sponsored | ' + t;
    if (t.length > 900) t = t.slice(0, 899) + '...';
    const ml = mainLink(els);
    // (the link's ref from pb's last scan: `pb click eN` opens the record)
    items.push([t, ml ? ml.href : '', ps.length, ml ? ml.getAttribute('data-pb') || '' : '']);
  }
  // Blocks in the group that are not items: an ad slot that never rendered ("Loading..."), and one shaped unlike the
  // rest (no link where nearly all have one, or a fraction of their pieces: a panel header, an info card).
  const NOTHING = /^(loading|please wait)?[.\s\u{2026}|]*$/iu;
  const linked = items.filter(x => x[1]).length, med = items.map(x => x[2]).sort((a, b) => a - b)[items.length >> 1] || 0;
  let left = 0;
  const kept = items.filter(x => {
    const odd = NOTHING.test(x[0]) || (items.length >= 4 && ((!x[1] && linked >= 0.75 * items.length) || (med >= 3 && x[2] * 3 <= med)));
    if (odd) left++;
    return !odd;
  });
  // every record starts with its own place number ("1." of Hacker News): the record number says it already
  if (kept.length >= 2 && kept.every((x, i) => new RegExp('^' + (i + 1) + '\\.? \\| ').test(x[0])))
    kept.forEach(x => { x[0] = x[0].replace(/^\d+\.? \| /, ''); });
  // the lines or paragraphs of one container (a single search result) are not cards
  if (best.ms.every(m => /^(P|SPAN|BR|DD|DT|LABEL)$/.test(m.tagName)) && !arg.pick)
    return { score: 0, label: best.label, n: 0, items: [], others: [], lines: true };
  items.length = 0;
  items.push(...kept.map(x => [x[0], x[1], x[3]]));
  // other groups worth naming: not the chosen one, not inside its items (the stars of each card), one per label
  const named = new Set([best.label]), others = [];
  for (const g of live) {
    if (others.length >= 5) break;
    if (named.has(g.label) || best.ms.some(m => m.contains(g.P) || g.ms.includes(m))) continue;
    if (g.score < 0.05 * best.score && others.length >= 2) continue;     // (only groups that could be the list meant)
    named.add(g.label);
    others.push([g.label, g.n, Math.round(g.score)]);
  }
  return { score: Math.round(best.score), label: best.label, n: items.length, items, others, left };
}
"""

# pb links: [text, address, ref] of every link that shows (script links left out: they have no address)
LINKS_JS = r"""
() => {
  const T = (s) => (s || '').replace(/\s+/g, ' ').trim(), out = [];
  for (const a of document.querySelectorAll('a[href],area[href]')) {
    const h = a.href;
    if (!h || /^javascript:/i.test(h)) continue;
    if (a.checkVisibility && !a.checkVisibility({ checkVisibilityCSS: true })) continue;
    const r = a.getBoundingClientRect();
    if (r.width < 1 && r.height < 1 && a.tagName !== 'AREA') continue;
    const img = a.querySelector('img[alt]');
    const t = T(a.innerText) || T(a.getAttribute('aria-label')) || (img ? T(img.alt) : '') || T(a.title);
    out.push([t.slice(0, 80), h, a.getAttribute('data-pb') || '']);
    if (out.length >= 3000) break;
  }
  return out;
}
"""

# pb find: the address behind each link ref
HREFS_JS = r"""(refs) => refs.map((r) => { const e = document.querySelector('[data-pb="' + r + '"]'); const a = e && e.closest('a[href],area[href]'); return a ? a.href : ''; })"""

# pb download TARGET: the address an element stands for (its link, its image, or one inside it)
HREF_OF_JS = r"""(e) => { const a = e.closest('a[href],area[href]'); if (a) return a.href;
  if (e.currentSrc || e.src) return e.currentSrc || e.src;
  const i = e.querySelector('a[href],img[src],source[src],video[src],audio[src],embed[src],object[data]');
  if (i) return i.href || i.currentSrc || i.src || i.data || '';
  return e.getAttribute('data-href') || e.getAttribute('data-url') || ''; }"""

# pb table: the data tables of the page, real <table>s and grids built from role=table/grid/row/cell. arg.pick: the
# position of the one to print in full (its rows arg.from..arg.to, 1-based); otherwise only a summary of each.
TABLES_JS = r"""
(arg) => {
  const T = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const vis = (el) => (!el.checkVisibility || el.checkVisibility({ checkVisibilityCSS: true })) && el.getClientRects().length > 0;
  // (a row of no height is a sizing copy: DataTables keeps the header in the body table, squashed to 0 px)
  const rowVis = (r) => vis(r) && r.getBoundingClientRect().height >= 1;
  const GRID = 'table,[role=table],[role=grid],[role=treegrid]';
  const CELL = '[role=cell],[role=gridcell],[role=columnheader],[role=rowheader]';
  const nativeRow = (r) => ({ r, cells: [...r.cells],
    head: r.parentElement.tagName === 'THEAD' || (r.cells.length > 0 && [...r.cells].every(c => c.tagName === 'TH')) });
  const rowsOf = (el) => {
    if (el.tagName === 'TABLE' && !el.querySelector('[role=row]'))
      return [...el.rows].filter(r => r.closest('table') === el && rowVis(r)).map(nativeRow);
    return [...el.querySelectorAll('[role=row]')].filter(r => r.closest(GRID) === el && rowVis(r)).map(r => {
      const cells = [...r.querySelectorAll(CELL)].filter(c => c.closest('[role=row]') === r);
      // a <table role=grid> whose rows say role=row and whose cells say nothing (DataTables): the table's own cells
      if (!cells.length && r.tagName === 'TR') return nativeRow(r);
      return { r, cells, head: cells.length > 0 && cells.every(c => c.getAttribute('role') === 'columnheader') };
    });
  };
  const byIds = (ids) => T(ids.split(/\s+/).map(id => { const e = document.getElementById(id); return e ? e.innerText : ''; }).join(' '));
  // The heading right before the table (or its box): not one past a block of other content (yahoo's history table was
  // named after a "Trading disclosure" heading further up, wikipedia's navboxes after "Bibliography")
  const headingBefore = (el) => {
    let p = el;
    for (let up = 0; up < 3 && p && p !== document.body; up++, p = p.parentElement) {
      let s = p.previousElementSibling;
      for (let k = 0; s && k < 3; k++, s = s.previousElementSibling) {
        if (/^H[1-6]$/.test(s.tagName) || s.getAttribute('role') === 'heading') return T(s.innerText);
        if (s.matches(GRID) || s.querySelector(GRID)) return '';
        const hs = s.querySelectorAll('h1,h2,h3,h4,h5,h6,[role=heading]');
        if (hs.length) { const h = hs[hs.length - 1], after = T(s.innerText).length - T(h.innerText).length; return after < 200 ? T(h.innerText) : ''; }
        if (T(s.innerText).length > 200) return '';
      }
    }
    return '';
  };
  const out = [];
  const all = [...document.querySelectorAll(GRID)].filter(el => el.getAttribute('role') !== 'presentation' && el.getAttribute('role') !== 'none' && vis(el));
  const used = new Set();
  for (let ti = 0; ti < all.length; ti++) {
    const el = all[ti];
    if (used.has(el)) continue;
    let rows = rowsOf(el);
    // A table in two parts (DataTables, scrolling grids): one table holds only the header row, the next one in the same
    // box the data rows, column for column. Read as one table.
    if (rows.length && rows.every(x => x.head) && ti + 1 < all.length) {
      const nx = all[ti + 1], box = el.parentElement && el.parentElement.parentElement && el.parentElement.parentElement.parentElement;
      const nrows = box && box.contains(nx) ? rowsOf(nx) : [];
      const hc = rows[rows.length - 1].cells.length;
      if (nrows.length && nrows.some(x => !x.head) && Math.max(...nrows.map(x => x.cells.length)) === hc) {
        rows = rows.concat(nrows.filter(x => !x.head));
        used.add(nx);
      }
    }
    const cols = Math.max(0, ...rows.map(x => x.cells.length));
    const hn = rows.findIndex(x => !x.head);
    const heads = rows.slice(0, hn < 0 ? rows.length : hn);
    if (cols < 2 && !heads.length) continue;                   // a layout box, not data
    const name = T((el.caption && el.caption.innerText) || el.getAttribute('aria-label') || (el.getAttribute('aria-labelledby') ? byIds(el.getAttribute('aria-labelledby')) : ''));
    const t = { name: name.slice(0, 300), heading: headingBefore(el).slice(0, 300), cols, rows: rows.length - heads.length,
                head: heads.length ? heads[heads.length - 1].cells.map(c => T(c.innerText).slice(0, 40)) : [] };
    // pb table TEXT where TEXT is in a cell, not a caption or header (pb text said "a match is a table row")
    // (a row of th cells inside the table counts too: wikipedia's infobox has "Population (2020)" as a header row of its own)
    if (arg.find) { const q = arg.find, i = rows.findIndex(x => x.cells.some(c => T(c.innerText).toLowerCase().includes(q))); t.row = i < 0 ? 0 : Math.max(1, i + 1 - heads.length); }
    if (out.length + 1 === arg.pick) {
      const cell = (c) => { const s = T(c.innerText); return s.length > 600 ? s.slice(0, 599) + '…' : s; };
      t.headRows = heads.map(x => x.cells.map(cell));
      t.data = rows.slice(heads.length).slice(arg.from - 1, arg.to).map(x => x.cells.map(cell));
    }
    out.push(t);
    if (out.length >= 60) break;
  }
  return out;
}
"""

# pb text --section: the text under a heading, up to the next heading of the same or a higher level. Read from the
# text nodes in between, a line per block, without touching the page's selection.
SECTION_JS = r"""
(arg) => {
  // arg: the heading's text, or { name, nth }: the nth of the headings that match (1 = the first)
  const name = typeof arg === 'string' ? arg : arg.name, want = (arg && arg.nth) || 1;
  const T = (s) => (s || '').replace(/\s+/g, ' ').trim();
  let vis = (el) => !el.checkVisibility || el.checkVisibility({ checkVisibilityCSS: true });
  const HS = 'h1,h2,h3,h4,h5,h6,[role=heading]';
  const all = [...document.querySelectorAll(HS)];
  let hs = all.filter(h => vis(h) && T(h.innerText));
  const lvl = (h) => /^H\d$/.test(h.tagName) ? +h.tagName[1] : (+h.getAttribute('aria-level') || 2);
  const q = T(name).toLowerCase();
  let txt = (h) => T(h.innerText).toLowerCase();
  // (words only: "2     DOSAGE AND ADMINISTRATION" is the heading "Dosage and administration")
  const W = (s) => s.replace(/^[\d.\s]+/, '').replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
  const tiers = (list) => [list.filter(x => txt(x) === q || W(txt(x)) === W(q)), list.filter(x => txt(x).startsWith(q) || W(txt(x)).startsWith(W(q))),
                           list.filter(x => txt(x).includes(q) || W(txt(x)).includes(W(q)))].find(l => l.length) || [];
  let cands = tiers(hs), hidden = false;
  if (!cands.length) {
    // a heading in a part of the page that is collapsed (dailymed.nlm.nih.gov: the label's sections until VIEW ALL
    // SECTIONS is clicked): its text is in the page, read as it is
    const shut = all.filter(h => !hs.includes(h) && T(h.textContent));
    txt = (h) => T(h.textContent).toLowerCase();
    cands = tiers(shut);
    if (cands.length) { hidden = true; hs = all.filter(h => T(h.textContent)); vis = () => true; }
  }
  if (!cands.length) {
    // the closest names first: those that share the most words with the one asked for
    const ws = new Set(W(q).split(' ').filter(Boolean)), score = (h) => W(txt(h)).split(' ').filter(x => ws.has(x)).length;
    const near = hs.map((x, i) => [score(x), i, x]).sort((a, b) => b[0] - a[0] || a[1] - b[1]).slice(0, 12).sort((a, b) => b[0] - a[0] || a[1] - b[1]);
    return { found: false, heads: near.map(([, , x]) => T(x.innerText).slice(0, 60)), total: hs.length };
  }
  // several headings by that name (a PMC article: "Results" in the abstract, h3, and the body's Results, h2): the
  // highest level first, then in page order
  // (same level: the longer section first; dailymed's label has "DOSAGE AND ADMINISTRATION" in its highlights, a
  // few lines, and as the full section)
  const span = (x) => {
    const L0 = lvl(x), nx = hs.slice(hs.indexOf(x) + 1).find(y => lvl(y) <= L0 && !x.contains(y)), r = document.createRange();
    r.setStartAfter(x);
    if (nx) r.setEndBefore(nx); else r.setEndAfter(document.body.lastChild || document.body);
    return r.toString().length;
  };
  const lens = new Map(cands.length > 1 ? cands.map(x => [x, span(x)]) : []);
  cands = cands.map((x, i) => [x, i]).sort((a, b) => lvl(a[0]) - lvl(b[0]) || (lens.get(b[0]) || 0) - (lens.get(a[0]) || 0) || a[1] - b[1]).map(a => a[0]);
  const h = cands[Math.min(want, cands.length) - 1];
  const count = cands.length;
  const hText = (x) => hidden ? T(x.textContent) : T(x.innerText);
  const L = lvl(h);
  let end = null;
  for (const x of hs.slice(hs.indexOf(h) + 1)) if (lvl(x) <= L && !h.contains(x)) { end = x; break; }
  const range = document.createRange();
  range.setStartAfter(h);
  if (end) range.setEndBefore(end); else range.setEndAfter(document.body.lastChild || document.body);
  const blocks = new Map();
  const blockOf = (el) => {
    for (let p = el; p && p !== document.body; p = p.parentElement) {
      let b = blocks.get(p);
      if (b === undefined) { const d = getComputedStyle(p).display; b = !(d.startsWith('inline') || d === 'contents'); blocks.set(p, b); }
      if (b) return p;
    }
    return document.body;
  };
  const lines = [];
  let cur = '', curB = null, curLi = null;
  const w = document.createTreeWalker(range.commonAncestorContainer, NodeFilter.SHOW_TEXT);
  for (let nd = w.nextNode(); nd; nd = w.nextNode()) {
    if (!range.intersectsNode(nd)) continue;
    const pe = nd.parentElement;
    if (!pe || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(pe.tagName) || !vis(pe)) continue;
    const s = nd.nodeValue.replace(/\s+/g, ' ');
    if (!s.trim()) { cur += ' '; continue; }
    const b = blockOf(pe), li = pe.closest('li');
    if (b !== curB) { if (T(cur)) lines.push(T(cur)); cur = (b.matches('h1,h2,h3,h4,h5,h6,[role=heading]') ? '# ' : ''); curB = b; }
    else if (li && curLi && li !== curLi && T(cur)) cur += ' | ';      // list items side by side ("Lana Wachowski | Lilly Wachowski")
    curLi = li;
    cur += s;
  }
  if (T(cur)) lines.push(T(cur));
  // for cutting the section out of the lines pb text reads (do_text_section): the heading, which one of the headings
  // with that text it is, the heading that ends it, and the headings inside it
  const same = hs.slice(0, hs.indexOf(h)).filter(x => hText(x) === hText(h)).length;
  const inner = hs.slice(hs.indexOf(h) + 1, end ? hs.indexOf(end) : hs.length).map(hText);
  return { found: true, name: hText(h).slice(0, 80), tag: /^H\d$/.test(h.tagName) ? h.tagName.toLowerCase() : 'heading', text: lines.join('\n'),
           head: hText(h), nth: same, end: end ? hText(end) : null, inner, count, pick: Math.min(want, count), hidden };
}
"""

# pb drag, for a page that listens to HTML5 drag events only and ignored the mouse drag: the same events by script,
# with one DataTransfer carried from dragstart to drop, as the browser does.
DND_JS = r"""
([src, dst]) => {
  const dt = new DataTransfer(), r = dst.getBoundingClientRect(), s = src.getBoundingClientRect();
  const at = (b) => ({ clientX: b.left + b.width / 2, clientY: b.top + b.height / 2 });
  const fire = (el, type, b) => el.dispatchEvent(new DragEvent(type, { bubbles: true, cancelable: true, composed: true, dataTransfer: dt, ...at(b) }));
  fire(src, 'dragstart', s);
  fire(dst, 'dragenter', r);
  fire(dst, 'dragover', r);
  fire(dst, 'drop', r);
  fire(src, 'dragend', r);
  return true;
}
"""

# Input types whose value has a fixed format (pb fill turns common human spellings into it, see field_value)
VALUE_FORMATS = {"date": "YYYY-MM-DD (or 12/25/2026, Dec 25, 2026)", "time": "HH:MM (or 3:30 PM)", "month": "YYYY-MM (or Dec 2026)",
                 "week": "YYYY-Www", "datetime-local": "YYYY-MM-DDTHH:MM", "color": "#rrggbb"}


def field_value(kind, v):
    """A value for an input of type `kind` in the format the field takes, from that format or a common human one
    ("12/25/2026", "Dec 25, 2026" -> 2026-12-25; "3:30 PM" -> 15:30). None when it cannot be read."""
    import datetime as dt
    s = re.sub(r"\s+", " ", v.strip())

    def parse(text, fmts):
        text = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", text).replace(" ,", ",")
        for f in fmts:
            with contextlib.suppress(ValueError):
                return dt.datetime.strptime(text, f)
        return None

    dates = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%Y/%m/%d", "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y",
             "%d %b %Y", "%d %B %Y", "%a, %b %d, %Y", "%A, %B %d, %Y", "%d.%m.%Y"]
    times = ["%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p", "%I %p", "%I%p", "%H.%M"]
    if kind == "date":
        d = parse(s, dates)
        return d.strftime("%Y-%m-%d") if d else None
    if kind == "time":
        if re.fullmatch(r"\d\d:\d\d(:\d\d(\.\d+)?)?", s):
            return s
        d = parse(s.upper(), times)
        return d.strftime("%H:%M") if d else None
    if kind == "month":
        d = parse(s, ["%Y-%m", "%b %Y", "%B %Y", "%m/%Y", "%Y/%m", "%m-%Y"])
        return d.strftime("%Y-%m") if d else None
    if kind == "week":
        return s.upper() if re.fullmatch(r"\d{4}-W\d\d", s, re.I) else None
    if kind == "datetime-local":
        m = re.fullmatch(r"(\d{4}-\d\d-\d\d)[T ](\d\d:\d\d(:\d\d)?)", s)
        if m:
            return f"{m.group(1)}T{m.group(2)}"
        for cut in (", ", " "):
            if cut in s:
                head, _, tail = s.rpartition(cut)
                d, t = parse(head, dates), parse(tail.upper(), times)
                if d is None and " " in head:           # "Dec 25, 2026 3:30 PM": the time may be two words
                    h2, _, t1 = head.rpartition(" ")
                    d, t = parse(h2, dates), parse((t1 + " " + tail).upper(), times)
                if d and t:
                    return d.strftime("%Y-%m-%d") + "T" + t.strftime("%H:%M")
        return None
    if kind == "color":
        m = re.fullmatch(r"#?([0-9a-f]{6}|[0-9a-f]{3})", s, re.I)
        if m:
            h = m.group(1).lower()
            return "#" + (h if len(h) == 6 else "".join(c * 2 for c in h))
        m = re.fullmatch(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(,[^)]*)?\)", s, re.I)
        return "#" + "".join(f"{min(255, int(x)):02x}" for x in m.groups()[:3]) if m else None
    return s


_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def date_of(text):
    """(year or None, month, day) a text names as a calendar day, in any common form and word order: "January 15, 2027",
    "Jan 15 2027", "2027-01-15", "1/15/2027", "15, Friday, January 2027", "Friday, January 15" (no year). None if none.
    Google Flights and amtrak label their day cells "Friday, January 15, 2027"; a click by the date in another form
    matched nothing."""
    s = (text or "").lower()
    if len(s) > 80:
        return None
    m = re.fullmatch(r"\s*(\d{4})-(\d{1,2})-(\d{1,2})\s*", s)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    m = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*", s)
    if m:
        return int(m.group(3)), int(m.group(1)), int(m.group(2))
    mon = re.findall(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?(?=\W|$)", s)
    if len(mon) != 1:
        return None
    year = re.findall(r"\b(19\d\d|20\d\d)\b", s)
    rest = re.sub(r"\b(19\d\d|20\d\d)\b", " ", s)
    days = [int(x) for x in re.findall(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", rest) if 1 <= int(x) <= 31]
    if len(days) != 1 or len(year) > 1:
        return None
    # nothing else in it but weekday names and punctuation (not "15 items from January")
    left = re.sub(r"\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*\b|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?|\b\d{1,4}(st|nd|rd|th)?\b|"
                  r"\b(selected|today|available|unavailable|departure|return|check-?in|check-?out|date)\b|[\s,.\-:()]", "", s)
    if left:
        return None
    return (int(year[0]) if year else None), _MONTHS[mon[0]], days[0]


def same_day_key(a, b):
    """Two date_of() results name the same day (a missing year matches any)."""
    return bool(a and b and a[1:] == b[1:] and (a[0] is None or b[0] is None or a[0] == b[0]))


def same_date(typed, shown):
    """A date field that writes the typed date its own way (Google Flights: "Jan 15, 2027" became "Fri, Jan 15"): the
    shown text has the same day of the month, and the same month by name or number."""
    iso = field_value("date", typed)
    if not iso or not shown:
        return False
    import datetime as dt
    d = dt.date.fromisoformat(iso)
    return (re.search(rf"(?<!\d)0?{d.day}(?!\d)", shown) is not None
            and (d.strftime("%b").lower() in shown.lower() or re.search(rf"(?<!\d)0?{d.month}(?!\d)", shown) is not None))


def unique_path(path):
    """`path`, or with -1, -2... before its extension when a file of that name exists, created empty at once so that
    two downloads of the same name cannot take the same path. A download never replaces a file."""
    base, ext = os.path.splitext(path)
    n = 0
    while True:
        p = path if n == 0 else f"{base}-{n}{ext}"
        try:
            with open(p, "x"):
                return p
        except FileExistsError:
            n += 1


def same_as_earlier(path):
    """A file just saved as NAME-N.ext that is byte for byte NAME.ext (or an earlier NAME-K.ext): the copy is removed
    and the earlier file's path returned (dailymed: opening the PDF address a second time left a -1.pdf twin), else
    None."""
    m = re.match(r"^(.*)-(\d+)(\.[^./\\]*)?$", path)
    if not m:
        return None
    import filecmp
    for k in range(0, int(m.group(2))):
        p = f"{m.group(1)}{'' if k == 0 else '-' + str(k)}{m.group(3) or ''}"
        with contextlib.suppress(Exception):
            if os.path.isfile(p) and os.path.getsize(p) == os.path.getsize(path) and filecmp.cmp(p, path, shallow=False):
                os.remove(path)
                return p
    return None


def file_url_path(url):
    """The local path of a file: address (file:///C:/x/y.pdf -> C:\\x\\y.pdf), else None. The browser's request
    context fetches http(s) only ("Protocol file: not supported")."""
    if not url.lower().startswith("file:"):
        return None
    from urllib.parse import unquote, urlparse
    from urllib.request import url2pathname
    u = urlparse(url)
    p = url2pathname(u.path) if os.name == "nt" else unquote(u.path)     # (url2pathname unquotes itself)
    if u.netloc and u.netloc.lower() != "localhost":
        p = "\\\\" + u.netloc + p if os.name == "nt" else "//" + u.netloc + p
    return p


def safe_name(name):
    """A file name as a site suggests it, made safe to save under: no directories, no characters Windows refuses."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (name or "").strip()).strip(". ")
    return name[:150] or "download"


def slash(p):
    return p.replace("\\", "/")


def code_like(line):
    """Minified script or JSON shown as text (payment and captcha frames): long, dense with symbols, almost no spaces."""
    if len(line) < 60:
        return False
    sym = sum(line.count(c) for c in "{}()[];=<>!&|,:")
    return sym / len(line) > 0.12 and line.count(" ") / len(line) < 0.08

# ----------------------------------------------------------------------------------------- failure capture (test runs)

# A static copy of one document, good enough to replay a scan or a click on offline: current form state written into
# the markup, open shadow roots serialized as declarative shadow DOM, every stylesheet read from the CSSOM (so rules
# inserted by script are kept), images pinned to the size they had, iframes tagged so their own copies can be put back.
SNAP_JS = r"""
(arg) => {
  const roots = [];
  let nimg = 0;
  const sizes = [];
  const walk = (root) => {
    for (const el of root.querySelectorAll('*')) {
      const t = el.tagName;
      if (t === 'INPUT') {
        if (el.type === 'checkbox' || el.type === 'radio') { if (el.checked) el.setAttribute('checked', ''); else el.removeAttribute('checked'); }
        else if (el.type !== 'password' && el.type !== 'file') el.setAttribute('value', el.value);
      } else if (t === 'OPTION') { if (el.selected) el.setAttribute('selected', ''); else el.removeAttribute('selected'); }
      else if (t === 'IFRAME' || t === 'FRAME') el.setAttribute('data-pb-snap', arg.prefix + '-' + (arg.n++));
      else if (t === 'IMG' || t === 'VIDEO' || t === 'CANVAS' || t === 'svg') {
        const r = el.getBoundingClientRect();
        if (r.width || r.height) { el.setAttribute('data-pb-img', String(nimg)); sizes.push('[data-pb-img="' + nimg + '"]{width:' + r.width.toFixed(1) + 'px!important;height:' + r.height.toFixed(1) + 'px!important}'); nimg++; }
      }
      if (el.shadowRoot) {
        roots.push(el.shadowRoot);
        const ad = el.shadowRoot.adoptedStyleSheets || [];
        if (ad.length && !el.shadowRoot.querySelector('style[data-pb-snap-style]')) {
          const st = document.createElement('style');
          st.setAttribute('data-pb-snap-style', '1');
          try { st.textContent = ad.map(s => [...s.cssRules].map(r => r.cssText).join('\n')).join('\n'); el.shadowRoot.prepend(st); } catch (e) {}
        }
        walk(el.shadowRoot);
      }
    }
  };
  walk(document);
  const css = [];
  const sheets = [...document.styleSheets].concat([...(document.adoptedStyleSheets || [])]);
  for (const s of sheets) {
    try { css.push({ text: [...s.cssRules].map(r => r.cssText).join('\n') }); }
    catch (e) { if (s.href) css.push({ href: s.href }); }
  }
  css.push({ text: sizes.join('\n') });
  const de = document.documentElement;
  const attrs = [...de.attributes].map(a => ' ' + a.name + '="' + a.value.replace(/&/g, '&amp;').replace(/"/g, '&quot;') + '"').join('');
  let inner;
  try { inner = de.getHTML({ shadowRoots: roots }); } catch (e) { inner = de.innerHTML; }
  return { html: (document.compatMode === 'CSS1Compat' ? '<!doctype html>' : '') + '<html' + attrs + '>' + inner + '</html>', css, url: location.href, n: arg.n };
}
"""

# ----------------------------------------------------------------------------------------- card data censor

CARD_SEP = "[ \\-\u00a0\u2009\u202f.]"
PAN_RX = re.compile(r"(?<![\d.,])\d(?:" + CARD_SEP + r"?\d){11,18}(?!\d)")       # 12 to 19 digits, single separators allowed


def luhn_ok(d):
    total = 0
    for i, ch in enumerate(reversed(d)):
        n = ord(ch) - 48
        if i % 2:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def card_like(d):
    """A digit string with the length and first digits of a payment card brand, and a valid checksum."""
    n = len(d)
    if not 13 <= n <= 19:
        return False
    p2, p3, p4 = int(d[:2]), int(d[:3]), int(d[:4])
    brand = ((d[0] == "4" and n in (13, 16, 19)) or (51 <= p2 <= 55 and n == 16) or (2221 <= p4 <= 2720 and n == 16)       # Visa, Mastercard
             or (p2 in (34, 37) and n == 15)                                                                       # Amex
             or ((p4 == 6011 or p2 == 65 or 644 <= p3 <= 649) and n >= 16)                                         # Discover
             or (3528 <= p4 <= 3589 and n >= 16) or ((300 <= p3 <= 305 or p2 in (36, 38)) and n >= 14)             # JCB, Diners
             or (p2 == 62 and n >= 16))                                                                            # UnionPay
    return brand and luhn_ok(d)


def scrub_pans(text):
    """Hide anything that reads as a card number, keeping its last four digits (as a receipt would)."""
    def rep(m):
        s = m.group(0)
        parts = re.split("(" + CARD_SEP + ")", s)                 # digit groups at even indexes, separators between
        groups = parts[0::2]
        if len(groups) == 1:
            return f"[card number hidden, ends {s[-4:]}]" if card_like(s) else s
        # a card written in groups (4-4-4-4, 4-6-5...), possibly with other numbers before or after it on the line
        for i in range(len(groups)):
            for j in range(len(groups), i + 1, -1):
                lens = [len(g) for g in groups[i:j]]
                d = "".join(groups[i:j])
                shaped = (all(x == 4 for x in lens[:-1]) and lens[-1] <= 4) or lens in ([4, 6, 5], [4, 6, 4])
                if shaped and card_like(d):
                    return "".join(parts[:2 * i]) + f"[card number hidden, ends {d[-4:]}]" + "".join(parts[2 * j - 1:])
        return s
    return PAN_RX.sub(rep, text)


class Censor:
    """Keeps card data out of everything pb prints or logs. Three layers:
    1. the card numbers in the secrets file, however the page spaces or chops them;
    2. any other number that reads as a payment card (brand prefix, length, checksum);
    3. the CVV and expiry from the secrets file where a value shows (quoted, or right after a label naming it).
    Bare three-digit numbers in running text are left alone: hiding every "739" would wreck prices and quantities."""
    LABEL = r"(?:cvv2?|cvc2?|csc|cid|security\s*code|card\s*code|verification(?:\s*code)?|exp(?:iry|iration)?(?:\s*date)?)"

    def __init__(self, secrets):
        self.known, self.short = [], []
        for sec, d in (secrets or {}).items():
            num = re.sub(r"\D", "", d.get("card", "") or d.get("number", ""))
            if len(num) >= 12:
                self.known.append((re.compile(r"[^0-9\n]{0,6}".join(num)), f"[{sec} number hidden]"))
            vals = []
            cvv = next((re.sub(r"\D", "", d[k]) for k in ("cvv", "cvc", "ccv") if d.get(k)), "")
            if 3 <= len(cvv) <= 4:
                vals.append(cvv)
            m = re.match(r"\s*(\d{1,2})\s*/\s*(\d{2,4})", next((d[k] for k in ("expiration", "expiry", "exp") if d.get(k)), ""))
            if m:
                mm, yy = m.group(1).zfill(2), m.group(2)[-2:]
                vals += [f"{mm}/{yy}", f"{mm}{yy}", f"{mm} / {yy}", f"{mm}/20{yy}", f"{mm}-{yy}", f"{mm}20{yy}"]
            for v in vals:
                e = re.escape(v)
                self.short.append((v, re.compile(r"([\"'])" + e + r"([\"'])|((?i:" + self.LABEL + r")[^0-9\n]{0,12})" + e + r"(?!\d)")))

    def scrub(self, text):
        if not text:
            return text
        for rx, label in self.known:
            text = rx.sub(label, text)
        text = scrub_pans(text)
        for v, rx in self.short:
            # Every answer passes through here, and these patterns are slow to run over a whole view (1 ms each, 14 of
            # them for two cards). A text that does not hold the value at all cannot match: skip it.
            if v in text:
                text = rx.sub(lambda m: (m.group(1) + "[hidden]" + m.group(2)) if m.group(1) else m.group(3) + "[hidden]", text)
        return text


class Err(Exception):
    pass


class Gone(Exception):
    """The element a command was about to act on is not in the page any more."""


class NotFound(Err):
    """No element matches the target (as opposed to: several do, or the ref is unknown)."""


class Session:
    def __init__(self, ctx, opts, session):
        self.ctx, self.opts, self.session = ctx, opts, session
        self.page = None
        self.next_ref = 1
        self.refs = {}            # ref -> (frame, item)
        self.pending = {}         # request -> (start time, seconds it may hold up "settled")
        self.req_own = {}         # request -> it went to the site of the page that asked (see busy, on_dcl)
        self.req_seq = 0          # count of requests that matter, to tell whether an action started one
        self.act_t = time.time()  # when the current action (or navigation) started
        self.hung = set()         # hosts and URLs whose requests were seen hanging: ignored from then on
        self.nav_t = 0.0          # when the page last asked for another document
        self.sidelog = {}         # PB_TRACE: the shop's own calls no wait waits for (or only briefly) and still unanswered
        self.req_event = asyncio.Event()      # set whenever a request that matters starts or ends
        self.reqlog = {}          # request -> [start, end]: recent requests that matter, for the timing trace
        self.domlog = []          # when the DOM changed during the last wait, for the timing trace
        self.unfinished = False   # the last answer was written while the page was still loading
        self.read_gave_up = None  # (document start, url) of the page a reading command last waited out in full (read_wait)
        self._censor = None       # (secrets file mtime, Censor)
        self.last_review = None   # the order facts last shown unasked (see maybe_review)
        self.req_no = 0           # requests served so far
        self.review_shown = None  # (request number, review lines) of the last review printed (see asked_review)
        self.cwd = None           # the caller's working directory for the current request
        self.base = None          # probe taken just before the current action (see mark)
        self.base_seq = 0
        self.end = None           # (probe, time) when the last wait or scan ended: the start of the idle gap
        self.noisy = False        # this document changes its DOM all the time by itself (carousel, ticker)
        self.scan = None          # last full scan, reused while the page cannot have changed
        self.dirty = True         # an action ran since the last scan
        self.ref_hist = {}        # ref -> (kind, text, name, frame) of refs handed out recently, to re-find re-rendered elements
        self.fmap = {}            # stamp of a frame element (data-pbf) -> the frame it holds (see shown_children)
        self.fclosed = {}         # frame -> its frame element, for frames whose element no scan can see
        self.fasked = {}          # frame -> when it was last asked for its frame element
        self.frame_vis = {}       # frame -> did it show at the last scan
        self.reused = False       # the last collect() was served from that scan
        self.notes = []           # dialogs, popups since last output
        self.http_errs = []       # (time, "POST /path -> HTTP 403"): the shop's own requests that failed (see watch)
        self.tab_switched = False # a new tab took over since the last answer
        self.tab_at = 0.0         # when it did
        self.in_batch = False     # the current request is a pb do batch of several steps
        self.cover_said = set()   # pages where a click already said in full what covered its target (see do_click)
        self.http_said = set()    # plain-HTTP hosts already named in a NOTE (see note_plain_http)
        self.batch_url, self.batch_acted = None, False     # where the running command began, and whether it has acted yet
        self.status_due = False   # pb open ran in this command: name an error status of the page in the answer
        self.lock = asyncio.Lock()
        self.closed = asyncio.Event()
        self.last_cmd = time.time()
        self.spans = []           # (name, seconds) of the current request, written to <session>.timing.jsonl
        self.secrets_path = opts.get("secrets") or os.environ.get("PB_SECRETS") or DEFAULT_SECRETS
        self.human_flag = None    # the page last reported as a human check
        self.soft_waited = None   # the address whose browser check was given its time to pass by itself (collect)
        self.human_text = ""
        self.patience = 8         # seconds a command waits for a target that is not there while the page is loading
        self.capture_dir = os.environ.get("PB_CAPTURE") or ""      # test runs: where failed commands leave a page copy
        self.captures = 0
        self.dialog_next = None   # ("accept", text or None) | ("dismiss", None): what to do with the next JS dialog (pb dialog)
        # the last request that choice holds for: the one that set it, or the next one when `dialog` was its last step
        # (pb dialog dismiss, then pb click Delete). It does not wait for a dialog that comes commands later.
        self.dialog_until = 0
        self.steps_left = 0       # steps of the batch after the one running
        self.dl_pending = []      # downloads being saved (see save_download)
        self.dl_lines = []        # "DOWNLOAD saved ..." lines not printed yet
        self.pdf_dl = None        # (path, address of the page then): a PDF the page sent as a download, for pb text
        self.last_fetch = None    # (path, is a PDF): the file fetch_to_file saved last
        self.view_due = False     # in a batch: its answer will be a whole view, not what changed (see execute)
        self.quiet_same = False   # the answer is not to say "(no visible change)" (a scroll: what is in view says it)
        self.prev_page = None     # the tab that was current before `pb tab new`, to go back to when that tab is closed
        self.sugg_hint = None     # (first suggestion, line): a plain fill opened suggestions; the answer ends with how to choose

    # ---- wiring
    def watch(self, page):
        def on_req(r):
            rel = self.relevance(r)
            if r.resource_type == "document":
                with contextlib.suppress(Exception):
                    if r.frame is page.main_frame:
                        self.nav_t = time.time()           # the page is on its way to another document (see do_click)
            if TRACE and r.resource_type in ("xhr", "fetch") and (not rel or rel[1] < rel[0]) and site_of(r.url) == site_of(page.url):
                # for the timing trace: the shop's own calls that a wait does not wait for, or only briefly
                self.sidelog[r] = (time.time(), "brief" if rel else "never")
                if len(self.sidelog) > 300:
                    for k in list(self.sidelog)[:100]:
                        self.sidelog.pop(k, None)
            if rel:
                # [start, seconds it may hold up "settled", seconds of that it counts with no loading sign showing,
                #  time from which it counts as answered]
                self.pending[r] = [time.time(), rel[0], rel[1], None]
                self.req_own[r] = site_of(r.url) == site_of(page.url)      # own or another site's, for the page that asked
                self.req_seq += 1
                self.reqlog[r] = [time.time(), None]
                if len(self.reqlog) > 400:
                    for k in list(self.reqlog)[:150]:
                        self.reqlog.pop(k, None)
                self.req_event.set()

        def on_dcl(*_):
            # A new document has loaded. What the document before it still had out is not coming back for this page,
            # and a call that the navigation cut off does not always report failing: left in the table it aged into "a
            # request that hangs", and its address (or, seen from a page of another site, its whole host) was then left
            # out of every later wait. Same-document moves (an app changing its address) do not come through here.
            # Only the site's own calls are dropped: another site's request that hangs goes on being watched, which is
            # how pb learns to leave an ad or tracking host out (busy), and that is judged by the page that asked.
            cut = self.nav_t
            if cut:
                for r in [r for r, e in list(self.pending.items())
                          if e[0] < cut - 0.05 and r.resource_type != "document" and self.req_own.get(r)]:
                    self.pending.pop(r, None)
                    self.sidelog.pop(r, None)
            if len(self.req_own) > 800:
                for k in [k for k in list(self.req_own) if k not in self.pending]:
                    self.req_own.pop(k, None)

        def on_done(r):
            self.pending.pop(r, None)
            self.sidelog.pop(r, None)
            if r in self.reqlog:
                self.reqlog[r][1] = time.time()
            self.req_event.set()

        def on_resp(resp):
            try:
                r = resp.request
                self.sidelog.pop(r, None)
                if resp.status < 400:
                    e = self.pending.get(r)
                    if e is not None and r.resource_type == "fetch":
                        # Chrome reports a fetch as finished only when the page has read its body to the end. A page
                        # that looks at the status alone never does, and the request stayed "pending" for good: it
                        # held this wait and every later one to the cap. So the arrival of the answer ends the wait for
                        # it, after a moment for the body: a short one when the body is known to be small, a longer
                        # one when its length is not known (it may be streaming in).
                        try:
                            size = int(resp.headers.get("content-length", ""))
                        except Exception:
                            size = None
                        grace = 0.05 if resp.status in (204, 205, 304) or size == 0 else 0.3 if size is not None and size <= 300000 else 1.5
                        e[3] = time.time() + grace
                    return
                # The shop refusing a request (hm.com: CONTINUE got a 403 and the page showed nothing) is invisible in
                # the DOM, so it is noted here: the page's own site only, API calls and pages only, trackers left out.
                # An error answer is the whole answer. Chrome never reports some of them finished (a POST answered 403
                # stayed "pending" for good in the fake shop), which held every wait to its cap.
                on_done(r)
                if r.resource_type not in ("xhr", "fetch", "document") or site_of(r.url) != site_of(page.url):
                    return
                short = r.url.split("?")[0]
                if TRACKERS.search(short) or BEACON_PATH.search(short):
                    return
                path = "/" + short.split("://", 1)[-1].partition("/")[2]
                self.http_errs.append((time.time(), f"{r.method} {path[:80]} -> HTTP {resp.status}"))
                del self.http_errs[:-20]
            except Exception:
                pass

        async def on_dialog(d):
            # Accepted unless `pb dialog` said otherwise for this one: a page waits on an open dialog, so it must be
            # answered at once, and the note says what it was and what pb did with it.
            plan, self.dialog_next = self.dialog_next, None
            kind, msg = d.type, re.sub(r"\s+", " ", d.message or "").strip()[:160]
            try:
                if plan and plan[0] == "dismiss":
                    await d.dismiss()
                    did = "dismissed (as pb dialog asked)"
                elif plan and plan[1] is not None and kind == "prompt":
                    await d.accept(plan[1])
                    did = f'answered "{plan[1]}" (as pb dialog asked)'
                else:
                    await d.accept()
                    did = ("accepted" + (f' with its default answer "{d.default_value}"' if kind == "prompt" else "")
                           + (" (as pb dialog asked)" if plan else " (the default; `pb dialog dismiss` before the action cancels it)"
                              if kind in ("confirm", "prompt", "beforeunload") else ""))
            except Exception as e:
                did = "could not be answered: " + str(e).splitlines()[0][:80]
            self.notes.append(f'JS {kind} dialog "{msg}": {did}')

        def on_download(d):
            self.dl_pending.append(asyncio.ensure_future(self.save_download(d, self.cwd)))

        page.on("request", on_req)
        page.on("requestfinished", on_done)
        page.on("requestfailed", on_done)
        page.on("domcontentloaded", on_dcl)
        page.on("response", on_resp)
        page.on("dialog", lambda d: asyncio.ensure_future(on_dialog(d)))
        page.on("download", on_download)

    def caller_dir(self, cwd=None):
        """The caller's working directory, where downloads go and relative paths start."""
        return local_path(".", cwd or self.cwd) if (cwd or self.cwd) else os.getcwd()

    async def save_download(self, d, cwd):
        """A download the page started: saved into the caller's directory under the name the site gave it, never over
        an existing file. The answer of the command that started it says where (see execute)."""
        try:
            path = unique_path(os.path.join(self.caller_dir(cwd), safe_name(d.suggested_filename)))
            await asyncio.wait_for(d.save_as(path), 120)
            size = os.path.getsize(path)
            twin = same_as_earlier(path) if size else None
            path = twin or path
            with contextlib.suppress(Exception):
                with open(path, "rb") as f:
                    if f.read(5) == b"%PDF-":
                        # dailymed's "PDF" link is sent as a download and the tab stays on the label page: pb text reads
                        # this file until the tab goes to another address
                        self.pdf_dl = (path, self.page.url)
            pdf = " (a PDF: the next pb text reads it, as the tab stayed on this page)" if self.pdf_dl and self.pdf_dl[0] == path else ""
            self.dl_lines.append(f"DOWNLOAD the same file is already at {slash(path)} ({size} bytes), so no second copy was saved{pdf}" if twin
                                 else f"DOWNLOAD saved {slash(path)} ({size} bytes){pdf}" if size else f"DOWNLOAD saved {slash(path)}: an EMPTY file (0 bytes)")
        except Exception as e:
            self.dl_lines.append(f"DOWNLOAD of {d.suggested_filename!r} failed: {str(e).splitlines()[0][:160]}")

    async def take_downloads(self, wait=90.0):
        """The DOWNLOAD lines of downloads started so far, once they are saved."""
        live = [t for t in self.dl_pending if not t.done()]
        if live:
            with self.span("downloads"):
                await asyncio.wait(live, timeout=wait)
        self.dl_pending = [t for t in self.dl_pending if not t.done()]
        out, self.dl_lines = self.dl_lines, []
        return out

    def on_page(self, page):
        self.watch(page)
        if self.page is not None and page is not self.page:
            self.page = page
            self.tab_switched = True           # delta() leads with the new tab's URL
            self.tab_at = time.time()

    async def init(self):
        self.ctx.on("page", self.on_page)
        self.page = self.ctx.pages[0] if self.ctx.pages else await self.ctx.new_page()
        for p in self.ctx.pages:
            self.watch(p)

    # ---- the window, and plain-HTTP pages
    async def window_size(self):
        return await self.page.evaluate("[window.outerWidth, window.outerHeight, window.innerWidth, window.innerHeight]")

    async def set_window(self, w, h):
        """Size the browser window (not an emulated viewport: the page sees a real window of that size)."""
        cdp = await self.ctx.new_cdp_session(self.page)
        try:
            win = await cdp.send("Browser.getWindowForTarget")
            if win.get("bounds", {}).get("windowState", "normal") != "normal":
                await cdp.send("Browser.setWindowBounds", {"windowId": win["windowId"], "bounds": {"windowState": "normal"}})
            await cdp.send("Browser.setWindowBounds", {"windowId": win["windowId"], "bounds": {"width": int(w), "height": int(h)}})
        finally:
            with contextlib.suppress(Exception):
                await cdp.detach()
        for _ in range(20):                  # the page learns its new size a moment later
            ow, oh, _iw, _ih = await self.window_size()
            if abs(ow - int(w)) <= 2 and abs(oh - int(h)) <= 2:
                break
            await asyncio.sleep(0.05)

    async def fit_window(self, want=None):
        """A headed Chrome with a new profile opens about 1050 px wide here, under the width where many sites switch to
        their tablet layout (wikipedia folds its search box away, shops fold the menu). Widen it to the default; a
        window that is already wide enough (a profile that remembers its size) is left alone unless a size was asked."""
        if want:
            w, h = want.split("x")
            return await self.set_window(w, h)
        ow, oh, iw, _ih = await self.window_size()
        dw, dh = (int(x) for x in WINDOW_DEFAULT.split("x"))
        if iw < 1200:
            await self.set_window(dw, max(oh, dh) if oh >= 800 else dh)

    async def page_status(self):
        """The HTTP status the server gave for the document that shows now (0 when the browser does not say)."""
        with contextlib.suppress(Exception):
            st = await asyncio.wait_for(self.page.evaluate(
                "() => { const n = performance.getEntriesByType('navigation')[0]; return (n && n.responseStatus) || 0; }"), 2)
            return int(st or 0)
        return 0

    def note_plain_http(self):
        """One NOTE per site for a plain-HTTP page of another machine: Chrome's own warning is off (ensure_prefs)."""
        url = self.page.url
        if plain_http(url, PUBLIC_FOR_TESTS) and host_of(url) not in self.http_said:
            self.http_said.add(host_of(url))
            self.notes.append(f"{host_of(url)} is a plain HTTP site (not encrypted: anyone on the network path can read and change "
                              "what is sent). pb types no card data on such a page; do not enter passwords there either")

    def card_allowed(self, what="the card"):
        """Card data goes to an https page or to this machine only. Raises before anything is typed."""
        url = self.page.url
        if plain_http(url, PUBLIC_FOR_TESTS):
            raise Err(f"{host_of(url)} is a plain HTTP page (not encrypted), so nothing was typed: pb does not put {what} on a page "
                      "that anyone on the network path can read. Use the site's https:// address; if it has none, do not pay there")

    @contextlib.contextmanager
    def span(self, name):
        t = time.time()
        try:
            yield
        finally:
            self.spans.append((name, round(time.time() - t, 3)))

    # ---- waiting for the page
    def relevance(self, r):
        """(a, b) for a request that may hold up "the page has settled": for a seconds at most, and for b seconds of
        that even when no loading sign shows (b < a: a call beside the point, see BACKGROUND). None when it never does."""
        rt = r.resource_type
        if rt not in ("xhr", "fetch", "script", "document"):
            return None
        short = r.url.split("?")[0]
        host = host_of(short)
        if TRACKERS.search(short) or host in self.hung or short in self.hung:
            return None
        own = site_of(r.url) == site_of(self.page.url)
        path = "/" + short.split("://", 1)[-1].partition("/")[2]
        if rt == "document":
            try:
                fr = r.frame
                if fr is self.page.main_frame:
                    return 10.0, 10.0
            except Exception:
                return 10.0, 10.0
            if own:
                return None if REPORT_HOST.search(host) or REPORT_PATH.search(path) else (3.0, 3.0)
            if (PSP_HOSTS.search(host) and "paypal" not in host) or HUMAN_FRAMES.search(short):
                return 3.0, 3.0            # a payment field or a challenge: part of the page for the visitor
            # Any other site's frame loading a page: an ad slot or a sync frame at work when the frame did not show
            # at the last scan (rokt, rlcdn, tapad: one load after another, each of which used to hold the wait 3 s).
            # One that shows, or is new, counts like other requests to another site: in the first burst, and briefly.
            if self.frame_vis.get(fr) is False or time.time() - self.act_t > 2.0 or THIRD_PARTY_REPORT.search(short):
                return None
            return 1.5, 1.5
        if not own:
            # Another site's request counts only as part of the first burst after an action (a search API, an app
            # bundle on a CDN), and briefly. What starts later, or looks like reporting, is an ad tag at work.
            if time.time() - self.act_t > 2.0 or THIRD_PARTY_REPORT.search(short):
                return None
            return (1.0, 1.0) if rt == "script" else (1.5, 1.5)
        if (BEACON_PATH.search(short) or SECONDARY.search(path[1:]) or REPORT_HOST.search(host) or REPORT_PATH.search(path)
                or sensor_path(path)):
            return None
        if rt == "script":
            return 4.0, 4.0
        if BACKGROUND.search(path):
            return 6.0, 1.5
        return 6.0, 6.0

    def busy(self, ld=0):
        """Pending requests that still count. ld: loading signs showing now (a call on a short allowance goes on
        counting while one shows)."""
        now = time.time()
        live = []
        for r, (t, ttl, soft, until) in list(self.pending.items()):
            if until is not None and now >= until:
                self.pending.pop(r, None)          # its answer came a moment ago (see on_resp)
                if r in self.reqlog and self.reqlog[r][1] is None:
                    self.reqlog[r][1] = until
                continue
            age = now - t
            if age < soft or (ld and age < ttl):
                live.append((r, t))
                continue
            if age < ttl:
                continue
            # Learn from requests that never come back: another site's host after 4 s (an ad tag the list above does
            # not know), one of the shop's own URLs after 20 s (a long poll). They stop counting for this session.
            # (Giving one of the shop's own addresses a short allowance as soon as it was slow once was tried and
            # dropped: shops with one address for every call, GraphQL above all, lost the wait for their real answers.)
            if r.resource_type in ("xhr", "fetch"):
                short = r.url.split("?")[0]
                # (own or another site's is what it was for the page that asked: seen from a later page of another
                # site, a shop's own slow call counted as a foreign request that hangs, and its whole host was dropped)
                own = self.req_own.get(r)
                if own is None:
                    own = site_of(short) == site_of(self.page.url)
                if not own:
                    if age >= 4:
                        self.hung.add(host_of(short))
                elif age >= 20:
                    self.hung.add(short)
            if age > 30:
                self.pending.pop(r, None)
        return live

    def own_pending(self, max_age=15.0, ld=0):
        """Requests to the page's own site that have been pending for less than max_age seconds and are still awaited:
        not answered, and not a call beside the point that is past its short allowance (unless a loading sign shows)."""
        now, site = time.time(), site_of(self.page.url)
        out = []
        for r, (t, ttl, soft, until) in list(self.pending.items()):
            age = now - t
            if age >= max_age or (until is not None and now >= until) or (soft < ttl and age >= soft and not ld):
                continue
            if site_of(r.url) == site:
                out.append(r)
        return out

    async def loading(self):
        """Is the page still loading: navigating, its own requests pending, or (on a page that is normally still) its
        DOM changing right now."""
        if self.page.url in ("", "about:blank") and time.time() - self.tab_at < 6:
            return True                # a tab that was just opened and has no address yet: its page is on its way
        p = await self.probe()
        if p is None or p["rs"] == "loading" or (not self.noisy and p["now"] - p["last"] < 600):
            return True
        return bool(self.own_pending(ld=p["ld"]))

    async def finish_loading(self, max_s=6.0):
        """The last answer was written while the page was still loading. Before the next command, let it finish."""
        t0 = time.time()
        with self.span("finish loading"):
            while time.time() - t0 < max_s:
                p = await self.probe()
                if p is not None and not self.own_pending(12.0, p["ld"]) and p["rs"] != "loading" and (self.noisy or p["now"] - p["last"] >= 300):
                    break
                await asyncio.sleep(0.08)
        self.unfinished, self.dirty = False, True

    async def find_target(self, target, purpose, near):
        """resolve(), but when nothing matches while the page is still loading, keep looking until it has loaded.
        Returns (locator, item, known): known = a ref of the last scan, taken as it is. Whether its element is still
        there is seen by the look every action starts with (Session.look), at no cost of its own."""
        is_ref = bool(re.fullmatch(r"e\d+", target))
        if is_ref and target in self.refs:
            return (*self.loc(target), True)       # a known ref needs no scan at all
        # mark() has looked at the page a moment ago: that look serves for "has the page changed since the last scan"
        items, _ = await self.collect(resolve=not is_ref, p=self.base if time.time() - self.act_t < 0.08 else None)
        t0 = time.time()
        while True:
            try:
                return (*await self.resolve(target, items, purpose, near), False)
            except NotFound as e:
                if self.reused:
                    pass                           # the reused scan may be out of date: look again at once
                elif time.time() - t0 > self.patience or (not await self.loading() and not await self.young_try()):
                    waited = time.time() - t0
                    raise NotFound(str(e) + (f" (waited {waited:.0f} s for the page to finish loading)" if waited > 1 else ""))
                else:
                    await asyncio.sleep(0.3)
                self.scan = None
                items, _ = await self.collect()

    async def young_try(self):
        """An optional step (`try click "Close Alert"`) on a page that came up a moment ago: its banner may render a
        moment later (pubmed's alert), so the step keeps looking for its short patience. Other pages: no wait."""
        if self.patience > 1.5:
            return False
        p = await self.probe()
        return p is not None and p["now"] - p["t0"] < 5000

    async def refind(self, target, old, purpose, near):
        """The element behind `old` was replaced by the page. Scan again and return the element that is the same thing:
        for a text target what the text resolves to now, for a ref the one element of the same kind, text and name."""
        self.scan = None
        items, _ = await self.collect()
        if not re.fullmatch(r"e\d+", target):
            return await self.resolve(target, items, purpose, near)
        same = [x for x in items if "ref" in x and all(x.get(k, "") == old.get(k, "") for k in ("k", "t", "name", "fr"))]
        if len(same) == 1:
            return self.loc(same[0]["ref"])
        if not same and old.get("k") in ("input", "select", "combo") and purpose == "fill":
            # a field the page rebuilt as another kind of the same field (wikipedia's search box: an input, then a
            # combobox with the same name, right after the page loaded): the one field with that name, or that label
            fields = [x for x in items if "ref" in x and x["k"] in ("input", "select", "combo") and x.get("fr", "") == old.get("fr", "")]
            for key in ("name", "t", "ph"):
                if old.get(key):
                    hit = [x for x in fields if x.get(key) == old.get(key)]
                    if len(hit) == 1:
                        return self.loc(hit[0]["ref"])
        raise Err(f"{target} is no longer on the page (the page re-rendered it" + (f" and now shows {len(same)} elements like it" if same else "")
                  + "). Take a fresh ref: pb view, or pb find TEXT")

    async def find_any(self, target, purpose="click"):
        """-> (locator, item) for commands that may name what is not a control (scroll, hover, drag, shot, download): an
        element of the scan first, as for click; when none matches, any element that shows that text (a heading, a
        plain box, a draggable card), or an image with that alt text or title."""
        try:
            # --near of the command being run (scroll, hover, upload): see run
            loc, it, _ = await self.find_target(target, purpose, getattr(self, "any_near", None))
            return loc, it
        except NotFound as e:
            if re.fullmatch(r"e\d+", target) or target.startswith("css="):
                raise
            err = e
        loc = await self.text_locator(target)
        if loc is None:
            raise NotFound(f'nothing on the page shows "{target}" (no control, text, image alt or title). Try pb find, pb text "{target}", or css=SELECTOR')
        return loc, {"k": "text", "t": target[:60]}

    async def text_locator(self, text, exact_only=False):
        """The first element that shows `text` (exactly, then as part of its text), or has it as alt text or title.
        exact_only: only an element whose own text is exactly that (pb click on plain text)."""
        fr = self.page.main_frame
        for exact in ((True,) if exact_only else (True, False)):
            for make in ((fr.get_by_text,) if exact_only else (fr.get_by_text, fr.get_by_alt_text, fr.get_by_title)):
                loc = make(text, exact=exact)
                try:
                    n = await asyncio.wait_for(loc.count(), 2)
                    for i in range(min(n, 8)):
                        if await asyncio.wait_for(loc.nth(i).is_visible(), 2):
                            return loc.nth(i)
                except Exception:
                    continue
        return None

    async def probe(self, timeout=1.0):
        """State of the page in one round trip, or None while it is navigating or not answering."""
        try:
            return await asyncio.wait_for(self.page.evaluate(PROBE_JS), timeout)
        except Exception:
            return None

    async def mark(self):
        """Snapshot just before an action, so settle() can tell what the action caused. Also judges, from the idle
        gap since the last command, whether this page keeps changing its DOM by itself."""
        p = await self.probe()
        now = time.time()
        e = self.end
        same = bool(p and e and e[0] and e[0]["t0"] == p["t0"])
        if p and same and now - e[1] >= 1.0:
            win = min(now - e[1], 3.0)
            self.noisy = sum(1 for d in p["rec"] if d * 0.25 < win) / win >= 0.8
        elif not same:
            self.noisy = False
        self.base, self.base_seq, self.act_t = p, self.req_seq, now

    LOADING_CAP = 10.0      # seconds a loading sign the action brought up may hold an answer (see _settle)
    SOFT_WAIT = 12.0        # seconds a browser check that asks nothing of a person gets to pass by itself (collect)
    # the NOTEs that say the page was still loading (dropped once a later step saw what it waited for)
    LOADING_NOTE = re.compile(r"still loading: |the page was still loading when this answer|the page has nothing on it yet")

    async def settle(self, max_s=4.0, quiet=0.3, react=0.4, net=True):
        """Wait until the action's effects are in: no request that matters is pending, the DOM has stopped changing and
        no short animation is running. Returns at once (after `react` seconds) when the action caused nothing.
        net=False watches the DOM only (typing into a plain field: reporting calls it sets off are not worth a wait)."""
        t0 = time.time()
        if self.base is None:
            self.act_t = t0 - 0.5          # no snapshot before the action: a navigation that has just committed
        with self.span("settle"):
            why = await self._settle(max_s, quiet, react, net)
        self.spans.append(("settled: " + why, 0))
        self.dirty = True
        if TRACE:
            # The shop's own calls that began with this action, were still unanswered when the wait ended and did not
            # hold it (or only for their short allowance). If an answer came too early, the call it needed is here.
            left = [f"{kind} {r.url.split('?')[0][-44:]}" for r, (t, kind) in list(self.sidelog.items()) if t >= self.act_t - 0.1]
            if left:
                self.spans.append(("left out: " + " ; ".join(left[:8]) + (f" ; +{len(left) - 8} more" if len(left) > 8 else ""), 0))
        if time.time() - t0 > 1.2 and TRACE:
            # which requests ran during a long wait, as start..end offsets in seconds (end "+" = still pending)
            reqs = sorted((a - t0, (b - t0) if b else None, r.url.split("?")[0][-34:]) for r, (a, b) in list(self.reqlog.items()) if (b or 1e18) > t0)
            self.spans.append(("trace: " + " ; ".join(f"{a:.1f}..{'+' if b is None else format(b, '.1f')} {u}" for a, b, u in reqs[-28:])
                               + " | dom: " + " ".join(self.domlog), 0))
        return why

    async def _settle(self, max_s, quiet, react, net=True):
        t0 = time.time()
        base, seq0 = self.base, self.base_seq
        self.base = None
        anim0 = base["anim"] if base else 0
        doc = base["t0"] if base else None
        reacted, why, net_quiet_since, p = False, "", t0, None
        deadline, t_cap, moves = t0 + max_s, t0, 0
        self.domlog, last_n, live = [], None, []
        # Loading signs the action brought up (see PROBE_JS ldn): one that was showing before the action holds nothing
        base_ld = {x["k"] for x in (base.get("ldn") or [])} if base else set()
        held, ld_said = False, False
        try:
            while True:
                if reacted and live and p is not None and p["now"] - p["last"] > 400 and p["anim"] <= anim0:
                    # Only requests are awaited and the page is still: the next look comes when one of them starts,
                    # ends or runs out of its allowance, or after a moment. A look every 40 ms is work for the page too
                    # (16 ms each on a large page), and waits for a slow answer are the long ones.
                    nap = min([0.12] + [max(0.02, e[3] - time.time()) for e in list(self.pending.values()) if e[3]])
                    self.req_event.clear()
                    with contextlib.suppress(asyncio.TimeoutError):
                        await asyncio.wait_for(self.req_event.wait(), nap)
                else:
                    await asyncio.sleep(0.04)
                p = await self.probe(0.8)
                now = time.time()
                if p is not None and (p["n"], p["ld"]) != last_n:          # trace: when the DOM changed, and loading indicators
                    last_n = (p["n"], p["ld"])
                    self.domlog.append(f"{now - t0:.1f}s:n{p['n']}/ld{p['ld']}")
                    del self.domlog[:-40]
                # read after the probe: request events arrive while it is awaited
                live = self.busy(p["ld"] if p else 0) if net else []
                if p is not None and p["t0"] != doc:
                    doc, self.noisy, anim0 = p["t0"], False, 0        # a new document: nothing is known about it yet
                    if base is not None and moves < 2:
                        # The action led to another page and that page begins only now: its time to settle counts
                        # from here. (A click no longer waits for the page it leads to, see do_click; without this
                        # the seconds a slow server takes to answer would come off the new page's time.)
                        moves += 1
                        t_cap, deadline = now, max(deadline, now + max_s)
                if live or p is None:
                    net_quiet_since = None
                elif net_quiet_since is None:
                    net_quiet_since = now
                # A loading message or loader the action made appear, on the same page, holds the answer while it shows
                # (results that come from a timer with no request pending), up to LOADING_CAP seconds; then a NOTE.
                ind = ([x for x in (p.get("ldn") or []) if x["k"] not in base_ld]
                       if base is not None and p is not None and p["t0"] == base["t0"] and p["href"] == base["href"] else [])
                held = bool(ind) and now - t0 < self.LOADING_CAP
                if held and net_quiet_since is not None:
                    net_quiet_since = now          # calm is counted from when the sign went away
                if ind and not reacted:
                    reacted, why = True, "loading sign"
                if ind and not held and not ld_said:
                    ld_said = True
                    d = ind[0]["d"]
                    word = re.match(r"[\w' ]*\w", d) if ind[0].get("tx") else None
                    self.notes.append(f'still loading: the page shows "{d}"' if ind[0].get("tx") else f"still loading: the page shows a loading sign ({d})")
                    self.notes[-1] += (f' (pb wait --gone "{word.group(0)}" or pb wait "TEXT YOU EXPECT")' if word else ' (pb wait "TEXT YOU EXPECT")')
                if not reacted:
                    if net and self.req_seq != seq0:
                        reacted, why = True, "request"
                        if net_quiet_since is not None:
                            net_quiet_since = now      # it may already be answered: the quiet time counts from here
                    elif p is None:
                        reacted, why = True, "navigation"
                    elif base is None or p["t0"] != base["t0"] or p["href"] != base["href"]:
                        reacted, why = True, "new page"
                    elif p["anim"] > anim0:
                        reacted, why = True, "animation"
                    elif not self.noisy and p["n"] != base["n"]:
                        reacted, why = True, "dom"
                    elif now - t0 >= react:
                        return "no reaction"
                if reacted and p is not None and net_quiet_since is not None and p["rs"] != "loading" and not held:
                    net_calm = now - net_quiet_since
                    anim_calm = p["anim"] <= anim0 or now - t0 > 1.5
                    if self.noisy:
                        if net_calm >= quiet and now - t0 >= react and anim_calm:
                            return why + " (noisy page)"
                    elif net_calm >= 0.15 and anim_calm and p["now"] - p["last"] >= quiet * 1000:
                        return why
                    elif net_calm >= 1.0 and anim_calm:
                        self.noisy = True          # network long quiet, DOM still churning: it does that by itself
                        return why + " (page keeps changing by itself)"
                if now >= deadline and held:
                    deadline = now + 0.25
                    continue
                if now >= deadline:
                    # The cap is for pages that never go quiet. While the site's own requests are pending and either a
                    # spinner is showing or the action led to another page (or the page asked for is still on its way),
                    # it is plainly still loading: keep waiting (half a second at a time, so the usual "quiet now" test
                    # gets its chance once the answers are in), because an answer that lists half a page costs the
                    # caller a whole extra turn.
                    own = self.own_pending(ld=p["ld"] if p else 0)
                    moved = base is None or (p is not None and (p["t0"] != base["t0"] or p["href"] != base["href"]))
                    # on its way to another page: the request for that page went out during this wait and is not answered yet
                    leaving = self.navigating(self.act_t) and any(r.resource_type == "document" for r, _ in live)
                    # (while it is leaving, the old page may stop answering: that is no reason to give up on the new one)
                    if (own or leaving) and (p is not None or leaving) and now - t_cap < max_s + (6 if p and p["ld"] > 0 else 3 if moved or leaving else 0):
                        deadline = now + 0.5
                        continue
                    if own:
                        self.unfinished = True
                        self.notes.append("the page was still loading when this answer was written (its own requests are pending): "
                                          "more may appear. pb view shows the finished page; a command that names its target waits for it")
                    held = [f"{r.resource_type} {host_of(r.url)}{r.url.split('?')[0][-40:]} age={now - t:.1f}" for r, t in live]
                    return "cap, held by: " + (" ; ".join(held[:6]) or ("dom" if p else "no answer from the page"))
        finally:
            self.end = (p, time.time())

    # ---- liveness
    async def ping(self, timeout=12.0):
        """True when the page's main thread answers. A page stuck in a script loop never does."""
        t0 = time.time()
        try:
            while True:
                left = timeout - (time.time() - t0)
                if left <= 0:
                    return False
                try:
                    await asyncio.wait_for(self.page.evaluate("() => 1"), left)
                    return True
                except asyncio.TimeoutError:
                    return False
                except Exception:
                    await asyncio.sleep(0.1)       # mid-navigation: the old context is gone, ask the new one
        finally:
            if time.time() - t0 > 0.2:             # a page that takes its time to answer: worth a line in the timing log
                self.spans.append(("ping", round(time.time() - t0, 3)))

    async def recover(self):
        """Replace a frozen tab: open the same URL in a new tab and drop the old one."""
        old, url = self.page, self.page.url
        new = await self.ctx.new_page()
        self.page = new
        self.pending.clear()
        self.base, self.scan = None, None
        await new.goto(url, wait_until="domcontentloaded", timeout=45000)
        asyncio.ensure_future(self._close_quietly(old))
        await self.settle(max_s=5)
        return url

    @staticmethod
    async def _close_quietly(page):
        with contextlib.suppress(Exception):
            await asyncio.wait_for(page.close(), 8)

    # ---- observation
    FROZEN = ("the page stopped responding (a script on it is spinning). Run `pb recover` to reopen it in a new tab; "
              "form fields typed so far may be lost. Avoid repeating the action that froze it (use the keyboard instead of a click)")

    async def collect(self, resolve=False, p=None):
        """(items, meta) of the current page. Rescans only when the page can have changed since the last scan: full
        reuse needs no action, no DOM mutation and no input event since then; resolve=True (finding a target by its
        text) only needs an unchanged DOM, because stale field values do not matter for that.
        p: a probe of the page taken this very moment, when the caller has one (it saves the round trip for another)."""
        for _ in range(4):
            if p is not None:
                break
            p = await self.probe(1.0)
            if p is None:
                await asyncio.sleep(0.15)
        if p is None and not await self.ping():
            raise Err(self.FROZEN)
        sc = self.scan
        self.reused = bool(p and sc and sc["page"] is self.page and sc["t0"] == p["t0"] and sc["href"] == p["href"] and sc["n"] == p["n"]
                           and sc["frames"] == len(self.page.frames) and (resolve or (not self.dirty and sc["ev"] == p["ev"])))
        if self.reused:
            self.refs = sc["refs"]
            return sc["items"], sc["meta"]
        with self.span("collect"):
            items, meta = await self._collect()
        key = self.page.url                    # (the whole address: the same page with another query is another check)
        if self.soft_waited != key and self.flag_human(items, meta, soft_only=True) == "soft":
            # a browser check with nothing for a person to do: give it its few seconds (pubmed's reCAPTCHA interstitial
            # cleared by itself in 3 of 5 runs, after pb had called it a human check and the driver had given up)
            self.soft_waited, t0, title0 = key, time.time(), meta.get("title") or ""
            with self.span("browser check"):
                while time.time() - t0 < self.SOFT_WAIT:
                    await asyncio.sleep(0.5)
                    with contextlib.suppress(Exception):
                        items, meta = await self._collect()
                        if self.flag_human(items, meta, soft_only=True) != "soft":
                            break
            # passed: no challenge text, no challenge frame, no challenge box left (pubmed: its image grid rendered a
            # moment after the interstitial and the answer said "passed by itself" above a HUMAN CHECK)
            if self.flag_human(items, meta, soft_only=True) is None and not any(CAPTCHA_ANY.search(u) for u in meta.get("frames", [])):
                self.notes.append(f'a browser check ("{title0[:60]}") passed by itself in {time.time() - t0:.0f} s')
            p = await self.probe(1.0) or p
        self.flag_human(items, meta)
        self.scan = {"page": self.page, "t0": p["t0"], "href": p["href"], "n": p["n"], "ev": p["ev"], "frames": len(self.page.frames),
                     "items": items, "meta": meta, "refs": self.refs} if p else None
        self.dirty = False
        self.end = (p, time.time())
        return items, meta

    def flag_human(self, items, meta, soft_only=False):
        """Say so, once per page, when the page is a human check or a refusal: callers otherwise keep poking at it.
        soft_only: only tell whether the page is a browser check that may pass by itself ("soft"), say nothing.
        Returns "hard", "soft" or None."""
        sparse = sum(1 for it in items if "ref" in it) < 30
        # A challenge frame is a block only when it covers a real part of the window, sits in a dialog, or the page
        # behind it is nearly empty. A small widget on an ordinary form (acehardware's Cloudflare box) and a captcha
        # frame that is loaded but not shown (autozone, petco) are not: calling them blocks made drivers give up.
        bare = sum(1 for it in items if "ref" in it and not it.get("fr")) <= 6
        def blocking(url):
            g = self.frame_geo(meta, url)
            return bare or (g is not None and (g["cover"] >= 0.3 or g["dlg"]))

        big = {host_of(u) for u in meta.get("frames", []) if blocking(u)}
        in_frames = " ".join(it.get("t", "") for it in items if it.get("fr") in big)[:2000]
        page_text = " ".join((meta.get("text") or [])[:60])[:3000]
        m = HUMAN_RX.search(in_frames) or (HUMAN_RX.search(page_text) if sparse else None)
        if not m:
            # a check inside a page that keeps its full header (amazon's /checkpoint: "We're noticing unusual browser
            # activity" and an "I am human" box under the search bar, 100 refs): its box or heading says it
            m = next((x for x in (HUMAN_RX.search(it.get("t", "")) for it in items
                                  if it["k"] in ("checkbox", "h") and it.get("reg") != "chrome" and not it.get("fr")
                                  and len(it.get("t", "")) < 120) if x), None)
        fr = next((u for u in meta.get("frames", []) if HUMAN_FRAMES.search(u) and blocking(u)), None)
        key = self.page.url.split("?")[0]
        if not m and not fr and not meta.get("hc"):
            if self.human_flag == key and not soft_only:
                self.human_flag = None             # the check this address showed is gone (it passed by itself)
            return None
        # A browser check that only says so ("Checking your browser", "Just a moment...") and shows nothing a person
        # must do (no image grid, checkbox, press-and-hold box) often passes by itself in a few seconds (pubmed's
        # reCAPTCHA interstitial, Cloudflare's): collect waits for it before calling it a human check (soft).
        widget = fr or meta.get("hc") or (m and m.string is in_frames) or any(
            it.get("k") == "checkbox" and HUMAN_RX.search(it.get("t", "")) for it in items)
        soft = not widget and m is not None and SOFT_CHECK_RX.search(m.group(0) + " " + page_text[:400] + " " + (meta.get("title") or ""))
        if soft_only:
            return "soft" if soft else "hard"
        if key == self.human_flag:
            return "hard"
        self.human_flag = key
        what = f'"{m.group(0)}"' if m else ("a challenge frame from " + host_of(fr)) if fr else f"a challenge box in the page ({meta['hc']})"
        self.human_text = f"HUMAN CHECK or block page ({what}): pb cannot get past it"
        self.notes = [n for n in self.notes if "passed by itself" not in n]     # never both in one answer
        self.notes.append(f"HUMAN CHECK or block page ({what}). pb cannot get past it: stop and report it, or leave the browser open for a person to solve it")
        return "hard"

    @staticmethod
    def frame_geo(meta, url):
        """{cover, dlg} of the frame element that holds the frame now at `url` (from the main frame's scan), or None
        when unknown (a frame that does not show, or one nested in another frame)."""
        u = (url or "").split("#")[0]
        if not u:
            return None
        for g in meta.get("fgeo") or []:
            if g["src"].split("#")[0] == u:
                return g
        return None

    FRAME_MIN = 8          # a frame element smaller than this in either direction holds nothing a person can use
    # the frame element that carries a stamp, in the document or in one of its open shadow roots
    FRAME_EL_JS = """(id) => { const sel = '[data-pbf="' + id + '"]';
        const find = (root) => { const e = root.querySelector(sel); if (e) return e;
          for (const el of root.querySelectorAll('*')) if (el.shadowRoot) { const r = find(el.shadowRoot); if (r) return r; }
          return null; };
        return find(document); }"""

    def frame_matters(self, fr):
        """A frame worth a question of its own when no scan can see its element: the shop's own, a payment frame or a
        challenge."""
        u = fr.url.split("?")[0]
        return site_of(u) == site_of(self.page.url) or bool(PSP_HOSTS.search(host_of(u))) or bool(HUMAN_FRAMES.search(u))

    async def shown_children(self, parent, infos):
        """The child frames of `parent` that show, as (frame, info), judged by what the parent document says about its
        frame elements (infos, see FRAMEINFO_JS). Chrome is asked which frame an element holds once per element; the
        answer is kept under the element's stamp. Frames behind hidden elements are never asked anything: on pages with
        dozens of ad slots those questions were most of the time a scan took."""
        kids = [c for c in parent.child_frames if not c.is_detached()]
        if not kids:
            return []
        # ad slots are left out (FRAMEINFO_JS marks them): their [cbb] and "Why this ad?" controls filled views and diffs
        vis = [f for f in infos if f.get("vis") and not f.get("ad") and f.get("w", 0) >= self.FRAME_MIN and f.get("h", 0) >= self.FRAME_MIN]

        async def learn(f):
            # The element is fetched with a plain script in the world the scan ran in. (A locator would have Playwright
            # set up its own script world first, which on a page that has just loaded took longer than the 0.7 s
            # allowed: the product page of the replay shop lost its frames on the first scan.)
            try:
                eh = (await asyncio.wait_for(parent.evaluate_handle(self.FRAME_EL_JS, f["id"]), 1.0)).as_element()
                fr = await asyncio.wait_for(eh.content_frame(), 0.7) if eh is not None else None
            except Exception:
                fr = None
            if fr is not None:
                self.fmap[f["id"]] = fr

        new = [f for f in vis if f["id"] not in self.fmap or self.fmap[f["id"]].is_detached()]
        if new:
            t = time.time()
            await asyncio.gather(*(learn(f) for f in new))
            if time.time() - t > 0.3:
                self.spans.append((f"slow frame lookup ({len(new)} new) {time.time() - t:.2f}s", 0))
        if len(kids) > len(infos):
            # More frames than frame elements: one sits where the scan cannot look (a closed shadow root), or was added
            # this very moment. The ones that matter are asked the long way round, once each.
            known, now = set(self.fmap.values()), time.time()

            async def ask(c):
                self.fasked[c] = now               # one that does not answer is not asked again for a while
                try:
                    fe = await asyncio.wait_for(c.frame_element(), 0.7)
                    sid = await asyncio.wait_for(fe.get_attribute("data-pbf"), 0.7)
                except Exception:
                    return
                if sid:
                    self.fmap[sid] = c
                else:
                    self.fclosed[c] = fe

            await asyncio.gather(*(ask(c) for c in kids if c not in known and c not in self.fclosed and self.frame_matters(c)
                                   and now - self.fasked.get(c, 0) > 5))
        out, shown = [], set()
        for f in vis:
            fr = self.fmap.get(f["id"])
            if fr is not None and not fr.is_detached() and fr not in shown:
                shown.add(fr)
                if fr.url and not TRACKERS.search(fr.url.split("?")[0]):
                    out.append((fr, f))
        for c in kids:
            fe = self.fclosed.get(c)
            if fe is not None and c not in shown:
                ok = False
                with contextlib.suppress(Exception):
                    ok = await asyncio.wait_for(fe.is_visible(), 0.7)
                if ok:
                    shown.add(c)
                    out.append((c, None))
        for c in kids:
            self.frame_vis[c] = c in shown          # relevance() ignores page loads in frames that do not show
        if len(self.frame_vis) > 400:
            for d in (self.frame_vis, self.fclosed, self.fasked):
                for c in [c for c in d if c.is_detached()]:
                    del d[c]
            for k in [k for k, c in self.fmap.items() if c.is_detached()]:
                del self.fmap[k]
        return out

    async def visible_frames(self):
        """Sub-frames worth looking into: attached, not an ad or tracker, and showing, as is every frame around them.
        Each document that holds frames is asked once about its frame elements (see shown_children)."""
        out, level, depth = [], [self.page.main_frame], 0

        async def infos(fr):
            try:
                return json.loads(await asyncio.wait_for(fr.evaluate(FRAMES_JS), 1.5))
            except Exception:
                return []

        while level and depth < 5:
            level = [fr for fr in level if any(not c.is_detached() for c in fr.child_frames)]
            lists = await asyncio.gather(*(infos(fr) for fr in level))
            found = await asyncio.gather(*(self.shown_children(fr, inf) for fr, inf in zip(level, lists)))
            level = [c for kids in found for c, _ in kids]
            out += level
            depth += 1
        return out

    async def _collect(self):
        """Interactive elements of every frame that shows, plus the main frame's visible text lines. The main frame is
        scanned first, because its scan says which of its frame elements show; those frames are scanned at the same
        time, then the frames inside them. Ad and tracker frames are skipped."""
        page = self.page
        items, meta = [], {"url": page.url, "title": "", "text": []}
        self.refs = {}

        async def one(fr, start, main):
            try:
                res = await asyncio.wait_for(fr.evaluate(COLLECT_JS, {"next": start, "text": main}), 4 if main else 1.5)
                # the scan answers with one string: a tree of values costs 1 ms per kilobyte to cross from the page
                return json.loads(res) if isinstance(res, str) else res
            except Exception:
                return None

        t0 = time.time()
        res = await one(page.main_frame, self.next_ref, True)
        if res is None:
            if not await self.ping():
                raise Err(self.FROZEN)
            t0 = time.time()
            res = await one(page.main_frame, self.next_ref, True)      # it was mid-navigation
        t_main = time.time() - t0
        results, subs, geo = [], [], {}
        if res:
            self.next_ref = res["next"]
            results.append((page.main_frame, res))
        level, depth = list(results), 0
        while level and depth < 5:
            found = [x for kids in await asyncio.gather(*(self.shown_children(fr, r.get("frames") or []) for fr, r in level)) for x in kids]
            if not found:
                break
            base = self.next_ref
            scans = await asyncio.gather(*(one(fr, base + i * 300, False) for i, (fr, _) in enumerate(found)))
            level = []
            for i, ((fr, info), r) in enumerate(zip(found, scans)):
                subs.append(fr)
                if depth == 0 and info:
                    geo[fr] = info
                if r:
                    results.append((fr, r))
                    level.append((fr, r))
                    if r["next"] > base + i * 300:       # this frame took new ref numbers from its own block
                        self.next_ref = max(self.next_ref, r["next"])
            depth += 1
        meta["frames"] = [fr.url for fr in subs]
        # where each frame of the main document sits (see flag_human), under the address the frame has now
        meta["fgeo"] = [{"src": fr.url, "cover": g["cover"], "dlg": g["dlg"]} for fr, g in geo.items()]
        for fr, r in results:
            main = fr is page.main_frame
            if main:
                meta["title"], meta["text"] = r["title"], r.get("text") or []
                meta["hc"] = r.get("hc") or ""
                note = f"scan js {r.get('ms', 0)} ms, {len(r['items'])} items, {len(subs)} subframes"
                if TRACE and r.get("prof"):
                    w, d, t, f = r["prof"]
                    note += f" (walk {w}, dialogs {d}, text {t}, frames and refs {f}; round trip {t_main * 1000:.0f} ms)"
                self.spans.append((note, 0))
            host = "" if main else host_of(fr.url)
            g = geo.get(fr)
            for it in r["items"]:
                it["fr"] = host
                if g and g["dlg"]:
                    it["reg"] = "dialog"           # a frame inside a dialog (a captcha in a modal): its controls are the dialog's
                items.append(it)
                if "ref" in it:
                    self.refs[it["ref"]] = (fr, it)
                    self.ref_hist[it["ref"]] = (it["k"], it.get("t", ""), it.get("name", ""), it.get("fr", ""))
        if len(self.ref_hist) > 8000:               # keep what the last few thousand refs were, not everything ever seen
            for k in list(self.ref_hist)[:3000]:
                del self.ref_hist[k]
        return items, meta

    @staticmethod
    def line(it):
        k = it["k"]
        if k == "h":
            return "# " + it["t"]
        if k == "!":
            return "! " + it["t"]
        if k == "run":
            return Session.run_line(it)
        s = f'{it["ref"]} '
        if k == "input":
            s += f'input[{it.get("it", "text")}] "{it.get("t", "")}"'
            if it.get("name"):
                s += f' {"id" if it.get("nid") else "name"}={it["name"]}'
            s += f' shows "{it["shows"]}"' if it.get("shows") and not it.get("v") else f' ="{it.get("v", "")}"'
        elif k == "select":
            s += f'select "{it.get("t", "")}" ="{it.get("v", "")}"'
            s += " options: " + " | ".join(it["opts"]) if it.get("opts") else f' ({it.get("n", 0)} options)'
        elif k in ("checkbox", "radio"):
            s += f'{k} "{it.get("t", "")}" ' + ("[x]" if it.get("on") else "[ ]")
        else:
            s += f'{k} "{it.get("t", "")}"'
            if it.get("al"):
                s += f' aria="{it["al"]}"'
            if it.get("on") is True:
                s += " [on]"
            if it.get("exp") is True:
                s += " [expanded]"
            if it.get("rep"):
                s += f' x{it["rep"]}'          # the same link again right after (same address and text): one line
        if it.get("ro"):
            s += " (read-only)"
        elif it.get("dis"):
            s += " (disabled)"
        if it.get("inv"):
            s += " (invalid)"
        if it.get("req") and not it.get("v"):
            s += " (required)"
        return s

    @staticmethod
    def sig(it):
        return (it.get("fr", ""), it["k"], it.get("t", ""), it.get("name", ""), it.get("v", ""), it.get("on"), it.get("dis"), it.get("exp"))

    # Runs of sibling controls that differ only by a number or a short token: calendar days (booking, Google Flights,
    # airbnb: about 200 day buttons), line-number links (github: 130), pages, star ratings, sizes. One line each.
    RUN_KINDS = ("button", "link", "click", "option", "radio", "checkbox", "tab", "menuitem")
    RUN_LEAST = 6
    ADDED_MAX = 25                 # lines of new elements an answer after an action lists
    NAV_MAX = 25                   # lines of the new page an answer lists after a click, back or forward led to it
    # A long article (en.wikipedia.org: 260 to 1200 refs): past PROSE_MAX links inside running text, the first
    # PROSE_KEEP are listed and the rest counted.
    PROSE_MAX, PROSE_KEEP = 40, 10
    # Lines under a heading that matched --grep (theguardian: which section a story is in)
    GREP_UNDER = 8

    @staticmethod
    def run_key(it):
        t = it.get("t", "")
        tpl = re.sub(r"\d+(?:[.,]\d+)?", "#", t)
        if "#" not in tpl:
            if not t or len(t) > 4:
                return None
            tpl = "~"                              # a short token (a size: XS, S, M ...)
        return (it["k"], it.get("fr", ""), it.get("reg", ""), tpl)

    def fold_runs(self, items):
        """items with each run of at least RUN_LEAST neighbours of one kind, whose texts differ only by a number or a
        short token, replaced by one item of kind "run" (see run_line)."""
        out, i, n = [], 0, len(items)
        while i < n:
            it = items[i]
            key = self.run_key(it) if it["k"] in self.RUN_KINDS and it.get("ref") else None
            j = i + 1
            if key:
                num = lambda x: int(m.group()) if (m := re.search(r"\d+", x.get("t", ""))) else None
                while j < n and items[j]["k"] in self.RUN_KINDS and items[j].get("ref") and self.run_key(items[j]) == key:
                    a, b = num(items[j - 1]), num(items[j])
                    if a is not None and b is not None and b < a:
                        break                      # the numbers start again: the next month of a calendar
                    j += 1
            run = items[i:j]
            if key and len(run) >= self.RUN_LEAST and len({x.get("t", "") for x in run}) > 1:
                r = {"k": "run", "kind": it["k"], "members": run, "fr": it.get("fr", ""), "reg": it.get("reg", ""),
                     "sec": it.get("sec", ""), "t": it.get("t", "")}
                # days that carry their full date (airbnb "15, Friday, January 2027"): the run is named by that month,
                # and one day is clicked by its date text
                # (the cell's date label counts as the day's own: Google Flights and amtrak keep it on the cell)
                lab = lambda x: x.get("dl") or x.get("al", "")
                months = {f"{m.group(1).title()} {m.group(2)}" for x in run if (m := self.MONTH_RX.search(lab(x)))}
                if len(months) == 1:
                    r["sec"] = months.pop()
                    d = re.match(r"^(.*?\b(?:19|20)\d\d)\b", lab(run[len(run) // 2]))
                    if d:
                        r["date"] = d.group(1)
                elif re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", lab(run[len(run) // 2]), re.I):
                    # labels with a month and no year (opentable: "Friday, January 15"): one real label is the example,
                    # in the form the page uses (a made-up "15, Friday, January 2027" matched nothing there)
                    r["date"] = lab(run[len(run) // 2])[:60]
                out.append(r)
                i = j
            else:
                out.append(it)
                i += 1
        # Two month grids whose headings both come first (airbnb): the runs that follow one another under the same
        # heading take the last headings before them, in order, when there are as many distinct ones.
        k = 0
        while k < len(out):
            if out[k]["k"] != "run" or out[k].get("date"):
                k += 1
                continue
            g = k
            while g + 1 < len(out) and out[g + 1]["k"] == "run" and out[g + 1].get("sec") == out[k].get("sec") and not out[g + 1].get("date"):
                g += 1
            if g > k:
                heads, b = [], k - 1
                while b >= 0 and out[b]["k"] != "run":
                    if out[b]["k"] == "h":
                        heads.insert(0, out[b]["t"])
                    b -= 1
                heads = heads[-(g - k + 1):]
                if len(heads) == g - k + 1 and len(set(heads)) == len(heads):
                    for x, h in zip(out[k:g + 1], heads):
                        x["sec"], x["paired"] = h, True
            k = g + 1
        return out

    MONTH_RX = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b,?\s+(?:\d{1,2},?\s+)?((?:19|20)\d\d)\b", re.I)

    @staticmethod
    def run_line(r):
        m = r["members"]
        refs = [x["ref"] for x in m]
        nums = [int(x[1:]) if x[1:].isdigit() else -1 for x in refs]
        kind = {"click": "clickable"}.get(r["kind"], r["kind"]) + "s"
        s = f'{refs[0]}..{refs[-1]} {len(m)} {kind} "{m[0].get("t", "")}".."{m[-1].get("t", "")}"'
        if r.get("sec"):
            s += f' under "{r["sec"]}"'
        extra = []
        if m[0].get("al"):
            extra.append(f'first aria="{m[0]["al"]}"')
        dis = sum(1 for x in m if x.get("dis"))
        if dis:
            extra.append(f"{dis} disabled")
        on = [x.get("t", "") for x in m if x.get("on") is True]
        if on:
            extra.append("on: " + ", ".join(f'"{x}"' for x in on[:3]))
        if nums != list(range(nums[0], nums[0] + len(nums))):
            extra.append("refs " + " ".join(refs))         # not numbered one after the other: each ref is needed
        if extra:
            s += " (" + "; ".join(extra) + ")"
        mid = m[len(m) // 2].get("t", "")
        if r.get("date"):
            return s + f'. Pick one by its date: pb click "{r["date"]}", or its ref'
        if r.get("paired"):
            # both headings sit above both grids, so --near cannot tell them apart
            return s + ". Pick one by its ref (in day order)"
        return s + (f'. Pick one: pb click "{mid}" --near "{r["sec"]}", or its ref' if r.get("sec") else f'. Pick one: pb click "{mid}", or its ref')

    @staticmethod
    def echoes(h, prev):
        """A card's heading that repeats the link printed just before it (theguardian: a link over the card, then the
        card's heading with the same words, kicker first)."""
        if prev is None or prev["k"] in ("h", "!", "run"):
            return False
        a, b = fold(prev.get("t", "")).rstrip(ELLIPSIS).strip(), fold(h["t"]).rstrip(ELLIPSIS).strip()
        if len(b) < 25 or len(a) < 20:
            return False
        return a[:40] in b or b[:40] in a

    def render(self, items, show_all=False, grep=None, cap=MAX_LINES, limit=None):
        """Compact view. Dialog first, controls always, links capped, nav/footer links hidden, repeats collapsed, runs
        of numbered neighbours folded into one line, the links in a long article's text counted. grep: the lines that
        match, a few lines under a heading that matches, and the section lines of what is shown. limit: at most that
        many lines of elements, then one line with the count of the rest."""
        groups = {}
        for it in items:
            if it["k"] in ("button", "link", "click"):
                groups.setdefault((it["fr"], it["k"], it.get("t", "")), []).append(it)
        prose = 0 if show_all else sum(1 for it in items if it.get("pr"))
        prose_seen, hidden_prose, more = 0, 0, 0
        items = self.fold_runs(items)
        out, hidden_chrome, hidden_cap, used = [], 0, 0, 0
        has_dialog = any(it.get("reg") == "dialog" for it in items)
        order = ([it for it in items if it.get("reg") == "dialog"] if has_dialog else [])
        rest = [it for it in items if it.get("reg") != "dialog"]
        # a section line is printed with the first line under it; without --grep there is always one
        section = "DIALOG open:" if has_dialog else None
        if section and not grep:
            out.append(section)
            section = None
        seen_groups, cur_frame, pending_h, prev = set(), "", None, None
        under, under_n = None, 0
        first_rest = True
        for it in order + rest:
            if has_dialog and first_rest and it.get("reg") != "dialog":
                section = "PAGE behind dialog:"        # printed with its first line (none: nothing new behind it)
                first_rest = False
            k = it["k"]
            if k == "h":
                pending_h = it
                if grep:
                    under, under_n = (it if grep.search("# " + it["t"]) else None), 0
                    if under is not None:
                        # a heading --grep asks for is a line of its own, controls under it or not (pb view --grep '^# '
                        # left out a PMC article's Results and Discussion, which hold only text)
                        if section:
                            out.append(section)
                            section = None
                        if it.get("fr", "") != cur_frame:
                            cur_frame = it.get("fr", "")
                            out.append(f"frame {cur_frame}:" if cur_frame else "main page:")
                        out.append("# " + it["t"])
                        used += 1
                        pending_h = None
                continue
            if k != "!" and not show_all:
                if it.get("reg") == "chrome" and k in ("link", "click") and not ACTION_RX.search(it.get("t", "") + " " + it.get("al", "")):
                    hidden_chrome += 1
                    continue
                if (limit is not None and it.get("reg") == "chrome" and k not in ("input", "select", "combo")
                        and not ACTION_RX.search(it.get("t", "") + " " + it.get("al", ""))):
                    # a short answer (a new page after a click): the header's and footer's buttons and menus are not what
                    # changed (pmc: the first 40 lines were the site banner and its menus)
                    hidden_chrome += 1
                    continue
                if it.get("pr") and prose > self.PROSE_MAX and not ACTION_RX.search(it.get("t", "")):
                    prose_seen += 1
                    if prose_seen > self.PROSE_KEEP:
                        hidden_prose += 1
                        continue
            g = (it["fr"], k, it.get("t", ""))
            n_rep = len(groups.get(g, [])) if k != "run" else 0
            if n_rep >= 3:
                if g in seen_groups:
                    continue
                seen_groups.add(g)
            line = self.line(it)
            if n_rep >= 3:
                line += f' x{n_rep} (also {" ".join(x["ref"] for x in groups[g][1:4])}{" ..." if n_rep > 4 else ""})'
            if grep and not grep.search(line) and not (k == "run" and any(grep.search(self.line(x)) for x in it["members"])):
                if under is None or under_n >= self.GREP_UNDER:
                    continue
                under_n += 1                       # a line under a heading that matched
            if not show_all and used >= cap and k in ("link", "click"):
                hidden_cap += 1
                continue
            if limit is not None and used >= limit:
                more += 1
                continue
            if section:
                out.append(section)
                section = None
            if it.get("fr", "") != cur_frame:
                cur_frame = it.get("fr", "")
                out.append(f"frame {cur_frame}:" if cur_frame else "main page:")
                if pending_h is not None and pending_h.get("fr", "") != cur_frame:
                    pending_h = None
            if pending_h is not None:
                if not self.echoes(pending_h, prev):
                    out.append("# " + pending_h["t"])
                pending_h = None
            out.append(line)
            used += 1
            prev = it
        if grep and not used:
            return [f'(no control matches --grep "{grep.pattern}". Text that is not a control (list items, messages, prices) is '
                    f'searched by pb text "{grep.pattern}"; pb find TEXT looks at every element)']
        if more:
            out.append(f"+{more} more: pb view --grep REGEX, pb find TEXT, pb table")
        if hidden_prose:
            out.append(f"({prose} links in the text, the first {self.PROSE_KEEP} listed: pb links REGEX, pb find TEXT)")
        tail = []
        if hidden_chrome:
            tail.append(f"{hidden_chrome} nav/footer links hidden")
        if hidden_cap:
            tail.append(f"{hidden_cap} more links not shown")
        if tail:
            out.append("(" + "; ".join(tail) + ". Use: pb find TEXT, or pb view --all)")
        return out

    def header(self, meta):
        # (a PDF or JSON address has no title: its file name says what it is)
        title = meta["title"] or (meta["url"].split("?")[0].rstrip("/").rsplit("/", 1)[-1][:120] + " (no title: the file's name)" if meta.get("url") else "")
        h = [f"URL {meta['url']}" + ("   (in a NEW TAB; pb tabs / pb tab N to switch back)" if self.tab_switched else ""), f"TITLE {title[:300]}"]
        self.tab_switched = False
        for n in self.notes:
            h.append("NOTE " + n)
        self.notes = []
        return h

    @staticmethod
    def clip(lines):
        s = "\n".join(lines)
        if len(s) > MAX_CHARS:
            s = s[:MAX_CHARS] + "\n... (truncated; narrow with pb view --grep RE or pb find TEXT)"
        return s + "\n"

    async def view_text(self, show_all=False, grep=None):
        items, meta = await self.collect()
        return self.clip(self.header(meta) + self.render(items, show_all=show_all, grep=grep) + ([] if grep else self.text_if_bare(items, meta)))

    @staticmethod
    def page_lines(items, meta, n=4):
        """The first lines of a new page's own text, after its first main heading: what it says, not its menus. Lines
        that are the names of controls, or the header's and footer's words, are left out."""
        names = {it.get("t", "") for it in items} | {it.get("al", "") for it in items}
        heads = [it for it in items if it["k"] == "h" and it.get("reg") not in ("chrome", "dialog")]
        text = [l for l in (meta.get("text") or []) if l.strip()]
        start = 0
        if heads:
            h0 = heads[0]["t"].rstrip("…")
            start = next((i for i, l in enumerate(text) if l.startswith(h0)), 0)
        out = [f'# {heads[0]["t"]}'] if heads else []
        for l in text[start:start + 40]:
            if l in names or len(l) < 3:
                continue
            out.append(f'text "{l[:160]}"')
            if len(out) >= n:
                break
        return out

    @staticmethod
    def text_if_bare(items, meta):
        """A page with next to no controls (a form's "submitted" page, a message, a component's shadow text): its first
        lines of text, so the view is not just an address and a title."""
        if sum(1 for it in items if "ref" in it) >= 3:
            return []
        lines = [l for l in (meta.get("text") or []) if l.strip()][:10]
        if not lines:
            return []
        return [f'text "{l[:160]}"' for l in lines] + (["(pb text reads all of it)"] if len(meta.get("text") or []) > 10 else [])

    def delta(self, before, meta_b, after, meta_a, status):
        out = list(status)
        nav = meta_a["url"].split("#")[0] != meta_b["url"].split("#")[0]
        old = {}
        for it in before:
            old[self.sig(it)] = old.get(self.sig(it), 0) + 1
        added = []
        # an element that kept its ref and its looks is the same one: matched first, so that a second calendar's "15"
        # is not taken for the first one's (the old grid then read as new and the new one as old)
        bref = {it["ref"]: self.sig(it) for it in before if it.get("ref")}
        same = set()
        for it in after:
            s = self.sig(it)
            if it.get("ref") and bref.get(it["ref"]) == s and old.get(s, 0) > 0:
                old[s] -= 1
                same.add(id(it))
        for it in after:
            if id(it) in same:
                continue
            s = self.sig(it)
            if old.get(s, 0) > 0:
                old[s] -= 1
            elif it["k"] != "h" and not (it["k"] == "!" and self.SR_HINT.search(it.get("t", ""))):
                added.append(it)
        removed = sum(v for v in old.values() if v > 0)
        # plain text that appeared (messages, prices, totals): lines of the page text that were not there before
        new_text = []
        if not nav and meta_b.get("text") is not None:
            have = {}
            for l in meta_b["text"]:
                have[l] = have.get(l, 0) + 1
            labels = {it.get("t", "") for it in added} | {it.get("v", "") for it in added}
            for l in meta_a.get("text") or []:
                if have.get(l, 0) > 0:
                    have[l] -= 1
                elif l not in labels and l not in new_text and not self.SR_HINT.search(l):
                    new_text.append(l)
        tab = self.tab_switched
        self.tab_switched = False
        if nav or tab:
            # Another page (or tab) took over: that is the news, so it comes first (samsung's Add to cart moved to
            # shop.samsung.com, etsy opened the product in a new tab, kroger's cart turned into a sign-in page).
            out = [f"URL -> {meta_a['url']}" + ("   (in a NEW TAB; pb tabs / pb tab N to switch back)" if tab else ""),
                   f"TITLE {meta_a['title'][:300]}"] + out
            wall = self.wall_note(after, meta_a)
            if wall:
                self.notes.append(wall)
        dialog_open = [it for it in after if it.get("reg") == "dialog"]
        if not (nav or tab) and not added and not removed and not new_text and dialog_open:
            head = next((it["t"] for it in dialog_open if it["k"] == "h"), "")
            # (demoqa's "Thanks for submitting" modal: its Close button has no handler at all, and only Escape closes it)
            self.notes.append(f'a dialog is open over the page{(" (" + head + ")") if head else ""}: it may have caught this action. '
                              "Act inside it or close it first (pb view lists it first). If this was its close button and it "
                              "stayed open, the button does nothing on this page: pb press Escape often closes it")
        elif dialog_open and (nav or tab or not any(it.get("reg") == "dialog" for it in before)):
            # the same NOTE for every dialog that comes up after an action (airbnb's "Got it" box after Search had none)
            head = next((it["t"] for it in dialog_open if it["k"] == "h"), "")
            self.notes.append(f'a dialog opened over the page{(" (" + head + ")") if head else ""}: act inside it or close it first')
        for n in self.notes:
            out.append("NOTE " + n)
        self.notes = []
        if nav or tab:
            # another page: its first NAV_MAX lines and a count (after a click on europepmc.org, every answer was the
            # whole results page, 8 KB); pb view prints it all. Its main heading and first lines of text come first
            # (the-internet /upload: "File Uploaded!" and the file's name were missing under a list of links)
            out += self.page_lines(after, meta_a) + self.render(after, limit=self.NAV_MAX)
        elif not added and not removed and not new_text and self.reordered(meta_b, meta_a):
            # the same lines in another order: a table sorted by its header, two boxes that swapped their text
            ta, tb = meta_a.get("text") or [], meta_b.get("text") or []
            i = next((k for k, (x, y) in enumerate(zip(ta, tb)) if x != y), 0)
            out.append("order changed; the lines from the first one that moved:")
            out += [f'  "{l[:120]}"' for l in ta[i:i + 6]]
        elif not added and not removed and not new_text:
            if not self.quiet_same:
                out.append("(no visible change)")
            # a message that was already up may be the reason nothing happened ("Please select a size" from an earlier try)
            for it in [it for it in after if it["k"] == "!" and self.ERRORISH.search(it["t"])][:3]:
                out.append("  still shown: " + self.line(it) + (f"  [frame {it['fr']}]" if it.get("fr") else ""))
        elif len(added) > 45:
            # what is new, as a view (headings for context, dialog first), its first ADDED_MAX lines (sec.gov's "View
            # filings" printed +634 elements, Google Flights' date picker the whole page)
            out.append(f"page changed a lot (+{len(added)} / -{removed} elements), what is new:")
            new = {id(it) for it in added}
            out += self.render([it for it in after if it["k"] == "h" or id(it) in new], limit=self.ADDED_MAX)
        else:
            if any(it.get("reg") == "dialog" for it in added) and not any(it.get("reg") == "dialog" for it in before):
                head = next((it["t"] for it in after if it.get("reg") == "dialog" and it["k"] == "h"), "")
                out.append("DIALOG opened" + (f': "{head}"' if head else ":"))
            # the dialog's own lines first; fields behind it that changed come after, under their own line (demoqa: the
            # form's inputs read as if they were in the summary modal)
            folded = self.fold_runs([it for it in added if it.get("reg") == "dialog"] + [it for it in added if it.get("reg") != "dialog"])
            behind = any(it.get("reg") == "dialog" for it in added)
            opts, more_opts = [it for it in folded if it["k"] == "option"], 0
            if len(opts) > 8:
                # a suggestion list (youtube: 30 suggestions after a plain fill): the first 8, and a count
                drop = {id(it) for it in opts[8:]}
                folded, more_opts = [it for it in folded if id(it) not in drop], len(drop)
            for i_opt, it in enumerate(folded[:self.ADDED_MAX]):
                if more_opts and it["k"] != "option" and i_opt and folded[i_opt - 1]["k"] == "option":
                    out.append(f"+ {more_opts} more suggestions (pb find TEXT, or pb view --grep REGEX)")
                    more_opts = 0
                if behind and it.get("reg") != "dialog":
                    out.append("PAGE behind dialog:")
                    behind = False
                out.append("+ " + self.line(it) + (f"  [frame {it['fr']}]" if it.get("fr") else ""))
            if more_opts:
                out.append(f"+ {more_opts} more suggestions (pb find TEXT, or pb view --grep REGEX)")
            if len(folded) > self.ADDED_MAX:
                out.append(f"+{len(folded) - self.ADDED_MAX} more: pb view --grep REGEX, pb find TEXT, pb table")
            for l in new_text[:8]:
                out.append(f'+ text "{l[:160]}"')
            if len(new_text) > 8:
                out.append(f"+ {len(new_text) - 8} more new text lines (pb text REGEX to read them)")
            if removed:
                was = [it for it in before if it.get("reg") == "dialog"]
                if was and not dialog_open:
                    # linkedin: Escape closed the sign-in modal and the answer said only "11 element(s) removed"
                    head = next((it["t"] for it in was if it["k"] == "h"), "")
                    out.append("dialog closed" + (f': "{head}"' if head else ""))
                out.append(f"- {removed} element(s) removed or changed")
        return self.clip(out)

    # what a suggestion box says to screen readers ("0 results are available, use up and down arrow keys to navigate."):
    # not news after a fill (pubmed printed it under every fill of its search box)
    SR_HINT = re.compile(r"^\d+ (results?|suggestions?) (are |is )?available\b|use (the )?up and down arrow(s| keys)? to", re.I)

    ERRORISH = re.compile(r"error|invalid|required|please|must|unable|sorry|failed|try again|not available|problem|cannot|can.t", re.I)

    def unchanged(self, before, meta_b, after, meta_a):
        """Would delta() say "(no visible change)"?"""
        if meta_b.get("text") is None or meta_a["url"].split("#")[0] != meta_b["url"].split("#")[0] or self.tab_switched:
            return False
        return (sorted(map(repr, map(self.sig, before))) == sorted(map(repr, map(self.sig, after)))
                and sorted(meta_b["text"]) == sorted(meta_a.get("text") or []) and not self.reordered(meta_b, meta_a))

    @staticmethod
    def reordered(meta_b, meta_a):
        """The page shows the same text lines as before, in another order."""
        tb, ta = meta_b.get("text"), meta_a.get("text")
        return tb is not None and ta is not None and tb != ta and sorted(tb) == sorted(ta)

    SIGNIN_RX = re.compile(r"^(sign|log)\s?-?(in|on)\b|^(please )?(sign|log) in to|^welcome back|^(customer )?login$", re.I)
    SIGNIN_URL = re.compile(r"(^|[./-])(login|signin|sign-in|log-in|logon|auth)([./?-]|$)", re.I)

    def wall_note(self, items, meta):
        """A NOTE when the page looks like a sign-in wall: a password field, a "Sign in" heading, a login URL. The wall
        has to cover or replace the content: in a dialog, only one that covers or blocks the page counts (cov, see
        COLLECT_JS; booking.com's "Sign in, save money" box sits beside the results); in the page, a heading counts as
        its first heading or on a page that holds little else."""
        # A password field counts in the page itself or a dialog, and on a page with few other fields: lowes keeps one
        # in its header menu on every page, and a checkout that offers "create an account" has a dozen other fields.
        fields = [it for it in items if it["k"] in ("input", "select") and it.get("reg") != "chrome" and it.get("cov", 1)]
        pw = any(it.get("it") == "password" for it in fields)
        page_items = [it for it in items if it.get("reg") not in ("chrome", "dialog") and it["k"] != "h"]
        first_main = next((it for it in items if it["k"] == "h" and it.get("reg") not in ("chrome", "dialog")), None)

        def walls(it):
            if it["k"] != "h" or not self.SIGNIN_RX.search(it["t"]):
                return False
            if it.get("reg") == "dialog":
                return bool(it.get("cov", 1))
            return it is first_main or len(page_items) <= 40
        why = ("a password field" if pw and len(fields) <= 6
               else next((f'the heading "{it["t"][:40]}"' for it in items if walls(it)), None)
               or ("its address" if self.SIGNIN_URL.search(meta["url"].split("://", 1)[-1].split("?")[0]) else None))
        if not why:
            return None
        return (f"this looks like a sign-in page ({why}): the site wants an account here. Look for a guest option, "
                "or stop and report it")

    async def late_look(self):
        """One short second look after an action that seemed to change nothing: errors such as "Please select a size"
        and redirects often come a moment after the page went quiet (qvc, samsung). Costs 0.35 s, only in that case.
        Returns (items, meta) when something did change, else None."""
        sc = self.scan
        await asyncio.sleep(0.35)
        p = await self.probe(0.8)
        if sc is None or (p is not None and p["t0"] == sc["t0"] and p["href"] == sc["href"] and p["n"] == sc["n"]
                          and len(self.page.frames) == sc["frames"] and sc["page"] is self.page):
            return None
        if p is None or p["t0"] != sc["t0"] or p["href"] != sc["href"] or sc["page"] is not self.page:
            self.base = None                   # on its way to another page: wait for that one
            await self.settle(max_s=5)
        self.scan = None
        return await self.collect()

    async def wait_for_content(self, items, meta, max_s=8.0):
        """advanceautoparts.com: a product link landed on a bare document that loaded the real page a moment later, and
        the answer was written in between: `URL ->`, an empty TITLE, not one element, and no word that the page was
        still coming. After a command that changed the page's address, a page with nothing on it (no text, no control)
        is not an answer yet: wait for something to show, then for the page to settle. A page that stays empty gets a
        NOTE. Costs nothing unless the scan came back empty."""
        # (a page made of frames has no text or control of its own: its frames are its content)
        empty = lambda its, m: not its and not m.get("text") and not m.get("frames")
        if not empty(items, meta) or not re.match(r"^https?:", self.page.url or "") or await self.doc_kind():
            return items, meta
        t0 = time.time()
        with self.span("empty page"):
            while time.time() - t0 < max_s:
                await asyncio.sleep(0.2)
                self.dirty, self.scan = True, None
                try:
                    items, meta = await self.collect()
                except Err:
                    raise
                except Exception:
                    continue                   # a document on its way in: the scan can fail in between
                if not empty(items, meta):
                    self.base = None           # it has begun to show: let it finish, as after any page load
                    await self.settle(max_s=4)
                    self.scan = None
                    return await self.collect()
                if await self.doc_kind():
                    return items, meta
        self.unfinished = True
        self.notes.append(f"the page has nothing on it yet (no text, no control), {time.time() - t0:.0f} s after it opened: it may still be "
                          "loading. pb view looks again; a command that names its target waits for it")
        return items, meta

    # ---- target resolution
    def loc(self, ref):
        if ref not in self.refs:
            # The page may have replaced that element with a fresh copy (same button, new node, so a new ref). If the
            # page now holds exactly one element of the same kind, text and name, that is the one that was meant.
            was = self.ref_hist.get(ref)
            same = [r for r, (_, x) in self.refs.items() if was and (x["k"], x.get("t", ""), x.get("name", ""), x.get("fr", "")) == was]
            if len(same) == 1:
                self.notes.append(f'{ref} was re-rendered by the page; used {same[0]}, the same {was[0]} "{was[1][:50]}"')
                ref = same[0]
            else:
                raise Err(f"unknown ref {ref}: that element is no longer on the page (or the ref is from an older page)"
                          + (f", and {len(same)} elements now look like it" if same else "") + ". Take a fresh ref: pb view, or pb find TEXT")
        fr, it = self.refs[ref]
        # .first: a page may clone a node that carries a ref between a scan and the action (ulta). The next scan gives
        # the copy a ref of its own; until then the ref stands for the first of them, and no command fails over it.
        return fr.locator(f'[data-pb="{ref}"]').first, it

    @staticmethod
    def score(q, it, purpose, chrome_ok=False):
        """How well item `it` matches the target text q for an action (0: not at all). chrome_ok: let a header or
        footer link that merely contains a short target count (see the end)."""
        k = it["k"]
        if k in ("h", "!"):
            return 0
        if purpose == "fill" and k not in ("input", "select", "combo"):
            return 0
        if purpose == "check" and k not in ("checkbox", "radio", "click", "button"):
            return 0
        # label, aria-label and name count fully; a field's placeholder and the text it currently shows count a little
        # less (a view line prints them, so they get used as targets)
        # screen-reader boilerplate is no part of the name (ebay: a survey link labelled "... opens in new window or tab"
        # won `click New`)
        al0 = NEW_WINDOW_RX.sub("", it.get("al", "")).strip(" -,:;") if it.get("al") else ""
        if it.get("ao"):
            # the shown name is the aria-label itself (an icon link): it counts as an aria-label match
            al0, it = NEW_WINDOW_RX.sub("", it.get("t", "")).strip(" -,:;"), dict(it, t="")
        cands = [(it.get("t", ""), 0), (al0, 0), (it.get("name", ""), 0), (it.get("ph", ""), 5), (it.get("dl", ""), 5)]
        if k == "input" and purpose == "fill" and not str(it.get("v", "")).startswith("•"):
            cands.append((it.get("v", ""), 10))
        # An aria-label that says more than the element shows ("Popular now" links labelled with a product's title, on
        # etsy) must not beat an element that shows the words: when the element has text of its own, a match on its
        # aria-label alone counts like a weak match.
        t = it.get("t", "")
        # (no text of its own: an aria-label match short of exact stays below a visible text that starts with the words)
        al_cap = 35 if t and not (t.startswith("[") and t.endswith("]")) else 55

        def match(ql, cl, ws):
            if cl == ql:
                return 100
            if cl.rstrip("*: ") == ql.rstrip("*: "):
                return 95
            if cl.startswith(ql):
                return 60
            if cl.endswith("…") and len(cl) > 25 and ql.startswith(cl[:-1].rstrip()):
                return 90                          # the view cut this text short; the caller gave the whole of it
            if ql in cl and (not ws or len(ql) >= 4):
                # inside another word counts less than as a word of its own (tcgplayer: "Cart" in "cartastcg")
                return 40 if ws or re.search(r"(?<![^\W_])" + re.escape(ql) + r"(?![^\W_])", cl) else 30
            return 0

        best, raw = 0, 0
        ql = fold(q).strip()
        for ws in (False, True):
            if ws:
                # Text the page splits over child elements reads with or without a space between the parts
                # ("$8.00 ShippingArrives by", nike), and callers type it either way: compare without any spaces.
                ql = re.sub(r"\s+", "", ql)
            for i, (c, less) in enumerate(cands):
                cl = fold(c).strip()
                if not cl:
                    continue
                if ws:
                    cl = re.sub(r"\s+", "", cl)
                s = match(ql, cl, ws)
                raw = max(raw, s)
                if s:
                    s = s - less - (5 if ws else 0)
                    # an aria-label that says exactly the target (tcgplayer's cart link shows only its count, "1")
                    # beats words found at the start of or inside other elements' text ("Cart Optimizer", "cartastcg"),
                    # and still loses to text shown exactly (etsy, above)
                    cap = max(al_cap, 70) if s + less >= 95 and not ws else al_cap
                    best = max(best, min(s, cap) if i == 1 else s)
            if best:
                break
        if it.get("srch") and re.fullmatch(r"(the )?search( box| field| bar| input)?", fold(q).strip()):
            best = max(best, 90)       # jcpenney: a type=search box labelled "What can we help you find?"
        if not best:
            return 0
        if (purpose == "click" and not chrome_ok and raw < 60 and it.get("reg") == "chrome" and k in ("link", "click")
                and len(q.split()) <= 2):
            # lego: `click Continue` hit a footer link to globalprivacycontrol.org whose text merely held "continue",
            # while the page's own Continue button had not shown up yet. A short target found only inside the words
            # of a header or footer link is no match: the target is waited for, as when nothing matches.
            return 0
        if purpose == "click":
            best += {"button": 10, "link": 6, "tab": 5, "menuitem": 5, "option": 8, "radio": 4, "checkbox": 4, "click": 2}.get(k, 0)
            if k == "input" and it.get("it") not in ("slider",):
                # a text box that carries the words as its label or placeholder is not what `click Search` means when a
                # button says them (cochranelibrary.com: the box's placeholder "Search" beat the icon button
                # aria-labelled "Search", and nothing was submitted)
                best -= 30
        if it.get("reg") == "dialog":
            best += 20
        if it.get("reg") == "chrome":
            best -= 3
        if it.get("dis"):
            best -= 50
        return best

    # How many levels up from el is the smallest block whose text holds q: -1 none, -2 that block also holds another
    # element with el's text (another "15" of a calendar: the text is next to that one, or to none in particular)
    NEAR_CORE = """let p = el, d = 0; while (p && d < 14) { if ((p.innerText || '').toLowerCase().includes(q)) {
                      const t = (el.innerText || '').replace(/\\s+/g, ' ').trim();
                      if (t && d > 0) for (const x of p.querySelectorAll('*')) { if (x.childElementCount || el.contains(x)) continue;
                        const xt = x.textContent; if (xt.length < t.length || xt.length > t.length + 40) continue;
                        const ctl = x.closest('button,a,[role=button],[role=link]');
                        if (ctl && ctl !== el && (ctl.innerText || '').replace(/\\s+/g, ' ').trim() !== t) continue;   /* a word inside another control's longer name ("Toggle: Search / Add to History", pubmed) */
                        if (xt.replace(/\\s+/g, ' ').trim() === t) return -2; }
                      return d; } p = p.parentElement; d++; } return -1;"""
    NEAR_JS = "(el, q) => { " + NEAR_CORE + " }"
    NEAR_ALL_JS = """([refs, q]) => refs.map((ref) => { const el = document.querySelector('[data-pb="' + ref + '"]'); if (!el) return null; """ + NEAR_CORE + " })"
    CTX_JS = """(el) => { let p = el; for (let i = 0; i < 6 && p.parentElement; i++) { p = p.parentElement; const t = (p.innerText || '').replace(/\\s+/g, ' ').trim();
                 if (t.length > (el.innerText || '').trim().length + 8) return t.slice(0, 70); } return ''; }"""

    # For each ref: does its element sit in a list, carousel or slider (true), outside all of them (false), or is it
    # not found (null)? Recommendation tiles, "similar items" and sponsored rows are built that way.
    IN_LIST_JS = r"""(refs) => refs.map((ref) => {
        const el = document.querySelector('[data-pb="' + ref + '"]');
        if (!el) return null;
        const RX = /carousel|slider|swiper|recommend|related|similar|sponsored/i;
        for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
          const tag = p.tagName, role = p.getAttribute('role') || '';
          if (tag === 'UL' || tag === 'OL' || tag === 'LI' || role === 'list' || role === 'listitem') return true;
          const c = typeof p.className === 'string' ? p.className : '';
          if ((c && RX.test(c)) || (p.id && RX.test(p.id))) return true;
        }
        return false; })"""

    # The one checkbox in the row (list item, table row, small box) of the text q: text nodes that read q exactly, then
    # ones that hold it, each walked up until a block holds a checkbox; one box there is the answer, several are not.
    ROW_BOX_JS = r"""(q) => {
        const norm = (s) => (s || '').replace(/\s+/g, ' ').trim().toLowerCase();
        q = norm(q);
        const hits = [[], []];
        const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        for (let n = w.nextNode(), k = 0; n && k < 20000; n = w.nextNode(), k++) {
          const t = norm(n.nodeValue);
          if (!t || t.length > q.length + 60) continue;
          if (t === q) hits[0].push(n.parentElement); else if (t.includes(q)) hits[1].push(n.parentElement);
        }
        for (const list of hits) for (const el of list) {
          let p = el;
          for (let d = 0; p && p !== document.body && d < 6; d++, p = p.parentElement) {
            const bx = [...p.querySelectorAll('input[type=checkbox],[role=checkbox]')];
            if (bx.length === 1) { const tok = 'r' + Math.random().toString(36).slice(2, 9); bx[0].setAttribute('data-pb-row', tok); return tok; }
            if (bx.length > 1) break;
          }
        }
        return null; }"""

    # For fill / select when no field is named by the target: [what, token, words]. what: 'radio' / 'checkbox' (select:
    # the box whose label is the option, under a legend or label that holds the target), 'select' (select: the one
    # dropdown that has the option), 'field' (the single field in the row or small box of a text that is exactly the
    # target), 'many' (several dropdowns have the option: their refs), or null.
    FIELD_BY_TEXT_JS = r"""([cmd, target, option]) => {
        const N = (s) => (s || '').replace(/\s+/g, ' ').trim().toLowerCase(), q = N(target), o = N(option);
        const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && (!e.checkVisibility || e.checkVisibility({ checkVisibilityCSS: true })); };
        const mark = (e) => { const t = 'f' + Math.random().toString(36).slice(2, 9); e.setAttribute('data-pb-row', t); return t; };
        const boxText = (b) => N((b.labels && b.labels[0] && b.labels[0].innerText) || b.getAttribute('aria-label') || (b.closest('label') || {}).innerText || (b.nextSibling && b.nextSibling.textContent) || '');
        // a field with a name of its own that is not the target is another field (amtrak: "From" text, its own field
        // hidden, and the field after it is the one labelled To: BOS went into To)
        const own = (f) => N(f.getAttribute('aria-label') || (f.labels && f.labels[0] && f.labels[0].innerText) || '');
        const otherwise = (f) => { const n = own(f); return !!n && !n.includes(q) && !q.includes(n); };
        const texts = [...document.querySelectorAll('legend,label,h1,h2,h3,h4,h5,h6,p,span,div,td,th,dt,[role=radiogroup]')]
          .filter((e) => vis(e) && (e.getAttribute('aria-label') ? N(e.getAttribute('aria-label')) === q : (e.childElementCount <= 2 && N(e.innerText) === q)));
        if (cmd === 'select' && o) {
          for (const t of texts) {
            let c = t.closest('fieldset') || t.parentElement;
            for (let i = 0; c && i < 3; i++, c = c.parentElement) {
              const bx = [...c.querySelectorAll('input[type=radio],input[type=checkbox],[role=radio]')];
              if (!bx.length) continue;
              const hit = bx.find((b) => boxText(b) === o) || bx.find((b) => boxText(b).startsWith(o));
              if (hit) return [hit.type === 'checkbox' ? 'checkbox' : 'radio', mark(hit), boxText(hit)];
              break;
            }
          }
          const sels = [...document.querySelectorAll('select')].filter((s) => vis(s) && [...s.options].some((x) => N(x.textContent) === o));
          if (sels.length === 1) return ['select', mark(sels[0]), ''];
          if (sels.length > 1) return ['many', '', sels.slice(0, 6).map((s) => s.getAttribute('data-pb') || s.name || s.id || 'select').join(', ')];
        }
        for (const t of texts) {
          let c = t.parentElement;
          for (let i = 0; c && c !== document.body && i < 3; i++, c = c.parentElement) {
            const fs = [...c.querySelectorAll(cmd === 'select' ? 'select,[role=combobox],input[aria-autocomplete]' : 'input:not([type=hidden]):not([type=radio]):not([type=checkbox]),textarea,select')].filter(vis)
              .filter((f, i, all) => !all.some((o) => o !== f && f.contains(o)))      // (a combobox box and the input in it: one field)
              .filter((f) => !otherwise(f));
            if (fs.length === 1) return ['field', mark(fs[0]), ''];
            if (fs.length > 1) break;
          }
        }
        // a text in a row of its own above its field (demoqa's "Select Value" over a react-select, in the next row): the
        // first field after the text, close under it
        const SEL = cmd === 'select' ? 'select,[role=combobox],input[aria-autocomplete]' : 'input:not([type=hidden]):not([type=radio]):not([type=checkbox]),textarea,select';
        for (const t of texts) {
          const tr = t.getBoundingClientRect();
          const f = [...document.querySelectorAll(SEL)].filter(vis).filter((x) => !otherwise(x)).find((x) => (t.compareDocumentPosition(x) & Node.DOCUMENT_POSITION_FOLLOWING)
            && x.getBoundingClientRect().top >= tr.top && x.getBoundingClientRect().top - tr.bottom < 60);
          if (f) { const inner = f.matches('[role=combobox]') && f.querySelector('input'); return ['field', mark(inner || f), '']; }
        }
        return null; }"""

    async def field_by_text(self, cmd, target, option):
        """fill / select when no field is named by the target (see FIELD_BY_TEXT_JS). -> ("done", lines) |
        ("loc", locator, item, note) | None."""
        fr = self.page.main_frame
        try:
            r = await asyncio.wait_for(fr.evaluate(self.FIELD_BY_TEXT_JS, [cmd, target, option]), 3)
        except Exception:
            return None
        if not r:
            return None
        what, tok, words = r
        if what == "many":
            raise Err(f'no dropdown is named "{target}", and several have the option "{option}": {words}. Use the ref of the one you mean')
        loc = fr.locator(f'[data-pb-row="{tok}"]').first
        if what in ("radio", "checkbox"):
            st = await self.look(loc)
            await self.do_check(loc, {"k": what}, True, st)
            await self.settle(max_s=2, quiet=0.25, react=0.3)
            return "done", [f'ok select: checked the {what} "{words or option}" under "{target}" (a {what} group, not a dropdown; pb check does this too)']
        if what == "select":
            return "loc", loc, {"k": "select", "t": target}, f'no dropdown is named "{target}": used the one dropdown on the page that has "{option}"'
        return "loc", loc, {"k": "input", "t": target}, f'"{target}" is not tied to a field: used the field next to that text'

    async def resolve(self, target, items, purpose, near=None):
        """-> (locator, item). target: ref | css=... | text. `near` picks, among equal matches, the one whose
        surrounding block contains that text (25 identical "Select" buttons, one per store)."""
        if re.fullmatch(r"e\d+", target):
            return self.loc(target)
        m_attr = re.fullmatch(r"(id|name)=(.+)", target.strip())
        if m_attr:
            # the view prints `id=datePickerMonthYearInput` and `name=q`: they work as targets
            target = 'css=[' + m_attr.group(1) + '="' + m_attr.group(2).strip('"\'').replace('"', '\\"') + '"]'
        if target.startswith("css="):
            # the main document first; when it has no match, the visible frames (an editor body inside an iframe)
            for fr in [self.page.main_frame] + await self.visible_frames():
                n = 0
                with contextlib.suppress(Exception):
                    n = await asyncio.wait_for(fr.locator(target[4:]).count(), 2)
                if n:
                    return fr.locator(target[4:]).first, {"k": "css", "t": target, "ref": target}
            # once more, a moment later: a count asked while the page was rewriting itself came back empty once
            # (uitestingplayground's progress bar: `text --of id=progressBar` said nothing shows it, then worked)
            for _ in range(3):
                await asyncio.sleep(0.25)
                n = 0
                with contextlib.suppress(Exception):
                    n = await asyncio.wait_for(self.page.main_frame.locator(target[4:]).count(), 3)
                if n:
                    return self.page.main_frame.locator(target[4:]).first, {"k": "css", "t": target, "ref": target}
            raise NotFound(f"no element matches {target} in the page or its frames. Check the selector (pb find TEXT gives refs)")
        if purpose == "click":
            # a calendar day by its date, in any form: "January 15, 2027" against cells labelled "Friday, January 15, 2027",
            # or `15 --near "January 2027"` on a calendar that shows two months (amtrak, Google Flights)
            qd = date_of(target)
            if qd is None and near and re.fullmatch(r"\d{1,2}", target.strip()):
                qd = date_of(f"{near} {target}")
            if qd is not None:
                days = [it for it in items if "ref" in it and it["k"] in ("button", "link", "click", "option", "radio")
                        and same_day_key(date_of(it.get("dl") or it.get("al") or it.get("t", "")), qd)]
                if len(days) > 1 and qd[0] is not None:
                    # the ones whose label carries the year beat a yearless one
                    full = [it for it in days if (date_of(it.get("dl") or it.get("al") or it.get("t", "")) or (None,))[0] == qd[0]]
                    days = full or days
                if len(days) == 1:
                    return self.loc(days[0]["ref"])
                if not days and any(it.get("dl") for it in items):
                    # a calendar is up but not on that month (Google Flights opens on the current two months)
                    shown = sorted({f"{date_of(it['dl'])[1]:02d}/{date_of(it['dl'])[0]}" for it in items if it.get("dl") and date_of(it["dl"]) and date_of(it["dl"])[0]})
                    raise NotFound(f'no calendar day for "{target}" shows: the calendar shows {", ".join(shown[:4]) or "other days"} (month/year). '
                                   "Move it to that month first (its Next button), then click the day again")
        scored = sorted(((self.score(target, it, purpose), i, it) for i, it in enumerate(items)), key=lambda x: (-x[0], x[1]))
        scored = [x for x in scored if x[0] > 0]
        if not scored and purpose == "check":
            # TodoMVC: the todo boxes have no name. The one checkbox in the row or list item that shows the text is meant.
            with contextlib.suppress(Exception):
                tok = await asyncio.wait_for(self.page.main_frame.evaluate(self.ROW_BOX_JS, target), 2.5)
                if tok:
                    return self.page.main_frame.locator(f'[data-pb-row="{tok}"]').first, {"k": "checkbox", "t": f"in the row of {target[:50]}"}
        if not scored and re.search(r"^[#.\[]|:nth-|^[a-z][a-z0-9]*-[a-z0-9-]+$|^[a-z][a-z0-9]*[#.\[][\w-]", target.strip()) and " " not in target.strip():
            # a target that reads as a CSS selector (`figure:nth-of-type(2)`, `relative-time`, `#x`) and names no text
            with contextlib.suppress(Exception):
                n = await asyncio.wait_for(self.page.main_frame.locator(target.strip()).count(), 2)
                if n:
                    self.notes.append(f'"{target}" matched no text or label; it was used as css={target.strip()}')
                    return self.page.main_frame.locator(target.strip()).first, {"k": "css", "t": "css=" + target.strip(), "ref": "css=" + target.strip()}
        if not scored:
            weak =[it for it in items if purpose == "click" and it.get("reg") == "chrome" and self.score(target, it, purpose, chrome_ok=True) > 0]
            if purpose == "fill":
                # ulta: the search box exists only once the Search button is clicked; nordstrom: a box that turns into a
                # field when clicked
                btns = sorted(((self.score(target, it, "click"), i, it) for i, it in enumerate(items)
                               if it["k"] in ("button", "link", "click", "tab", "menuitem") and "ref" in it), key=lambda x: (-x[0], x[1]))
                btns = [x[2] for x in btns if x[0] > 0][:3]
                if btns:
                    what = {"click": "clickable box", "menuitem": "menu item"}.get(btns[0]["k"], btns[0]["k"])
                    raise NotFound(f'no field matches "{target}", but there is a {what} with that name: click it first, then fill '
                                   "(it may open the field): " + "; ".join(self.line(it) for it in btns))
            raise NotFound(f'nothing matches "{target}" for {purpose}'
                           + (". Only header or footer links hold those words: " + "; ".join(self.line(it) for it in weak[:4])
                              + " (use the ref if one of them is meant)" if weak else "")
                           + ". Try pb find, pb view --all, or css=SELECTOR")
        top = scored[0][0]
        ties = [x[2] for x in scored if x[0] == top]
        nth = getattr(self, "pick_nth", None)
        if nth:
            ties.sort(key=lambda it: items.index(it))        # page order
            if nth > len(ties):
                raise NotFound(f'--nth {nth}: only {len(ties)} element(s) match "{target}" equally: '
                               + "; ".join(self.line(it) for it in ties[:6]))
            return self.loc(ties[nth - 1]["ref"])
        if near and all("ref" in it for it in ties):
            # (also with one match: google flights' `click 15 --near "January 2027"` took the 15 of December, the one
            # in the scan, since January was out of view; near was looked at only among several equal matches)
            async def depth(it):
                try:
                    return await asyncio.wait_for(self.loc(it["ref"])[0].evaluate(self.NEAR_JS, near.lower()), 2)
                except Exception:
                    return -1

            # All candidates of a frame are asked about in one round trip (25 store rows were 25). One the document
            # cannot find by its ref (it sits in a shadow root) is asked for by itself.
            cands, by_frame, depths = ties[:80], {}, {}
            for it in cands:
                by_frame.setdefault(self.refs[it["ref"]][0], []).append(it)

            async def ask(fr, its):
                try:
                    ds = await asyncio.wait_for(fr.evaluate(self.NEAR_ALL_JS, [[it["ref"] for it in its], near.lower()]), 2.5)
                except Exception:
                    ds = [None] * len(its)
                for it, d in zip(its, ds):
                    depths[it["ref"]] = d if d is not None else await depth(it)

            await asyncio.gather(*(ask(fr, its) for fr, its in by_frame.items()))
            found = [(depths[it["ref"]], it) for it in cands if depths.get(it["ref"], -1) >= 0]
            shared = sum(1 for it in cands if depths.get(it["ref"]) == -2)
            scroll = f'. If it is out of view (a calendar that shows a few months), bring it in first: pb scroll "{near}", then try again'
            if not found and shared:
                raise Err(f'"{near}" is not next to one single "{target}": the block around it holds other "{target}" too, '
                          f'so it is equally close to several of them. Nothing was clicked. It may belong to an entry that has no "{target}" '
                          f'(already selected?){scroll}. Look with: pb text "{near}"')
            if not found:
                raise Err(f'none of the {len(ties)} "{target}" matches has "{near}" in its surrounding block. Nothing was clicked{scroll}')
            best = min(d for d, _ in found)
            closest = [it for d, it in found if d == best]
            if len(closest) > 1:
                # the text sits in a block shared by several candidates, so it belongs to none of them in particular
                raise Err(f'"{near}" is not next to one single "{target}": {len(closest)} of them are equally close to it. It may belong to an '
                          f'entry that has no "{target}" (already selected?) or appear elsewhere on the page. Nothing was clicked. '
                          f'Look with: pb text "{near}"')
            return self.loc(closest[0]["ref"])
        if 1 < len(ties) <= 12 and all(it.get("ref") in self.refs for it in ties):
            # amtrak: "From" is a combobox wrapper and the input inside it, both named From: one target. The innermost
            # of matches that hold one another is the one meant.
            frs = {self.refs[it["ref"]][0] for it in ties}
            if len(frs) == 1:
                outer = []
                with contextlib.suppress(Exception):
                    outer = await asyncio.wait_for(next(iter(frs)).evaluate(
                        """(refs) => { const els = refs.map(r => document.querySelector('[data-pb="' + r + '"]'));
                           return refs.filter((r, i) => els[i] && els.some((o, j) => j !== i && o && els[i].contains(o))); }""",
                        [it["ref"] for it in ties]), 2)
                inner = [it for it in ties if it["ref"] not in outer]
                if outer and len(inner) == 1:
                    return self.loc(inner[0]["ref"])
        if len(ties) > 1 and len(ties) <= 80:
            # petsmart: "Add to cart" matched the product's own button and five in recommendation tiles. When exactly
            # one of the equal matches lies outside every list, carousel or slider, that is the main one. Asked only
            # when there is a tie, in one round trip per frame.
            by_frame, inlist = {}, {}
            for it in ties:
                if it.get("ref") in self.refs:
                    by_frame.setdefault(self.refs[it["ref"]][0], []).append(it)

            async def lists(fr, its):
                with contextlib.suppress(Exception):
                    r = await asyncio.wait_for(fr.evaluate(self.IN_LIST_JS, [it["ref"] for it in its]), 2)
                    for it, v in zip(its, r):
                        inlist[it["ref"]] = v

            await asyncio.gather(*(lists(fr, its) for fr, its in by_frame.items()))
            outside = [it for it in ties if inlist.get(it["ref"]) is False]
            if len(outside) == 1 and all(inlist.get(it["ref"]) is True for it in ties if it is not outside[0]):
                self.notes.append(f'"{target}" matched {len(ties)} elements: picked the one outside the product lists '
                                  f'({outside[0]["ref"]}); {len(ties) - 1} others are in lists or carousels')
                return self.loc(outside[0]["ref"])
        if len(ties) > 1:
            async def context(it):
                ctx = ""
                with contextlib.suppress(Exception):
                    loc, _ = self.loc(it["ref"])
                    ctx = await asyncio.wait_for(loc.evaluate(self.CTX_JS), 1.5)
                return f'{it["ref"]} {it["k"]} "{it.get("t", "")}"' + (f" in [{ctx}]" if ctx else "")

            parts = await asyncio.gather(*(context(it) for it in ties[:6]))
            raise Err(f'"{target}" is ambiguous ({len(ties)} matches): ' + "; ".join(parts) + '. Use a ref, or add: --near "text next to the one you want", or --nth N (the Nth of them in page order)')
        if purpose == "click":
            # pubmed's query builder: its ADD button had turned into AND, and `click ADD` clicked "Toggle: Search / Add to
            # History" with a plain ok. A click on a control whose name only holds the words says so.
            it0, sq = ties[0], lambda s: re.sub(r"\s+", "", fold(s or "").strip())
            ql = sq(target)
            names = [sq(it0.get("t")), sq(NEW_WINDOW_RX.sub("", it0.get("al", ""))), sq(it0.get("name")), sq(it0.get("ph"))]
            whole = any(n and (n == ql or n.startswith(ql) or n.rstrip("*:") == ql.rstrip("*:") or (n.endswith("…") and ql.startswith(n[:-1])))
                        for n in names)
            if ql and not whole:
                # Refused when the words sit inside a longer name, other words before and after them, or when the control
                # is a toggle: pubmed's ADD had become AND and `click ADD` switched "Toggle: Search / Add to History",
                # which changed the page's mode. "Checkout" for "Proceed to Checkout" (words before only) still goes.
                nm = fold(it0.get("t") or it0.get("al") or "")
                mm = re.search(r"(?<![^\W_])" + re.escape(fold(target).strip()) + r"(?![^\W_])", nm)
                inside = bool(mm and re.search(r"\w", nm[:mm.start()]) and re.search(r"\w", nm[mm.end():]))
                toggle = it0.get("on") is not None or it0.get("k") in ("checkbox", "radio") or nm.startswith("toggle")
                if inside or toggle:
                    raise NotFound(f'nothing is named "{target}". The only control that holds those words is {self.line(it0)}, '
                                   f'a {"toggle" if toggle else "control with a longer name"}: not clicked. Use its ref if it is the one; '
                                   f'the control asked for may have been renamed (pb find, pb view)')
                self.notes.append(f'nothing is named "{target}": clicked {self.line(it0)}, whose name only contains those words. '
                                  f'If that is not the one, the control may have been renamed: pb find "{target}" or pb view')
        return self.loc(ties[0]["ref"])

    # ---- actions
    async def pick_option_by_keyboard(self, loc):
        """Choose a listbox/autocomplete option with ArrowDown + Enter. Some sites freeze when an option is hovered or
        clicked by an automated mouse, and the keyboard path is what the widget is built for anyway."""
        js = """(el) => {
            const act = document.activeElement;
            const ad = act && act.getAttribute && act.getAttribute('aria-activedescendant');
            if (ad && el.id && ad === el.id) return true;
            if (el.getAttribute('aria-selected') === 'true' || el.getAttribute('data-focused') === 'true' || el.getAttribute('data-highlighted') != null) return true;
            return /(^|[\\s_-])(focus|focused|active|highlight|highlighted|is-focused)([\\s_-]|$)/i.test(typeof el.className === 'string' ? el.className : '');
        }"""
        try:
            n = await asyncio.wait_for(loc.evaluate("el => (el.parentElement ? el.parentElement.querySelectorAll('[role=option]').length : 1)"), 2)
            # the keys go to the focused element: only when that is a field or the list itself (else ArrowDown scrolls)
            ok = await asyncio.wait_for(loc.evaluate("""(el) => { let a = document.activeElement; while (a && a.shadowRoot && a.shadowRoot.activeElement) a = a.shadowRoot.activeElement;
                return !!a && a !== document.body && (a.tagName === 'INPUT' || a.isContentEditable || !!a.closest('[role=listbox],[role=combobox],[role=menu]') || a.contains(el)); }"""), 2)
        except Exception:
            return None
        if not ok:
            return None
        # demoqa: the first entry is highlighted as soon as the list opens. An ArrowDown first went past it, so the
        # highlight is looked at before every key, and Enter goes only to the entry asked for.
        for k in range(min(int(n) + 1, 25)):
            try:
                if await asyncio.wait_for(loc.evaluate(js), 2):
                    await self.page.keyboard.press("Enter")
                    return ("picked with keyboard (Enter on the entry, which was highlighted)" if k == 0
                            else f"picked with keyboard ({k} x ArrowDown, then Enter on the highlighted entry)")
            except Exception:
                return None
            await self.page.keyboard.press("ArrowDown")
            await asyncio.sleep(0.06)
        return None

    # One look at an element before acting on it, in one round trip: is it still there, could a person use it, and what
    # lies on top of it. With that the right way to act is chosen at once. (Trying the ways in turn, each until its own
    # timeout, made single steps cost 12 to 59 s: lowes `click Search`, jcpenney `uncheck`, cvs `fill`.)
    #   gone      it is no longer in the page
    #   vis       it has a box and is not hidden; when not, a mouse cannot reach it
    #   dis       disabled (or aria-disabled); off: the native disabled alone
    #   edit      text can be typed into it
    #   checked   true / false for a native checkbox or radio, else null
    #   focus     the keyboard focus is in it
    #   vlen      how many characters its value holds (-1: it has no value)
    #   cover     what lies on top of its center: '' nothing, 'popup' a suggestion list or menu, 'widget' another
    #             part of the same small control (a styled dropdown whose text box sits under its own placeholder),
    #             'other' anything else; what: that element in words
    #   x, y      its center in its own frame's window (it is scrolled into view first when asked to)
    # With mark it also tags the element as holding a secret (see MARK_SECRET), to save that round trip.
    LOOK_JS = """(els, [scroll, mark]) => {
        const el = els[0];
        if (!el || !el.isConnected) return { gone: true };
        if (mark) el.setAttribute('data-pb-secret', '1');
        const tag = el.tagName, typ = (el.getAttribute('type') || '').toLowerCase();
        let a = document.activeElement; while (a && a.shadowRoot && a.shadowRoot.activeElement) a = a.shadowRoot.activeElement;
        const st = { tag, type: typ, off: !!el.disabled, dis: !!el.disabled || el.getAttribute('aria-disabled') === 'true', focus: a === el,
                     edit: (tag === 'INPUT' || tag === 'TEXTAREA') ? !el.readOnly && !el.disabled : !!el.isContentEditable,
                     checked: (tag === 'INPUT' && (typ === 'checkbox' || typ === 'radio')) ? !!el.checked : null, cover: '', what: '',
                     vlen: typeof el.value === 'string' ? el.value.length : -1, ro: (tag === 'INPUT' || tag === 'TEXTAREA') && !!el.readOnly };
        let r = el.getBoundingClientRect();
        st.vis = (!el.checkVisibility || el.checkVisibility({ checkVisibilityCSS: true })) && r.width > 0 && r.height > 0;
        if (!st.vis) return st;
        const vw = window.innerWidth, vh = window.innerHeight;
        const out = (q) => q.left + q.width / 2 < 0 || q.top + q.height / 2 < 0 || q.left + q.width / 2 > vw || q.top + q.height / 2 > vh;
        if (scroll && out(r)) { el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' }); r = el.getBoundingClientRect(); }
        st.x = r.left + r.width / 2; st.y = r.top + r.height / 2;
        if (out(r)) return st;
        const top = document.elementFromPoint(st.x, st.y);
        // inside: across shadow roots too (the document only names the host of what lies in one)
        const inside = (p, q) => { for (; p; p = p.parentNode || p.host) if (p === q) return true; return false; };
        if (!top || inside(top, el) || inside(el, top)) return st;
        const t = (top.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 40);
        st.what = '<' + top.tagName.toLowerCase() + (top.id ? '#' + top.id : '') + (typeof top.className === 'string' && top.className ? '.' + top.className.trim().split(/\\s+/)[0] : '') + '>' + (t ? ' "' + t + '"' : '');
        if (top.closest('[role=listbox],[role=option],[role=menu],[role=menuitem],.pac-container,[class*="autocomplete"],[class*="suggest"],[class*="typeahead"]')) { st.cover = 'popup'; return st; }
        st.cover = 'other';
        // an open dialog or popup the target is not part of: a click through it does not reach the page behind
        const dlg = top.closest('[role=dialog],[role=alertdialog],[aria-modal=true],dialog[open]');
        if (dlg && !inside(el, dlg)) {
          const lb = dlg.getAttribute('aria-labelledby'), lbe = lb && document.getElementById(lb.split(/\\s+/)[0]);
          const hd = dlg.querySelector('h1,h2,h3,h4,[role=heading]');
          st.dlg = ((dlg.getAttribute('aria-label') || (lbe && lbe.innerText) || (hd && hd.innerText) || (dlg.innerText || '').split('\\n')[0] || '')
                    .replace(/\\s+/g, ' ').trim().slice(0, 60)) || 'a dialog';
          // its close controls, with the ref the last scan gave them
          st.dclose = [...dlg.querySelectorAll('button,a,[role=button]')].map((b) => [b.getAttribute('data-pb') || '',
              ((b.getAttribute('aria-label') || '') + ' ' + (b.innerText || '')).replace(/\\s+/g, ' ').trim().slice(0, 50)])
            .filter(([r, t]) => /close|dismiss|no,? thanks|not now|maybe later|cancel|skip|^x\\b|\\u00d7|\\u2715/i.test(t)).slice(0, 2);
        }
        let p = el;
        for (let i = 0; i < 4 && p.parentElement; i++) { p = p.parentElement; if (p.contains(top)) { const b = p.getBoundingClientRect(); if (b.height <= 120 && b.width <= 700) st.cover = 'widget'; break; } }
        return st; }"""

    async def look(self, loc, scroll=True, mark=False):
        """LOOK_JS on what the locator matches now. It never waits for the element: one that is not there reads as gone."""
        try:
            return await asyncio.wait_for(loc.evaluate_all(self.LOOK_JS, [scroll, mark]), 2.5)
        except Exception:
            # no answer (the page is busy or on its way to another document): nothing is known, the old ways apply
            return {"unknown": True, "vis": True, "dis": False, "off": False, "edit": True, "checked": None, "cover": "", "what": "", "focus": False, "tag": ""}

    def navigating(self, since):
        """Did the page ask for another document after `since`? Then the action went through, whatever the browser
        said about it: a click whose page load outlasted the click's own limit was reported as a failure, and every
        fallback then timed out against a page that was leaving (lowes `click View Cart`: 27 s, exit 1, cart loaded)."""
        return self.nav_t >= since - 0.05

    async def do_click(self, loc, it, st=None):
        if st is None:
            st = await self.look(loc)
        if st.get("gone"):
            raise Gone()                       # do not make every click strategy wait for a ghost
        if it.get("k") == "option":
            how = await self.pick_option_by_keyboard(loc)
            if how:
                return how
        t0 = time.time()

        async def script_click():
            try:
                await loc.evaluate("e => e.click()", timeout=1200)
            except Exception:
                if not self.navigating(t0):
                    raise

        if not st["vis"]:
            # It has no box (hidden, or of no size): no mouse click can land on it and Playwright would wait its whole
            # limit, twice, for it to show up. The click is sent to the element itself.
            await script_click()
            return "click (js)"
        if st["cover"] == "widget":
            # Playwright would wait its whole timeout for the cover to go away; within one control it never does.
            # (The box is asked of Playwright: the look's own x and y are those of the element's frame, not the page's.)
            with contextlib.suppress(Exception):
                box = await loc.bounding_box(timeout=1000)
                await self.page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                return "click (at its center: another part of the same control lies over it)"
        try:
            # no_wait_after: the click is done when the mouse button is up. Waiting here for the page it leads to made
            # a slow page load look like a failed click; settle() waits for that page.
            # Something on top of it may be on its way out (a fading layer), so the mouse still gets its chance: a
            # short one when the look just now saw the cover, the usual one otherwise.
            if not st["cover"] and "x" in st and not it.get("fr") and it.get("k") != "css" and self.refs.get(it.get("ref"), (self.page.main_frame,))[0] is self.page.main_frame:
                # The mouse comes over the target first, as a person's does. uitestingplayground's mouseover link is
                # replaced by a copy on mouseenter; with no_wait_after, Playwright's press then went to the old, detached
                # node and the click was lost. Moved here first, the click lands on what is under the mouse. (16 ms)
                with contextlib.suppress(Exception):
                    await self.page.mouse.move(st["x"], st["y"])
            await loc.click(timeout=1000 if st["cover"] else 2500, no_wait_after=True)
            return "click"
        except Exception as e:
            msg = str(e)
        if self.navigating(t0):
            return "click"
        st = await self.look(loc, scroll=False)
        if st.get("gone"):
            raise Gone()
        if st["cover"] == "popup":
            # A suggestion list or menu lies on top. A click at that spot would choose one of its entries (and on
            # some sites freeze the page), so close the list and click the real target.
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.2)
            st = await self.look(loc, scroll=False)
            if st.get("gone"):
                raise Gone()
            if st["cover"] == "popup":
                # Escape did not close it (lowes, samsung address boxes). Most of these lists close when their field
                # loses the focus, as when a person clicks elsewhere: take the focus out of the field and look again.
                with contextlib.suppress(Exception):
                    await self.page.evaluate("() => { let a = document.activeElement; while (a && a.shadowRoot && a.shadowRoot.activeElement) "
                                             "a = a.shadowRoot.activeElement; if (a && a.blur) a.blur(); }")
                await asyncio.sleep(0.2)
                st = await self.look(loc, scroll=False)
                if st.get("gone"):
                    raise Gone()
            if st["cover"] == "popup":
                # Still on top. A mouse click at that spot would pick one of its entries, so the click goes to the
                # element itself, by script.
                await script_click()
                return f"click (by script: an open suggestion list ({st['what'] or 'a list'}) covered it and did not close; check that it took effect)"
            try:
                await loc.click(timeout=2500, no_wait_after=True)
                return "click (after closing a suggestion list that covered it)"
            except Exception:
                if self.navigating(t0):
                    return "click"
                await script_click()
                return "click (by script, after closing a suggestion list that covered it; check that it took effect)"
        if st.get("dlg"):
            # booking.com: a "Sign in, save money" popup lay over the date field; the click by script reached the field
            # but opened nothing, and the answer read as success. A dialog the target is not part of is closed first.
            close = [(f"{r} " if r else "") + f'button "{t}"' for r, t in st.get("dclose") or []]
            raise Err(f'covered by the dialog "{st["dlg"]}", so nothing was clicked: close it first'
                      + (", " + "; ".join(close) if close else " (pb view lists it; pb press Escape often closes one)"))
        if st["cover"] or "intercepts pointer events" in msg:
            # Something else lies over it (a transparent layer, a sticky bar). A mouse click there would land on that
            # other thing, so the click is sent to the element itself, and the answer says so.
            await script_click()
            # Said in full once per page: a cookie banner over the page (samsung, ikea, petsmart) covers every target,
            # and the same warning on every click was noise.
            key = self.page.url.split("#")[0]
            if key in self.cover_said:
                return "click (by script: covered, as before)"
            self.cover_said.add(key)
            return (f"click (it was covered by {st['what'] or 'another element'}, so the click went to it by script; check that it took "
                    "effect. If that is a cookie banner or a popup, dismiss it first: later clicks on this page meet the same)")
        if st["vis"]:
            try:
                await loc.click(timeout=1200, force=True, no_wait_after=True)
                return "click (forced)"
            except Exception:
                if self.navigating(t0):
                    return "click"
        await script_click()
        return "click (js)"

    async def do_check(self, loc, it, want, st):
        """Tick or untick a box. A native box that is not shown or lies under its own styled label (the usual custom
        checkbox) is clicked by script at once: every mouse way would time out first (jcpenney: 6.8 s)."""
        if st.get("gone"):
            raise Gone()
        if st["checked"] is not None and (not st["vis"] or st["cover"]):
            if st["checked"] != want:
                await loc.evaluate("e => e.click()", timeout=1200)
                now = await loc.evaluate("e => !!e.checked", timeout=1200)
                if now != want and it.get("k") != "radio":
                    # the page put it back, or wants its label clicked: the old way, with its fallbacks
                    await self.do_click(loc, it)
            return
        try:
            await (loc.check(timeout=2500) if want else loc.uncheck(timeout=2500))
        except Exception:
            await self.do_click(loc, it)

    # The other text fields of the field's document and their values, kept in the page before typing (FIELD_LEAK_JS
    # compares after): amtrak's depart date went partly into the To field ("NYP/202701/15/2027").
    FIELD_SNAP_JS = r"""(el) => {
      const fs = [...el.ownerDocument.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=file]),textarea')]
        .filter(f => f !== el).slice(0, 300);
      window.__pbFieldSnap = fs.map(f => [f, f.value]);
      // keys that land in another field reach it as trusted input events; a page script that copies a value over
      // (billing same as shipping) does not make those, and its fields are left alone
      const got = window.__pbTypedInto = new Set();
      if (window.__pbTypedOff) window.__pbTypedOff();
      const on = (e) => { if (e.isTrusted && e.target !== el) got.add(e.target); };
      el.ownerDocument.addEventListener('input', on, true);
      window.__pbTypedOff = () => { el.ownerDocument.removeEventListener('input', on, true); window.__pbTypedOff = null; };
      return fs.length;
    }"""
    # -> labels of the fields that took some of the typed text, each put back to the value it had
    FIELD_LEAK_JS = r"""(el, typed) => {
      const snap = window.__pbFieldSnap || [], got = window.__pbTypedInto || new Set();
      window.__pbFieldSnap = null;
      if (window.__pbTypedOff) window.__pbTypedOff();
      const k = Math.min(3, typed.length), bits = [];
      for (let i = 0; i + k <= typed.length; i++) bits.push(typed.slice(i, i + k));
      const out = [];
      for (const [f, v] of snap) {
        if (!f.isConnected || f.value === v || !k || !got.has(f)) continue;
        if (!bits.some(b => f.value.includes(b) && !v.includes(b))) continue;
        const set = Object.getOwnPropertyDescriptor(f.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype, 'value').set;
        set.call(f, v);
        f.dispatchEvent(new Event('input', { bubbles: true }));
        f.dispatchEvent(new Event('change', { bubbles: true }));
        out.push((f.getAttribute('aria-label') || (f.labels && f.labels[0] && f.labels[0].innerText) || f.placeholder || f.name || f.id || 'a field').trim().slice(0, 40));
      }
      return out;
    }"""

    async def do_fill(self, loc, value, keys=False, st=None):
        """do_fill_typed, with a guard: text that the page sent into another field while pb typed (focus moved away
        in the middle: a date field that moves on by itself) is taken out of that field again, the value is set in the
        field asked for, and self.fill_leak says so."""
        self.fill_leak = ""
        snapped = False
        with contextlib.suppress(Exception):
            snapped = bool(await loc.evaluate(self.FIELD_SNAP_JS, timeout=1500))
        actual = await self.do_fill_typed(loc, value, keys, st)
        if snapped:
            leaked = []
            with contextlib.suppress(Exception):
                leaked = await loc.evaluate(self.FIELD_LEAK_JS, value, timeout=1500)
            if leaked:
                norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
                if norm(actual) != norm(value):
                    with contextlib.suppress(Exception):
                        await loc.fill(value, timeout=1500)
                        actual = await loc.input_value(timeout=1500)
                self.fill_leak = (f" (some of the typed text went into another field, {', '.join(leaked)[:80]}, while typing: "
                                  "taken out of it again; check both)")
        return actual

    async def do_fill_typed(self, loc, value, keys=False, st=None):
        """keys=True: clear the field and type with real key events. Search boxes and comboboxes run by a script often
        build their query from key events and ignore a value set at once (target.com: fill + Enter searched nothing).
        st: what Session.look saw of the field. A field that is disabled, or neither shown nor able to take the focus,
        is refused with the reason instead of being typed at. Returns what the field holds afterwards (None: not known)."""
        norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
        if st is None:
            st = await self.look(loc)
        if st.get("gone"):
            raise Gone()
        for _ in range(5):
            if not st.get("off"):
                break
            await asyncio.sleep(0.2)               # a field the page is just about to enable
            st = await self.look(loc)
        if st.get("gone"):
            raise Gone()
        if st["off"]:
            # (the hint about a missing step only where something points to one: a required field of the same form
            # still empty, or a disabled fieldset around it; selenium's "Disabled input" is disabled for good)
            pending = False
            with contextlib.suppress(Exception):
                pending = await loc.evaluate("e => !!e.closest('fieldset[disabled]') || (!!e.form && [...e.form.elements].some(f => f !== e && f.required && !f.disabled && !f.value))", timeout=1500)
            raise Err("that field is disabled, so nothing was typed" + (". Something the page requires first is still missing (a required field "
                      "of the form is empty)" if pending else ". It is disabled on this page, not waiting for an earlier step"))
        if st.get("ro") and not keys:
            # (keys=True: a combobox that is read-only on purpose and opens its list when clicked takes the other way)
            raise Err("that field is read-only, so nothing was typed. It shows a value the page sets itself")
        if st.get("vis") and st.get("cover") == "other":
            # uitestingplayground /overlapped: its centre lies under another element, or outside its own scrolling box.
            # Brought to the middle of that box first, the way click does it (some pages empty a field typed while hidden).
            with contextlib.suppress(Exception):
                await loc.evaluate("e => e.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' })", timeout=1000)
                st = await self.look(loc, scroll=False)
        typed = False
        if not st["vis"]:
            # Not shown: Playwright would wait out its limit for it to appear, and so would each fallback (cvs: 16.7 s
            # for a search box that was not open). A click by script may open what holds it; a field of no size can
            # still take the keyboard focus. If neither, say so: typing would land somewhere else.
            focused = False
            with contextlib.suppress(Exception):
                focused = await loc.evaluate("e => { e.click(); e.focus(); let a = document.activeElement; "
                                             "while (a && a.shadowRoot && a.shadowRoot.activeElement) a = a.shadowRoot.activeElement; return a === e; }", timeout=1200)
            st = await self.look(loc)
            if st.get("gone"):
                raise Gone()
            if not st["vis"]:
                if not focused:
                    raise Err("that field is not visible (it is hidden, or has no size), so nothing was typed. Open what holds it "
                              "first: pb view lists what the page shows")
                await self.clear_field(loc)
                await self.page.keyboard.type(value, delay=15)
                typed = True
        if not typed:
            try:
                if not st["edit"]:
                    raise Exception("not a text field")        # a custom control: click it and type, as a person would
                if not keys:
                    await loc.fill(value, timeout=2000)
                else:
                    if st["cover"]:
                        # a layer over the box (a placeholder animation, a click shield): the mouse would wait for it
                        # to go away, the keyboard needs no clear line of sight
                        await loc.focus(timeout=1500)
                    else:
                        try:
                            await loc.click(timeout=1500, no_wait_after=True)
                        except Exception:
                            await loc.focus(timeout=1500)
                    if st.get("vlen") != 0:                 # an empty field needs no emptying
                        await self.clear_field(loc)
                    await loc.press_sequentially(value, delay=8, timeout=8000)
            except Exception:
                await self.do_click(loc, {})
                await self.page.keyboard.press("Control+A")
                await self.page.keyboard.type(value, delay=20)
        actual = None
        with contextlib.suppress(Exception):
            actual = await loc.input_value(timeout=1500)

        def fine(a):
            """The field holds the text: as typed (spacing and punctuation aside), or completed by the field's own
            script ("100 Summer St, Boston, MA": the text, then more, and the text only once)."""
            want, got = norm(value), norm(a)
            return a is None or got == want or (bool(want) and got.startswith(want) and want not in got[len(want):])

        if not fine(actual):
            # Keys got lost (a script that formats while one types) or old text stayed. Once more, slowly, into a
            # field that is known to be empty: typing after a select-all the field ignored doubled the text
            # (advanceautoparts: "100 Summer St100 Summer St").
            with contextlib.suppress(Exception):
                await loc.focus(timeout=1500)
                await self.clear_field(loc)
                await loc.press_sequentially(value, delay=25, timeout=8000)
                actual = await loc.input_value(timeout=1500)
            if not fine(actual) and st["edit"]:
                # still not it: set the text at once
                with contextlib.suppress(Exception):
                    await loc.fill(value, timeout=1500)
                    actual = await loc.input_value(timeout=1500)
        return actual

    # Suggestion lists. mode 'mark': remember what is clickable now, so that 'list' can tell what typing brought up.
    # mode 'list' (aria: true = ARIA ways only): the suggestions that belong to the focused field, each tagged
    # data-pb-sug=N. Ways, in order: a native datalist; the list the field names (aria-controls / aria-owns, of the
    # field or its combobox); an open listbox; new clickable entries near the field or in the dialog it sits in.
    # -> { kind, items: [{ i, t, hl }], field: text the field holds, ins: the field is the one pb typed into }
    SUG_JS = r"""([mode, aria]) => {
      let a = document.activeElement; while (a && a.shadowRoot && a.shadowRoot.activeElement) a = a.shadowRoot.activeElement;
      const CAND = 'li,[role=option],[role=menuitem],a,button,[class*="option" i],[class*="suggest" i],[class*="item" i],[class*="result" i]';
      const shown = (el) => { if (el.checkVisibility && !el.checkVisibility({ checkVisibilityCSS: true })) return false;
        const r = el.getBoundingClientRect(); return r.width > 2 && r.height > 2; };
      const txt = (el) => (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
      if (mode === 'mark') { window.__pbSugPre = new WeakSet([...document.querySelectorAll(CAND + ',div,span,p')].filter(shown)); return null; }
      const pre = window.__pbSugPre || new WeakSet();
      const edit = a && (a.tagName === 'INPUT' || a.tagName === 'TEXTAREA' || a.isContentEditable) ? a : null;
      const out = { kind: '', items: [], field: edit ? (edit.value !== undefined ? edit.value : txt(edit)) : null };
      const HL = /(^|[\s_-])(focus|focused|active|highlight|highlighted|is-focused|selected|hover)([\s_-]|$)/i;
      const ad = edit && edit.getAttribute('aria-activedescendant');
      const hl = (el) => (ad && el.id === ad) || el.getAttribute('aria-selected') === 'true' || el.getAttribute('data-highlighted') != null
        || HL.test(typeof el.className === 'string' ? el.className : '');
      // a field inside a web component (MDN's search): its list lives in the same shadow root, or in the document
      const root = edit && edit.getRootNode && edit.getRootNode() !== document && edit.getRootNode().querySelectorAll ? edit.getRootNode() : null;
      const Q = (sel) => root ? [...root.querySelectorAll(sel), ...document.querySelectorAll(sel)] : [...document.querySelectorAll(sel)];
      const byId = (id) => (root && root.getElementById(id)) || document.getElementById(id);
      Q('[data-pb-sug]').forEach((e) => e.removeAttribute('data-pb-sug'));
      const give = (kind, els) => {
        const seen = new Set(), items = [];
        for (const el of els) { const t = txt(el); if (!t || t.length > 150 || seen.has(t)) continue; seen.add(t);
          el.setAttribute('data-pb-sug', String(items.length)); items.push({ i: items.length, t, hl: hl(el) }); if (items.length >= 30) break; }
        out.kind = kind; out.items = items; return out; };
      if (!edit) return out;
      if (edit.list && edit.list.options) {
        const os = [...edit.list.options].map((o) => o.label || o.value).filter(Boolean);
        out.kind = 'datalist'; out.items = os.slice(0, 30).map((t, i) => ({ i, t, hl: false })); return out;
      }
      const owner = edit.closest('[role=combobox]') || edit;
      for (const host of [edit, owner]) {
        for (const id of ((host.getAttribute('aria-controls') || '') + ' ' + (host.getAttribute('aria-owns') || '')).split(/\s+/)) {
          const c = id && byId(id);
          if (!c || !shown(c)) continue;
          let os = [...c.querySelectorAll('[role=option]')].filter(shown);
          if (!os.length) os = [...c.querySelectorAll('li')].filter(shown);
          if (os.length) return give('list', os);
        }
      }
      const r = edit.getBoundingClientRect(), dlg = edit.closest('[role=dialog],[aria-modal=true],dialog');
      const near = (el) => { if (dlg && dlg.contains(el)) return true; const q = el.getBoundingClientRect();
        return q.bottom >= r.top - 300 && q.top <= r.bottom + 500 && q.left < r.right + 300 && q.right > r.left - 300; };
      // an open listbox near the field, with entries that came after the typing began (not one left open elsewhere)
      const lb = Q('[role=listbox]').filter((l) => shown(l) && near(l))
        .map((l) => [...l.querySelectorAll('[role=option]')].filter(shown)).find((os) => os.length && os.some((o) => !pre.has(o)));
      if (lb) return give('listbox', lb);
      if (aria) return out;
      // new clickable entries: near the field (under it, or beside it) or in the dialog that holds it
      let els = Q(CAND).filter((el) => !pre.has(el) && !el.contains(edit) && shown(el) && txt(el));
      els = els.filter((el) => { if (dlg && dlg.contains(el)) return true; const q = el.getBoundingClientRect();
        return q.top >= r.top - 10 && q.top <= r.bottom + 500 && q.left < r.right + 300 && q.right > r.left - 300; });
      // one entry per suggestion: the outermost of nested candidates that show the same text
      els = els.filter((el) => !els.some((o) => o !== el && o.contains(el) && txt(o) === txt(el)));
      // plain entries with no role: often a box of text whose parent holds the click handler; keep the leaves of text
      if (!els.length) {
        const box = Q('div,span,p').filter((el) => !pre.has(el) && el.childElementCount === 0 && shown(el) && txt(el)
          && el !== edit && (() => { if (dlg && dlg.contains(el)) return true; const q = el.getBoundingClientRect();
            return q.top >= r.bottom - 5 && q.top <= r.bottom + 500 && q.left < r.right + 300 && q.right > r.left - 300; })());
        if (box.length && box.length <= 60) return give('new', box);
        return out;
      }
      return give('new', els);
    }"""

    @staticmethod
    def quote_arg(s):
        return s if re.fullmatch(r"[\w.@=#:/-]+", s) else '"' + s.replace('"', '\\"') + '"'

    async def sug_list(self, fr, aria=False):
        try:
            return await asyncio.wait_for(fr.evaluate(self.SUG_JS, ["list", aria]), 3) or {"kind": "", "items": []}
        except Exception:
            return {"kind": "", "items": [], "field": None}

    @staticmethod
    def sug_choose(items, want):
        """The suggestion that matches want: equal, then starting with it, then holding it; "1": the first one."""
        if want.strip() == "1":
            return items[0] if items else None
        w = re.sub(r"\s+", " ", fold(want)).strip()
        ts = [(re.sub(r"\s+", " ", fold(x["t"])).strip(), x) for x in items]
        for test in (lambda t: t == w, lambda t: t.startswith(w), lambda t: w in t):
            hit = next((x for t, x in ts if test(t)), None)
            if hit:
                return hit
        return None

    async def fill_pick(self, loc, it, st, value, want, label):
        """pb fill TARGET VALUE --pick [TEXT]: type with real keys, wait for the suggestion list of the field, pick the
        entry that matches, read the field back. -> answer line; Err when nothing fits (with what was seen)."""
        fr = self.refs[it["ref"]][0] if it.get("ref") in self.refs else self.page.main_frame
        with contextlib.suppress(Exception):
            await asyncio.wait_for(fr.evaluate(self.SUG_JS, ["mark", False]), 3)
        if st.get("off"):
            raise Err("that field is disabled, so nothing was typed")
        try:
            await loc.click(timeout=1500, no_wait_after=True)
        except Exception:
            await loc.focus(timeout=1500)
        # where the typing goes: the field itself, or an input the page opened for it (a dialog of its own). The box may
        # open a moment after the click (amtrak's station picker: "BOS" went into the field it hides, and no list came),
        # so the focus is watched for half a second; it goes on as soon as it has moved.
        moved = False
        eh = None
        with contextlib.suppress(Exception):
            eh = await loc.element_handle(timeout=1500)
        for k in range(5):
            await asyncio.sleep(0.1 if k else 0.15)
            with contextlib.suppress(Exception):
                moved = await fr.evaluate("""([e, last]) => { let a = document.activeElement; while (a && a.shadowRoot && a.shadowRoot.activeElement) a = a.shadowRoot.activeElement;
                    const ed = a && (a.tagName === 'INPUT' || a.tagName === 'TEXTAREA' || a.isContentEditable);
                    if (ed && a !== e && !e.contains(a)) return true; if (!ed && last) e.focus(); return false; }""", [eh, k == 4])
            if moved:
                break
            if k == 1:
                shows = True
                with contextlib.suppress(Exception):
                    shows = bool(eh) and await fr.evaluate("(e) => { const r = e.getBoundingClientRect(); return r.width > 2 && r.height > 2; }", eh)
                if shows:
                    break                          # the field is still there and shows: typing goes into it
        kb = self.page.keyboard
        await kb.press("Control+A")
        await kb.press("Delete")
        await kb.type(value, delay=35)
        sug, t0 = {"items": []}, time.time()
        with self.span("pick:wait list"):
            typed = re.sub(r"\s+", " ", fold(value)).strip()
            while time.time() - t0 < 3.5:
                await asyncio.sleep(0.15)
                sug = await self.sug_list(fr)
                if sug["items"]:
                    await asyncio.sleep(0.25)          # a list that is still filling in: one more look a moment later
                    sug = await self.sug_list(fr)
                    if not sug["items"]:
                        continue
                    # booking.com: the list shows its default places the moment the box has the focus, and the entries
                    # for what was typed most of a second later. A list that has the wanted entry, or that answers the
                    # typed text, is the one; any other list is given until 2.5 s to turn into it.
                    answers = any(typed and typed in re.sub(r"\s+", " ", fold(x["t"])) for x in sug["items"])
                    wanted = (want or value).strip() != "1" and self.sug_choose(sug["items"], want or value) is not None
                    if wanted or answers or time.time() - t0 > 2.5:
                        break
        items = sug["items"]
        into = " (typed into the box the page opened for it)" if moved else ""
        if not items:
            # the page may take a code by itself, with no list (amtrak: "BOS" became "From BOS Boston, MA South Station"
            # a moment later, while pb said no list appeared)
            await self.settle(max_s=1.5, react=0.4)
            self.scan = None
            with contextlib.suppress(Exception):
                after, _ = await self.collect()
                lw = fold(re.sub(r"\s+", " ", (it.get("t") or "")).strip())
                took = [x for x in after if "ref" in x and x["k"] in ("click", "button", "combo", "input")
                        and fold(x.get("t", "") + " " + str(x.get("v", ""))).startswith(lw) and re.search(r"(?<![^\W_])" + re.escape(fold(value)) + r"(?![^\W_])", fold(x.get("t", "") + " " + str(x.get("v", ""))))]
                if lw and took:
                    return f'ok fill {label} --pick: no list came, the page took "{value}" itself: now {self.line(took[0])}'
            raise Err(f'no suggestion list appeared after typing "{value}" into {label}{into}; the field holds "{sug.get("field") or ""}". '
                      "Try fewer letters, or pb view to see what the page shows")
        pick = self.sug_choose(items, want or value)
        if pick is None:
            seen = " | ".join(f'"{x["t"][:60]}"' for x in items[:10])
            raise Err(f'no suggestion matches "{want or value}" after typing "{value}"{into}. Suggestions seen: {seen}'
                      + (f" (+{len(items) - 10} more)" if len(items) > 10 else "") + ". Pick one: pb fill ... --pick \"TEXT\" (or --pick 1 for the first)")
        how, t_pick = "", time.time()
        if sug["kind"] == "datalist":
            # the browser draws a datalist's list itself: no page element to click. Set the value as choosing it does.
            await fr.evaluate("""(t) => { let a = document.activeElement; const o = [...a.list.options].find((o) => (o.label || o.value) === t);
                const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(a, o ? o.value : t);
                a.dispatchEvent(new Event('input', { bubbles: true })); a.dispatchEvent(new Event('change', { bubbles: true })); }""", pick["t"])
            how = "from the field's own list"
        else:
            # The keyboard first, where the list shows which entry the keys are on: a mouse click on a suggestion froze
            # a checkout page (advanceautoparts.com, the address list), the keys never did. Each press is checked
            # against the highlight, so the entry taken is the one asked for. A list that shows no highlight gets the
            # mouse.
            for k in range(len(items) + 1):
                cur = await self.sug_list(fr)
                hit = next((x for x in cur["items"] if x["hl"]), None)
                if hit and hit["t"] == pick["t"]:
                    await kb.press("Enter")
                    how = f"by keyboard ({k} x ArrowDown, then Enter on the highlighted entry)"
                    break
                if k >= 1 and not hit:
                    break                          # the keys move nothing this page shows
                await kb.press("ArrowDown")
                await asyncio.sleep(0.08)
            if not how:
                # (the list was read again after each key, which numbers its entries afresh: find the entry by its text)
                again = next((x for x in (await self.sug_list(fr))["items"] if x["t"] == pick["t"]), None)
                opt = fr.locator(f'[data-pb-sug="{(again or pick)["i"]}"]').first
                try:
                    await opt.click(timeout=1500, no_wait_after=True)
                    how = "by click"
                except Exception:
                    raise Err(f'"{pick["t"][:60]}" could be neither reached with the arrow keys nor clicked; nothing was picked')
        await self.settle(max_s=2.5, quiet=0.2, react=0.3)
        holds = None
        with contextlib.suppress(Exception):
            holds = await loc.evaluate("""(e) => { const v = e.value !== undefined ? e.value : (e.innerText || '');
                if (String(v).trim()) return String(v);
                let p = e.parentElement; for (let i = 0; i < 3 && p; i++, p = p.parentElement) { const t = (p.innerText || '').replace(/\\s+/g, ' ').trim(); if (t && t.length <= 80) return t; }
                return ''; }""", timeout=1500)
        line = f'ok fill {label} --pick: picked "{pick["t"][:80]}" {how}{into}'
        if holds is None:
            return line + (" (the page went on to another address)" if self.navigating(t_pick) else " (pb could not read the field back: look at the page)")
        still = False
        if fold(holds).strip() == fold(value).strip() and fold(pick["t"]) != fold(value) and not self.navigating(t_pick):
            # the field shows only what was typed: fine when the list closed (google shows the city name it chose),
            # not when the list still offers the entry (the click did not take)
            still = any(x["t"] == pick["t"] for x in (await self.sug_list(fr))["items"])
        if still:
            raise Err(f'{label} --pick: chose "{pick["t"][:80]}" {how}, but the list still offers it and the field holds only what was '
                      f'typed ("{holds[:80]}"). The page may want the entry chosen another way: pb view to see the list, then pb click on it')
        return line + f'; the field now holds "{holds[:100]}"'

    FIND_OPTION_JS = """(e, qs) => { const os = [...e.options];
        for (let q of qs) { q = q.toLowerCase();
          const o = os.find(o => o.textContent.trim().toLowerCase() === q) || os.find(o => o.value.toLowerCase() === q);
          if (o) return o.value; }
        const q = qs[0].toLowerCase();
        const o = os.find(o => o.textContent.trim().toLowerCase().startsWith(q)) || os.find(o => o.textContent.toLowerCase().includes(q));
        return o ? o.value : null; }"""

    # a range input set the way the page's own script would see it (the native setter, so frameworks notice), with
    # the events a person's drag fires
    RANGE_SET_JS = """(e, v) => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
        set.call(e, v); e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new Event('change', {bubbles: true}));
        return [e.value, e.min || '0', e.max || '100', e.step || '1']; }"""
    SLIDER_JS = "e => [parseFloat(e.getAttribute('aria-valuenow')), parseFloat(e.getAttribute('aria-valuemin')), parseFloat(e.getAttribute('aria-valuemax'))]"

    async def fill_special(self, loc, kind, value, label):
        """pb fill on a field that takes no typing: a range input, a custom slider, a date, time, month, week or color."""
        if kind in ("range", "slider"):
            try:
                want = float(value)
            except ValueError:
                raise Err(f"{label} is a slider: it takes a number, not {value!r}")
            if kind == "slider":
                return await self.do_slider(loc, want, label)
            got, lo, hi, step = await loc.evaluate(self.RANGE_SET_JS, value)
            if float(got) == want:
                return f"ok fill {label} -> {got}"
            return f'ok fill {label} (field now shows "{got}": the closest it takes; range {lo}-{hi}, step {step})'
        v = field_value(kind, value)
        if v is None:
            raise Err(f'"{value}" is not a {kind} pb can read, so nothing was filled. Give it as {VALUE_FORMATS[kind]}')
        await loc.fill(v, timeout=2000)
        got = await loc.input_value(timeout=1500)
        if got != v:
            return f'ok fill {label} (field now shows "{got}"' + ("; it refused " + v if not got else "") + ")"
        return f"ok fill {label}" + (f" ({value} -> {v})" if v != value else "")

    async def do_slider(self, loc, want, label):
        """A custom slider (role=slider) is moved as a person does it with the keyboard: Home / End for its ends, the
        arrow keys in between, until it shows the value or would go past it. A click on it would jump to wherever the
        mouse lands."""
        await loc.focus(timeout=1500)
        now, lo, hi = await loc.evaluate(self.SLIDER_JS)
        if now != now:                          # NaN: no aria-valuenow to read
            raise Err(f"{label} does not say its value (no aria-valuenow), so pb cannot tell where to move it. Use pb press ArrowRight / ArrowLeft")
        kb = self.page.keyboard
        if lo == lo and want <= lo:
            await kb.press("Home")
        elif hi == hi and want >= hi:
            await kb.press("End")
        else:
            for _ in range(400):
                if now == want:
                    break
                up = now < want
                await kb.press("ArrowRight" if up else "ArrowLeft")
                new = (await loc.evaluate(self.SLIDER_JS))[0]
                if new == now:
                    break                       # it does not move further (an end, or it ignores the keys)
                if (new > want) == up and new != want:
                    # gone past it: step back when the value before was closer
                    if abs(new - want) > abs(now - want):
                        await kb.press("ArrowLeft" if up else "ArrowRight")
                        new = (await loc.evaluate(self.SLIDER_JS))[0]
                    now = new
                    break
                now = new
        now = (await loc.evaluate(self.SLIDER_JS))[0]
        shown = int(now) if now == int(now) else now
        if now == want:
            return f"ok fill {label} -> {shown}"
        return f"ok fill {label}: got {shown}, the closest it goes to {int(want) if want == int(want) else want}"

    async def do_select(self, loc, it, option, st=None):
        if st is not None and st.get("gone"):
            raise Gone()
        tag = st["tag"] if st and st.get("tag") else await loc.evaluate("e => e.tagName", timeout=2500)
        if isinstance(option, list):
            # several words or quoted options: on a <select multiple> each one is an option of its own
            if tag == "SELECT" and await loc.evaluate("e => e.multiple", timeout=1500):
                vals = [await loc.evaluate(self.FIND_OPTION_JS, [o] + state_alts(o)) for o in option]
                if None in vals:
                    one = await loc.evaluate(self.FIND_OPTION_JS, [" ".join(option)])
                    if one is None:
                        raise Err(f'no option like "{option[vals.index(None)]}" in that list')
                    vals = [one]
                await loc.select_option(value=vals, timeout=1500)
                return ", ".join(await loc.evaluate("e => [...e.selectedOptions].map(o => o.textContent.trim())"))
            option = " ".join(option)
        # A US state may be listed by name or by code, and callers give either ("Massachusetts" failed where "MA"
        # worked on dollargeneral and lego, and the other way round elsewhere): the other form is tried as well.
        alts = [option] + state_alts(option)
        if tag == "SELECT":
            # find the option in the page first (exact text, value, then prefix, then substring): asking Playwright for
            # a label that is not exactly there costs its whole timeout. A state's other form is tried by exact text
            # and value only ("MA" is inside many names).
            val = await loc.evaluate(self.FIND_OPTION_JS, alts)
            if val is None:
                raise Err(f'no option like "{option}" in that select')
            try:
                if st is not None and not st.get("vis", True):
                    raise Exception("not shown")       # Playwright would wait 1.5 s for it to show before saying so
                await loc.select_option(value=val, timeout=1500)
            except Exception:
                # a native select hidden behind a styled one: set it the way the page's own script would
                await loc.evaluate("""(e, v) => { e.value = v; e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new Event('change', {bubbles: true})); }""", val)
            # a short limit: a page that replaces the select after the change would hold this for the default 30 s
            return await loc.evaluate("e => e.selectedOptions[0] ? e.selectedOptions[0].textContent.trim() : ''", timeout=1500)
        # custom dropdown: open it, type to filter, pick the matching option as soon as it shows up
        with self.span("select:open"):
            await self.do_click(loc, it, st)
            await asyncio.sleep(0.1)
        picked, n = False, 0
        fr = self.refs[it["ref"]][0] if it.get("ref") in self.refs else self.page.main_frame      # options render next to their control
        cand = fr.locator('[role=option], [id*="option"], li').filter(
            has_text=re.compile(r"^\s*(?:" + "|".join(re.escape(x) for x in alts) + r")\s*$", re.I))
        with contextlib.suppress(Exception):
            n = await asyncio.wait_for(cand.count(), 1.0)          # the list may already show the option: no typing needed
        # Typing filters the list, but only into the dropdown itself. One that cannot take focus leaves the focus where
        # it was, often in the text box next to it (hobbylobby: "MAMassachusetts" typed into the address line).
        where = "none"
        with contextlib.suppress(Exception):
            where = await loc.evaluate(self.FOCUS_IN_JS, timeout=1000)
        typed_into, old_val = None, None
        if not n and where != "other":
            with contextlib.suppress(Exception):
                old_val = await fr.evaluate("() => { const a = document.activeElement; return a && 'value' in a ? String(a.value) : null; }")
            with self.span("select:type"):
                await self.page.keyboard.type(option, delay=15)
            typed_into = where
        with self.span("select:find"):
            t0 = time.time()
            while not n and time.time() - t0 < 1.5:
                try:
                    n = await asyncio.wait_for(cand.count(), 1.0)
                except Exception:
                    n = 0
                if n:
                    break
                await asyncio.sleep(0.08)
        if n:
            with self.span("select:pick"):
                if where == "in":
                    picked = await self.pick_option_by_keyboard(cand.first)
                if not picked:
                    with contextlib.suppress(Exception):
                        await cand.first.click(timeout=1500)
                        picked = True
        if not picked and typed_into:
            await self.page.keyboard.press("Enter")
        await asyncio.sleep(0.05)
        shown = ""
        with contextlib.suppress(Exception):
            shown = await loc.evaluate("""e => { let p = e; for (let i = 0; i < 4 && p.parentElement; i++) { p = p.parentElement; if ((p.innerText || '').trim()) break; }
                                                 return (p.innerText || e.value || '').replace(/\\s+/g, ' ').trim().slice(0, 60); }""")
        if not picked and option.lower() not in shown.lower():
            if typed_into and old_val is not None:
                # nothing was chosen: take back what was typed, so the field does not keep a half-typed state name
                with contextlib.suppress(Exception):
                    await fr.evaluate("""(v) => { const a = document.activeElement; if (!a || !('value' in a)) return;
                        const set = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(a), 'value');
                        if (set && set.set) set.set.call(a, v); else a.value = v;
                        a.dispatchEvent(new Event('input', {bubbles: true})); }""", old_val)
            with contextlib.suppress(Exception):
                await self.page.keyboard.press("Escape")
            raise Err(f'no option "{option}" found in that dropdown (it showed: "{shown}"). Open it with pb click and read the options')
        return shown

    # a date picker that shows now (bootstrap's .datepicker, a calendar grid)
    PICKER_JS = """() => [...document.querySelectorAll('[class*="datepicker" i],[class*="calendar" i],[id*="datepicker" i],[role=grid]')].slice(0, 12)
        .some((e) => { const r = e.getBoundingClientRect(); return r.width > 40 && r.height > 40 && (!e.checkVisibility || e.checkVisibility({ checkVisibilityCSS: true })); })"""

    # The calendars that show: picker boxes, grids, dialogs that hold a grid of days. -> [count, text of a button that
    # closes one ("Done", "Close", "Apply") or '']
    PICKERS_JS = r"""() => {
      const shown = (e) => { const r = e.getBoundingClientRect(); return r.width > 40 && r.height > 40 && (!e.checkVisibility || e.checkVisibility({ checkVisibilityCSS: true })); };
      const isDlg = (e) => e.tagName === 'DIALOG' || /dialog/.test(e.getAttribute('role') || '') || e.getAttribute('aria-modal') === 'true';
      const cal = (e) => !!e.querySelector('[role=grid],table,[class*="calendar" i],[class*="datepicker" i]');
      const boxes = [...document.querySelectorAll('[class*="datepicker" i],[class*="calendar" i],[id*="datepicker" i],[role=grid],[role=dialog],[aria-modal=true],dialog[open]')]
        .slice(0, 400).filter(e => shown(e) && (!isDlg(e) || cal(e))).slice(0, 150);
      // (all of them, nested ones too: a box named "datePickerContainer" around the whole form holds the calendar that
      // opens, demoqa.com; the number goes up when one opens)
      let close = '';
      for (const b of boxes.filter(b => !b.querySelector('input,textarea'))) for (const x of b.querySelectorAll('button,[role=button]')) {
        const t = (x.innerText || x.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim();
        if (/^(done|close|apply|ok|select)\b/i.test(t)) { close = t.slice(0, 30); break; }
      }
      return [boxes.length, close];
    }"""

    async def close_left_picker(self, fr, loc, label, before, value_before):
        """After a fill of a date: a calendar the fill opened and left open covers what comes next (Google Flights: the
        next click, on Search, only closed it). Closed with Escape typed in the field when that keeps the date; else
        a NOTE says it is open and what closes it. Returns a few words for the ok line, or ''."""
        # (a calendar that opens when the next field gets the focus comes a moment after the Tab: demoqa.com)
        t0 = time.time()
        while True:
            try:
                n, close = await asyncio.wait_for(fr.evaluate(self.PICKERS_JS), 2)
            except Exception:
                return ""
            if n > before or time.time() - t0 > 0.5:
                break
            await asyncio.sleep(0.12)
        if n <= before:
            return ""
        # Escape where the keyboard is now (the field was left with Tab: going back into it may open the calendar
        # again), then, if that did not close it, in the field itself
        n2, close2 = n, close
        for press in (lambda: self.page.keyboard.press("Escape"), lambda: loc.press("Escape", timeout=1500)):
            with contextlib.suppress(Exception):
                await press()
            await self.settle(max_s=1.0, quiet=0.15, react=0.25, net=False)
            with contextlib.suppress(Exception):
                n2, close2 = await asyncio.wait_for(fr.evaluate(self.PICKERS_JS), 2)
            if n2 <= before:
                break
        now = value_before
        with contextlib.suppress(Exception):
            now = await loc.input_value(timeout=1000)
        if n2 <= before and (now or "") == (value_before or ""):
            return " (closed the calendar the fill left open, with Escape)"
        if n2 <= before:
            # Escape closed it but took the typed date with it: type it once more and leave the calendar be
            with contextlib.suppress(Exception):
                await loc.fill(value_before or "", timeout=1500)
            await self.settle(max_s=1.0, quiet=0.15, react=0.25, net=False)
        how = f'its "{close2 or close}" button' if (close2 or close) else "pb press Escape, or a click on the field's label"
        self.notes.append(f"a calendar is still open after the fill of {label}: it covers part of the page and may take the next "
                          f"click. Close it first ({how})")
        return ""

    async def leave_date_field(self, loc, value, label, actual):
        """After typing a date into a text field: leave it with Tab, as a person does (amtrak took the date only then),
        and read it back after the blur. A picker that keeps only dates chosen in its calendar empties the field then
        (selenium.dev's bootstrap datepicker): that is an error, with the way on."""
        with contextlib.suppress(Exception):
            await self.page.keyboard.press("Tab")
        await self.settle(max_s=1.5, quiet=0.15, react=0.2)
        now = actual
        with contextlib.suppress(Exception):
            now = await loc.input_value(timeout=1500)
        digits = lambda s: re.sub(r"\D", "", s or "")
        if now is not None and value.strip() and (not now.strip() or (digits(value) and digits(now) != digits(value)
                                                  and not digits(now).startswith(digits(value)) and not same_date(value, now))):
            ex = 'pb click 15 --near "January 2027"'
            iso = field_value("date", value)
            if iso:
                import datetime as dt
                d = dt.date.fromisoformat(iso)
                ex = f'pb click {d.day} --near "{d.strftime("%B %Y")}"'
            raise Err(f'{label}: the page threw the typed date away when the field was left (it now holds "{now}"). It takes dates '
                      f"from its calendar: click the field, then pick the day in the calendar: {ex}")
        return now

    async def select_took(self, cmd, loc, it, a, purpose, near):
        """saucedemo's sort: `fill "Sort products" "Price (low to high)"` (or select) chose the option, the page re-rendered
        the dropdown at once, and pb tried again until it gave up ("keeps replacing that element") while the sort had
        applied. When the dropdown pb acted on is gone and the new one shows the option asked for: ok, as lines."""
        if cmd not in ("fill", "select") or len(a) < 2 or (it or {}).get("k") not in ("select", "combo", "css", None):
            return None
        shown = None
        with contextlib.suppress(Exception):
            shown = await self.replaced_select_shows(loc, it, a, purpose, near)
        if not shown:
            return None
        await self.settle(max_s=2, react=0.3)
        return [f'ok {cmd} {it.get("ref", "")} select "{it.get("t", "")}" -> shows "{shown}" (the page re-rendered the dropdown '
                "after the choice; the new one shows it)"]

    async def replaced_select_shows(self, loc, it, a, purpose, near):
        """After a select whose element the page replaced: what the field shows now when that is the option asked for,
        else None (the choice may not have gone in: the usual retry follows)."""
        with contextlib.suppress(Exception):
            if await asyncio.wait_for(loc.count(), 2) > 0:
                return None                     # not replaced: some other failure
        try:
            await asyncio.sleep(0.1)
            nloc, _ = await self.refind(a[0], it, purpose, near)
        except Exception:
            nloc = None
        if nloc is None:
            return None
        shown = ""
        with contextlib.suppress(Exception):
            shown = await nloc.evaluate("e => e.selectedOptions ? (e.selectedOptions[0] ? e.selectedOptions[0].textContent.trim() : '') "
                                        ": (e.value || e.innerText || '').trim()", timeout=1500)
        want = [fold(x) for x in ([" ".join(a[1:])] + state_alts(" ".join(a[1:])))]
        return shown if shown and any(w == fold(shown) or w in fold(shown) for w in want) else None

    # A target for fill that is no field at all: a form, a list, a section, or a box that holds several fields. -> its
    # tag in words, or '' when typing at it is reasonable (a custom field, a wrapper of one field, a label)
    NOT_FIELD_JS = """(e) => { const role = (e.getAttribute('role') || '').toLowerCase();
        if (e.isContentEditable || /^(textbox|combobox|searchbox|spinbutton|slider|listbox)$/.test(role)) return '';
        const tag = e.tagName;
        const n = e.querySelectorAll('input:not([type=hidden]),textarea,select,[contenteditable=true]').length;
        if (/^(FORM|FIELDSET|TABLE|TBODY|UL|OL|SECTION|MAIN|ARTICLE|NAV|HEADER|FOOTER|ASIDE|BODY|HTML)$/.test(tag) || n >= 2)
          return tag + (e.id ? ' (#' + e.id + ')' : '') + (n ? ' holding ' + n + ' field' + (n > 1 ? 's' : '') : '');
        return ''; }"""

    async def do_mouse_click(self, loc, st, button):
        """pb click --right | --double: real mouse events (contextmenu, dblclick). -> the kind, for the answer."""
        if st.get("gone"):
            raise Gone()
        if not st.get("vis"):
            raise Err("that element is not shown, so no mouse can reach it for a right-click or double-click. Bring it into view first")
        kind = "right-click" if button == "right" else "double-click"
        try:
            if button == "right":
                await loc.click(button="right", timeout=2500, no_wait_after=True)
            else:
                await loc.dblclick(timeout=2500, no_wait_after=True)
        except Exception:
            # covered (a transparent layer): the mouse goes to the element's center anyway, as a person's would
            box = await loc.bounding_box(timeout=1000)
            if not box:
                raise
            x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            if button == "right":
                await self.page.mouse.click(x, y, button="right")
            else:
                await self.page.mouse.dblclick(x, y)
            kind += " (at its center)"
        return kind

    # Where the focus is after a click on a custom dropdown: 'in' the dropdown (itself, inside it, its list, or a popup
    # list), 'other' another text field, 'none' nowhere in particular (the page body).
    FOCUS_IN_JS = """(el) => { let a = document.activeElement; while (a && a.shadowRoot && a.shadowRoot.activeElement) a = a.shadowRoot.activeElement;
        if (!a || a === document.body || a === document.documentElement) return 'none';
        if (a === el || el.contains(a) || a.contains(el)) return 'in';
        for (const id of ((el.getAttribute('aria-controls') || '') + ' ' + (el.getAttribute('aria-owns') || '')).split(/\\s+/)) {
          const c = id && document.getElementById(id); if (c && c.contains(a)) return 'in'; }
        if (a.closest('[role=listbox],[role=menu],[role=dialog]')) return 'in';
        const ctl = a.getAttribute('aria-controls'); if (ctl && el.closest('#' + CSS.escape(ctl))) return 'in';
        return (a.tagName === 'INPUT' || a.tagName === 'TEXTAREA' || a.isContentEditable) ? 'other' : 'none'; }"""

    # ---- secrets
    def secret(self, key):
        data = parse_secrets(self.secrets_path)
        sec, _, field = key.partition(".")
        sec = {"card": "card1"}.get(sec.lower(), sec.lower())
        d = data.get(sec)
        if d is None:
            raise Err(f"no [{sec}] section in the secrets file (its sections: {', '.join(data) or 'none'})")
        alias = {"number": ["card", "number"], "cvc": ["cvv", "cvc", "ccv"], "cvv": ["cvv", "cvc", "ccv"], "exp": ["expiration", "expiry", "exp"],
                 "name": ["name"], "zip": ["billing zip", "zip"]}
        if field in ("exp_month", "exp_year"):
            exp = next((d[k] for k in alias["exp"] if k in d), "")
            m = re.match(r"\s*(\d{1,2})\s*/\s*(\d{2,4})", exp)
            if not m:
                raise Err("card expiry not in MM/YY form")
            return m.group(1).zfill(2) if field == "exp_month" else m.group(2)[-2:]
        for k in alias.get(field, [field]):
            if k in d:
                v = d[k]
                return re.sub(r"\D", "", v) if field in ("number", "cvc", "cvv") else v
        raise Err(f"no '{field}' in [{sec}]")

    def card_sections(self):
        """Names of the secrets-file sections that hold a card. Names only: callers print them."""
        try:
            data = parse_secrets(self.secrets_path)
        except Exception:
            return []
        return [s for s, d in data.items() if "card" in d or "number" in d]

    def card_usage(self):
        return ("pb card [SECTION] types a card from the secrets file into the card fields of the page (payment frames "
                f"included). SECTION is a card section of the secrets file, default card1; this one has: {', '.join(self.card_sections()) or 'none'}. "
                "It is not a field of the page: to fill one field use pb secret TARGET card.number|card.exp|card.exp_month|card.exp_year|card.cvc|card.name")

    async def clear_field(self, loc):
        """Empty the focused input before typing into it. Select-all and Delete first; masked card fields that ignore
        select-all (macys kept its old digits and the new ones were added to them) get one Backspace per character."""
        kb = self.page.keyboard
        await kb.press("Control+A")
        await kb.press("Delete")
        got = ""
        with contextlib.suppress(Exception):
            got = await loc.input_value(timeout=1000)
        if got:
            await kb.press("End")
            for _ in range(len(got) + 1):
                await kb.press("Backspace")
            with contextlib.suppress(Exception):
                if await loc.input_value(timeout=1000):
                    await loc.fill("", timeout=1000)

    async def pick_exp(self, loc, part, mm, yy, wait=0.0):
        """Select the card's month (part "month") or year ("year"; "" = judge by the options) in an expiry <select>, then
        read the choice back. Returns (True, "month"|"year") or (False, why not). Never says which month or year."""
        r = await loc.evaluate(PICK_JS, [part, mm, yy], timeout=2000)
        t0 = time.time()
        while r["dis"] and time.time() - t0 < wait:
            await asyncio.sleep(0.2)
            r = await loc.evaluate(PICK_JS, [part, mm, yy], timeout=2000)
        what = r["kind"] or "month or year"
        if r["dis"]:
            return False, f"the {what} list stayed disabled (shops enable it once they accept the card number)"
        if not r["kind"]:
            return False, "this list holds neither months nor years"
        if r["i"] < 0:
            return False, f"the {what} list has no option for the card's {what}"
        try:
            await loc.select_option(index=r["i"], timeout=2000)
        except Exception:
            # a select the page keeps behind its own dropdown: set it the way the page's script would
            await loc.evaluate("(e, i) => { e.selectedIndex = i; e.dispatchEvent(new Event('input', {bubbles: true})); "
                               "e.dispatchEvent(new Event('change', {bubbles: true})); }", r["i"], timeout=2000)
        r2 = await loc.evaluate(PICK_JS, [r["kind"], mm, yy], timeout=2000)
        if r2["sel"] != r["i"]:
            return False, f"the {what} list did not keep the choice"
        return True, r["kind"]

    async def secret_into(self, loc, key, label, fr=None):
        """pb secret: put one value from the secrets file into one field and say honestly whether it is there.
        fr: the frame the field is in (the main frame when not given)."""
        sec, _, field = key.partition(".")
        if field != "name" and {"card": "card1"}.get(sec.lower(), sec.lower()) in self.card_sections():
            self.card_allowed("card data")
        tag = ""
        with contextlib.suppress(Exception):
            tag = await loc.evaluate("e => e.tagName", timeout=2500)
        if tag == "SELECT":
            # chewy, nordstrom: an expiry month or year list. Typing into a select changes nothing, so pick the option.
            if field not in ("exp", "expiry", "expiration", "exp_month", "exp_year"):
                raise Err(f"{label} is a dropdown: pb secret picks only an expiry month or year in one (card.exp, card.exp_month, "
                          "card.exp_year). Nothing was selected")
            mm, yy = int(self.secret(f"{sec}.exp_month")), int(self.secret(f"{sec}.exp_year"))
            ok, why = await self.pick_exp(loc, {"exp_month": "month", "exp_year": "year"}.get(field, ""), mm, yy, wait=3)
            if not ok:
                raise Err(f"nothing was selected in {label}: {why}")
            with contextlib.suppress(Exception):
                await loc.evaluate(self.MARK_SECRET, timeout=1500)
            return f"ok secret {key} selected the card's {why} in {label}"
        value = self.secret(key)
        if not key.startswith("buyer.") and field != "name":
            with contextlib.suppress(Exception):           # from now on every view and screenshot hides this field
                await loc.evaluate(self.MARK_SECRET, timeout=1500)
        digits = len(value) if field in ("number", "cvc", "cvv") else 0

        fr = fr or self.page.main_frame

        async def type_it(delay):
            st = await self.look(loc)
            if st.get("gone"):
                raise Gone()
            if st["cover"] or not st["vis"]:
                # a label or icon lies over the input (jcpenney's CVV): keyboard focus needs no clear line of sight,
                # and a mouse click would wait out its limit for the cover to go away
                await loc.focus(timeout=1200)
            else:
                try:
                    await loc.click(timeout=1200, no_wait_after=True)
                except Exception:
                    await loc.focus(timeout=1200)
            if not await self.focus_in(fr, loc):
                # what is typed now would land wherever the focus is, after select-all and Delete have emptied that
                raise Err(f"the keyboard focus does not go into {label}, so nothing was typed. Click the field first (pb click), "
                          "or check that it is the field you mean (pb view)")
            await self.clear_field(loc)
            await loc.press_sequentially(value, delay=delay, timeout=10000)
            got = None
            with contextlib.suppress(Exception):
                got = await loc.input_value(timeout=1500)
            if got is None:             # not an input (an editable div): nothing to read back
                return True, ""
            n = len(re.sub(r"\D", "", got))
            if digits:
                return n == digits or (n == 0 and len(got) >= digits), f"the field holds {n} digits instead of {digits}"
            return bool(got), "the field is still empty"

        ok, why = await type_it(12)
        if not ok:
            ok, why = await type_it(45)
        if not ok:
            raise Err(f"typed {key} into {label} twice, but {why}")
        return f"ok secret {key} typed into {label} ({len(value)} chars)"

    FOCUS_JS = "e => { let a = document.activeElement; while (a && a.shadowRoot && a.shadowRoot.activeElement) a = a.shadowRoot.activeElement; return a === e; }"
    # the element of the main document that holds the focus: [tag, frame stamp]
    FOCUS_TOP_JS = ("() => { let a = document.activeElement; while (a && a.shadowRoot && a.shadowRoot.activeElement) a = a.shadowRoot.activeElement; "
                    "return a ? [a.tagName, a.getAttribute('data-pbf') || ''] : ['', '']; }")

    async def focus_in(self, fr, loc):
        """Is the keyboard focus in this element, so that what is typed now lands in it? The element must hold the
        focus of its document, and for an element in a frame the page's focus must be in that frame: there the main
        document names the frame element as its focused element. (Whether the window is in front does not matter,
        and is not asked: keys sent by pb go to the page's focused element either way.)"""
        try:
            if not await loc.evaluate(self.FOCUS_JS, timeout=1000):
                return False
        except Exception:
            return False
        main = self.page.main_frame
        if fr is main:
            return True
        top = fr
        while top.parent_frame is not None and top.parent_frame is not main:
            top = top.parent_frame
        stamp = next((k for k, v in self.fmap.items() if v is top), "")
        try:
            tag, at = await asyncio.wait_for(main.evaluate(self.FOCUS_TOP_JS), 1)
        except Exception:
            return True                # the main document does not answer: the frame's own word stands
        if tag in ("IFRAME", "FRAME"):
            return not stamp or not at or at == stamp
        # a frame inside a web component shows as that component; anything else of the page holding the focus (its
        # body, one of its own fields) means the focus is not in the frame
        return "-" in tag

    async def do_card(self, section):
        """Types the card into the page, waits a moment and reads the fields back. Returns (answer, complete): complete
        is False when the number, the expiry or the security code was not found, did not end up in its field or did
        not stay there."""
        sec = {"card": "card1"}.get((section or "card1").lower(), (section or "card1").lower())
        if sec not in self.card_sections():
            raise Err(f'no card section "{section}" in the secrets file. ' + self.card_usage())
        self.card_allowed("a card")
        number, cvc = self.secret(f"{sec}.number"), self.secret(f"{sec}.cvc")
        mm, yy = self.secret(f"{sec}.exp_month"), self.secret(f"{sec}.exp_year")
        name = ""
        with contextlib.suppress(Err):
            name = self.secret(f"{sec}.name")
        main = self.page.main_frame
        PARTS = ["number", "cvc", "exp", "exp_month", "exp_year", "name"]

        async def discover():
            cands = []   # (score, part, order, frame, id, host, info)
            with self.span("card:find"):
                shown = await self.visible_frames()
                # Frames that do not show (0x0 for now, or behind a frame element Chrome could not name in time:
                # acehardware) are searched too, but a field in one only counts when no shown frame has one for that part.
                rest = [fr for fr in self.page.frames if fr is not main and fr not in shown and not fr.is_detached() and fr.url
                        and not TRACKERS.search(fr.url.split("?")[0])]
                frames = [main] + shown + rest

                async def fields(fr):
                    try:
                        return await asyncio.wait_for(fr.evaluate(CARD_JS), 3)
                    except Exception:
                        return []

                per_frame = await asyncio.gather(*(fields(fr) for fr in frames))
            order = 0
            for fr, fs in zip(frames, per_frame):
                host = "" if fr is main else host_of(fr.url)
                psp = 30 if (host and PSP_HOSTS.search(host)) else 0
                hidden = -60 if fr in rest else 0
                for c in fs:
                    order += 1
                    c["hidden_frame"] = fr in rest
                    blob = " ".join([c["name"], c["eid"], c["ph"], c["lab"], c["dft"]])
                    if NOT_CARD.search(blob) and not c["ac"].startswith("cc-"):
                        continue
                    sc = {}
                    ac = c["ac"]
                    if c["tag"] == "SELECT":
                        # a select on a card form is only ever the expiry month or year, and its options say which
                        kind = "month" if ac == "cc-exp-month" else "year" if ac == "cc-exp-year" else c.get("kind")
                        if kind in ("month", "year") and not re.search(r"birth|dob|born", blob, re.I):
                            cands.append(((100 if ac.startswith("cc-exp-") else 85) + psp + hidden, "exp_" + kind, order, fr, c["id"], host, c))
                        continue
                    if ac == "cc-number" or re.search(r"card.?number|cardnumber|credit.?card.?n|cc.?num|encryptedcardnumber|^number$|card.?no\b", blob, re.I):
                        sc["number"] = 100 if ac == "cc-number" else 70
                    if ac == "cc-csc" or re.search(r"cvv|cvc|csc|security.?code|securitycode|verification|\bcid\b", blob, re.I):
                        sc["cvc"] = 100 if ac == "cc-csc" else 70
                    if ac == "cc-exp" or re.search(r"exp(iry|iration)?(.?date)?$|expir|exp[\s_.-]?(date|month|year|mm|yy|mo|yr)|mm\s*/\s*yy|valid.?thru|"
                                                   r"encryptedexpirydate", blob, re.I):
                        if ac == "cc-exp-month" or re.search(r"month", blob, re.I) and not re.search(r"year|yy", blob, re.I):
                            sc["exp_month"] = 80
                        elif ac == "cc-exp-year" or re.search(r"year", blob, re.I) and not re.search(r"month|mm", blob, re.I):
                            sc["exp_year"] = 80
                        else:
                            sc["exp"] = 100 if ac == "cc-exp" else 70
                    if ac == "cc-exp-month":
                        sc["exp_month"] = 100
                    if ac == "cc-exp-year":
                        sc["exp_year"] = 100
                    # The name needs evidence of its own, and a field that reads as the number, the expiry or the
                    # security code is never the name field as well (a label may speak of both: "Expiry date, as
                    # printed below the cardholder name"). Being in a payment frame is evidence for a number or a code,
                    # not for a name: petsmart's and ulta's frames got the name typed into one of their fields.
                    if not sc and (ac == "cc-name" or re.search(r"name.?on.?card|card.?holder|cardholder|cc.?name", blob, re.I)):
                        sc["name"] = 100 if ac == "cc-name" else 70
                    for part, s in sc.items():
                        cands.append((s + hidden + (0 if part == "name" else psp), part, order, fr, c["id"], host, c))
            # One field, one part: the surest pairs first, each field and each part given once.
            found, used = {}, set()
            for s, part, _, fr, cid, host, c in sorted(cands, key=lambda x: (-x[0], PARTS.index(x[1]), x[2])):
                if part not in found and (fr, cid) not in used:
                    found[part] = (s, fr, cid, host, c)
                    used.add((fr, cid))
            return found

        found = await discover()
        report, done = [], {}       # done: role -> True when the value is confirmed in its field
        typed = {}                  # role -> (locator, digits it must hold or None for a list, where it is)

        mask_chars = "*xX#" + chr(0x2022) + chr(0x25cf) + chr(0xb7) + chr(0x2219) + chr(0x25e6)

        def holds(got, digits_expected):
            """Does the field hold what was typed, judged by what can be read back? Digits where it shows them. Some
            fields show only dots, and some hide a card number once the field is left, keeping its last four digits
            behind bullets or stars: that is still the number that was typed, not an emptied field."""
            got = got or ""
            n = len(re.sub(r"\D", "", got))
            if not digits_expected:
                return bool(got), len(got)
            if n == digits_expected:
                return True, n
            compact = re.sub(r"[\s-]", "", got)
            masked = (len(compact) >= digits_expected and n <= 4 and any(ch in mask_chars for ch in compact)
                      and all(ch in mask_chars or ch.isdigit() for ch in compact))
            return masked or (n == 0 and len(got) >= digits_expected), n

        async def put(role, value, digits_expected=None, again=False):
            if role not in found:
                return False
            _, fr, cid, host, info = found[role]
            loc = fr.locator(f'[data-pbc="{cid}"]').first
            where = (f" [frame {host}" + (", hidden" if info.get("hidden_frame") else "") + "]") if host else ""
            try:
                if info["tag"] == "SELECT":
                    with self.span("card:" + role):
                        ok, why = await self.pick_exp(loc, role[4:], int(mm), int(yy))
                    with contextlib.suppress(Exception):       # views and screenshots hide the choice from now on
                        await loc.evaluate(self.MARK_SECRET, timeout=1500)
                    report.append(f"{role} ok{where}" if ok else f"{role} FAILED{where}: {why}")
                    done[role] = ok
                    if ok:
                        typed[role] = (loc, None, where, None, fr)
                    return ok

                async def type_it(delay):
                    # the look also tags the field: from now on every view and screenshot hides it (not the name)
                    st = await self.look(loc, mark=role != "name")
                    if st.get("gone") or not st["vis"]:
                        raise Exception("the field is not visible")
                    if st.get("unknown") and role != "name":
                        with contextlib.suppress(Exception):
                            await loc.evaluate(self.MARK_SECRET, timeout=1500)
                    if st["cover"]:
                        # A floating label or an icon lies over the input (common on card forms). A mouse click would
                        # wait for it to move away, which it never does (3 s a field on ikea and jcpenney, twice).
                        # Keyboard focus needs no clear line of sight.
                        await loc.focus(timeout=900)
                    else:
                        try:
                            await loc.click(timeout=900, no_wait_after=True)
                        except Exception:
                            await loc.focus(timeout=900)
                    if not await self.focus_in(fr, loc):
                        with contextlib.suppress(Exception):
                            await loc.focus(timeout=900)
                        if not await self.focus_in(fr, loc):
                            # What is typed now would land wherever the focus is: in another field of the card, most
                            # likely, after select-all and Delete have emptied it. Nothing is typed.
                            return None, 0
                    if st.get("vlen") != 0:                 # an empty field needs no emptying (five round trips)
                        await self.clear_field(loc)
                    await loc.press_sequentially(value, delay=delay, timeout=10000)
                    got = ""
                    with contextlib.suppress(Exception):
                        got = await loc.input_value(timeout=1500)
                    return holds(got, digits_expected)

                with self.span("card:" + role):
                    ok, n = await type_it(12)
                    if ok is False:                 # a formatter dropped keys typed that fast, or old digits stayed: once more, slowly
                        ok, n = await type_it(45)
                if ok:
                    report.append(f"{role} ok{where}")
                    typed[role] = (loc, digits_expected, where, value, fr)
                elif ok is None:
                    report.append(f"{role} FAILED{where}: the keyboard focus does not go into the field, so nothing was typed")
                elif digits_expected:
                    report.append(f"{role} FAILED{where}: typed twice, the field holds {n} digits instead of {digits_expected}")
                else:
                    report.append(f"{role} FAILED{where}: typed twice, the field stayed empty")
                done[role] = bool(ok)
                return bool(ok)
            except Exception as e:
                if not again:
                    # payment widgets rebuild their frames while you type (the brand is recognised, a field is added):
                    # look for the fields once more and try this one again
                    found.clear()
                    found.update(await discover())
                    return await put(role, value, digits_expected, again=True)
                report.append(f"{role} FAILED{where}: {str(e).splitlines()[0][:80]}")
                done[role] = False
                return False

        async def wake():
            """macys: month and year stay disabled until the number field is left. Leave it the way a person does (Tab),
            then give the page a few seconds to enable them."""
            sels = [r for r in ("exp_month", "exp_year") if r in found and found[r][4]["tag"] == "SELECT" and found[r][4].get("dis")]
            if not sels:
                return
            with self.span("card:wake"), contextlib.suppress(Exception):
                await self.page.keyboard.press("Tab")
                t0, blurred = time.time(), False
                while time.time() - t0 < 4:
                    await asyncio.sleep(0.2)
                    off = []
                    for r in sels:
                        _, fr, cid, _, _ = found[r]
                        off.append(await fr.locator(f'[data-pbc="{cid}"]').first.evaluate("e => e.disabled", timeout=1000))
                    if not any(off):
                        return
                    if not blurred and time.time() - t0 > 1.5 and "number" in found:
                        blurred = True        # Tab may have gone nowhere (focus was never in the field): blur it directly
                        _, fr, cid, _, _ = found["number"]
                        await fr.locator(f'[data-pbc="{cid}"]').first.evaluate("e => e.blur()", timeout=1000)

        def year_for(role):
            """A year input that wants four digits (maxlength 4, YYYY) gets 20YY."""
            c = found[role][4]
            return "20" + yy if c.get("ml") == 4 or re.search(r"yyyy", c["ph"] + " " + c["lab"], re.I) else yy

        async def late_fields():
            """jcpenney shows the expiry and the code only once the number is in, macys enables its code field only then:
            a search made before the number was typed did not see them ("NOT FOUND: cvc, exp"). Search again for the
            parts still missing, for up to 3 s; after the first look, leave the number field as a person would (some
            forms wait for that). Costs nothing on a form that showed every part from the start."""
            def lacking():
                return "cvc" not in found or not any(p in found for p in ("exp", "exp_month", "exp_year"))
            with self.span("card:late fields"):
                t0, left = time.time(), False
                while lacking() and time.time() - t0 < 3:
                    await asyncio.sleep(0.3)
                    used = {(v[1], v[2]) for v in found.values()}
                    for part, v in (await discover()).items():
                        if part not in found and (v[1], v[2]) not in used:
                            found[part] = v
                            used.add((v[1], v[2]))
                    if lacking() and not left and "number" in typed:
                        left = True
                        with contextlib.suppress(Exception):
                            await typed["number"][0].evaluate("e => e.blur()", timeout=1000)

        await put("number", number, len(number))
        if done.get("number"):
            await late_fields()
        exp_line = None             # index in report of the line about the expiry
        if "exp" in found:
            ok = await put("exp", mm + yy, 4)
            if not ok:
                report.pop()
                await put("exp", f"{mm}/{yy}", 4)
            done["exp_all"] = done.get("exp", False)
            exp_line = len(report) - 1
        elif "exp_month" in found or "exp_year" in found:
            await wake()
            n0 = len(report)
            okm = await put("exp_month", mm) if "exp_month" in found else False
            oky = await put("exp_year", year_for("exp_year")) if "exp_year" in found else False
            parts = report[n0:]
            del report[n0:]
            if okm and oky:
                where = parts[0][parts[0].find(" ["):] if " [" in parts[0] else ""
                report.append("exp ok (month and year)" + where)
            else:
                why = [p.replace("exp_month FAILED", "month").replace("exp_year FAILED", "year") for p in parts if "FAILED" in p]
                if "exp_month" not in found:
                    why.append("no month field found")
                if "exp_year" not in found:
                    why.append("no year field found")
                report.append("exp FAILED: " + "; ".join(why))
            done["exp_all"] = okm and oky
            exp_line = len(report) - 1
        await put("cvc", cvc, len(cvc))
        named = False
        if name and "name" in found:
            n0 = len(report)
            named = await put("name", name)
            if not named:
                c = found.get("name", (0, 0, 0, 0, {}))[4]
                self.spans.append((f"card name candidate not usable: name={c.get('name')} id={c.get('eid')} label={c.get('lab', '')[:30]}", 0))
                del report[n0:]
                # optional, so not a failure of pb card; but there is a field, so do not say there is none
                report.append("name not filled: a cardholder-name field is there but did not take the name (pb secret TARGET card.name)")
        elif name:
            report.append("name: this form has no cardholder-name field to fill (nothing to do)")
        # The page gets its usual wait, and then every part of the card is read once more: a payment widget may empty
        # a field while the next ones are typed (petsmart: all four reported ok, the expiry was gone afterwards). Not
        # sooner than 0.4 s after the last key: what a widget does in its own frame is not seen by the wait.
        t_typed = time.time()
        await self.settle(max_s=2, quiet=0.2, react=0.25)
        await asyncio.sleep(max(0.0, 0.4 - (time.time() - t_typed)))
        async def still_there(role):
            loc, digits_expected = typed[role][:2]
            try:
                if digits_expected is None:        # a month or year list: is the card's option still the chosen one?
                    r = await loc.evaluate(PICK_JS, [role[4:], int(mm), int(yy)], timeout=1500)
                    return r["i"] >= 0 and r["sel"] == r["i"]
                return holds(await loc.input_value(timeout=1500), digits_expected)[0]
            except Exception:
                return False                       # the field is gone: whatever was typed is not in the form

        async def again(role):
            """Put one part in once more, after the read-back found it emptied. Adyen's fields (lego, petsmart) drop keys
            that come fast and empty themselves when left too soon after the last key: typed slowly, with the focus
            made sure of, given a moment, and then left the way a person leaves a field."""
            loc, digits_expected, _, value, fr = typed[role]
            try:
                if digits_expected is None:
                    return (await self.pick_exp(loc, role[4:], int(mm), int(yy)))[0]
                st = await self.look(loc)
                if st.get("gone") or not st["vis"]:
                    return False
                with contextlib.suppress(Exception):
                    await loc.focus(timeout=900)
                if not await self.focus_in(fr, loc):
                    with contextlib.suppress(Exception):
                        await loc.click(timeout=900, no_wait_after=True)
                    if not await self.focus_in(fr, loc):
                        return False
                await self.clear_field(loc)
                await loc.press_sequentially(value, delay=60, timeout=10000)
                await asyncio.sleep(0.4)
                await loc.evaluate("e => e.blur()", timeout=1000)
                await asyncio.sleep(0.15)
                return holds(await loc.input_value(timeout=1500), digits_expected)[0]
            except Exception:
                return False

        with self.span("card:check"):
            roles = [r for r in ("number", "exp", "exp_month", "exp_year", "cvc") if r in typed and done.get(r)]
            lost = [r for r in roles if not await still_there(r)]
            retried = set()
            if lost:
                with self.span("card:again"):
                    for role in lost:
                        retried.add(role)
                        await again(role)
                    # what was typed again may have upset another part: every part is read back once more
                    lost = [r for r in roles if not await still_there(r)]
            for role in roles:
                if role not in lost:
                    head = "exp ok" if role.startswith("exp") else f"{role} ok"
                    i = next((k for k, l in enumerate(report) if l.startswith(head)), None)
                    if role in retried and i is not None and "again" not in report[i]:
                        report[i] = report[i].replace(" ok", " ok (put in again: the page had emptied it)", 1)
                    continue
                loc, digits_expected, where = typed[role][:3]
                done[role] = False
                line = (f"{role.replace('exp_', '')} FAILED{where}: the field no longer holds what was typed (the page emptied or changed it "
                        "afterwards, also when it was put in a second time, slowly)")
                if role in ("exp", "exp_month", "exp_year"):
                    done["exp_all"] = False
                    if exp_line is not None:
                        report[exp_line] = ("exp" if role == "exp" else f"exp ({role[4:]})") + line[line.index(" FAILED"):]
                else:
                    i = next((k for k, l in enumerate(report) if l.startswith(f"{role} ok")), None)
                    if i is None:
                        report.append(line)
                    else:
                        report[i] = line
        missing = [r for r in ("number", "cvc") if r not in found]
        if "exp" not in found and "exp_month" not in found and "exp_year" not in found:
            missing.append("exp")
        complete = not missing and done.get("number") and done.get("exp_all") and done.get("cvc")
        if not complete:
            # next to the real problem, "there is no name field to fill" is noise
            report = [l for l in report if not l.startswith("name: this form has no")]
        s = ", ".join(report) if report else "no card fields found"
        if missing:
            s += " | NOT FOUND: " + ", ".join(missing) + " (fill with: pb secret TARGET card.number|card.exp|card.cvc)"
        if len(missing) == 3:
            # acehardware: the card form was closed behind a button, so there was nothing to type into
            s += ". The card form may not be open yet"
            with contextlib.suppress(Exception):
                items, _ = await self.collect()
                openers = []
                for i, it in enumerate(items):
                    if (it["k"] in ("button", "link", "radio", "click", "tab", "checkbox", "option") and "ref" in it
                            and self.OPENS_CARD.search(it.get("t", "") + " " + it.get("al", "")) and not re.search(r"gift", it.get("t", ""), re.I)):
                        openers.append(it)
                        # acehardware's opener was a button with no words of its own ("button value") right after the
                        # ticked "Credit/Debit Card" radio
                        nxt = next((x for x in items[i + 1:i + 3] if x["k"] in ("button", "click") and "ref" in x), None)
                        if it["k"] == "radio" and nxt is not None and nxt not in openers:
                            openers.append(nxt)
                if openers:
                    s += ": these may open it: " + "; ".join(self.line(it) for it in openers[:5]) + " (pb click one, then pb card again)"
        return ("card: " if complete else "CARD INCOMPLETE: ") + s, bool(complete)

    def exp_spellings(self):
        """The expiry of every card in the secrets file as pages print it (11/31, 11/2031, 11-31, 11 / 31, 1131...), for
        the screenshot mask. Only the expiry: the number and the code never go into the page."""
        out = []
        try:
            data = parse_secrets(self.secrets_path)
        except Exception:
            return out
        for d in data.values():
            m = re.match(r"\s*(\d{1,2})\s*/\s*(\d{2,4})", next((d[k] for k in ("expiration", "expiry", "exp") if d.get(k)), ""))
            if m:
                mm, yy = m.group(1).zfill(2), m.group(2)[-2:]
                out += [f"{mm}/{yy}", f"{mm}/20{yy}", f"{mm}-{yy}", f"{mm}-20{yy}", f"{mm} / {yy}", f"{mm} / 20{yy}", f"{mm}{yy}"]
                if mm[0] == "0":
                    out += [f"{mm[1]}/{yy}", f"{mm[1]}/20{yy}"]
        return list(dict.fromkeys(out))

    # what a button or radio that opens a closed card form says
    OPENS_CARD = re.compile(r"\b(credit|debit)\b|\bcards?\b|payment method|add (a )?new card", re.I)

    def redact(self, text):
        """Never let card data leave the daemon, whatever produced the text (see Censor). The secrets file is read
        again only when it changes."""
        try:
            stamp = os.path.getmtime(self.secrets_path)
        except OSError:
            stamp = None
        if self._censor is None or self._censor[0] != stamp:
            try:
                data = parse_secrets(self.secrets_path) if stamp is not None else {}
            except Exception:
                data = {}
            self._censor = (stamp, Censor(data))
        # A login in an address (pb open https://user:password@host/, the way in past HTTP authentication): the browser
        # keeps it in the page's address, so every URL line and the timing log carried the password.
        # (not the placeholder of pb's own advice, "https://USER:PASSWORD@host/")
        text = re.sub(r"(://[^/\s:@\"']{1,64}):(?!PASSWORD@)[^/\s@\"']{1,128}@", r"\1:***@", text)
        return self._censor[1].scrub(text)

    # ---- read-back
    async def review_lines(self, items):
        """What the page says about the order, as short lines: the final button, where it is picked up or shipped,
        the money, every checkbox, what is filled in, what is still wrong. Most important first."""
        try:
            facts = await asyncio.wait_for(self.page.evaluate(REVIEW_JS, {}), 4)
        except Exception:
            facts = {}
        sections, places = facts.get("sections") or [], facts.get("places") or []
        money, loose = facts.get("money") or [], facts.get("loose") or []
        out = []
        if self.human_flag == self.page.url.split("?")[0]:
            out.append("! " + self.human_text)
        finals = final_buttons(items)
        for it in finals[:3]:
            out.append(f'{it["ref"]} button "{it["t"]}" ({"disabled" if it.get("dis") else "enabled"})')
        # Amounts without a totals-like label are promo prices on most pages ("Deal of the day $4.99"). They count
        # only where an order is being built: a final button, a cart or checkout, or one product's own page.
        adds = [it for it in items if it["k"] in ("button", "link") and it.get("reg") == "main" and ADD_RX.search(it.get("t", ""))]
        cartish = bool(finals) or bool(CART_RX.search(self.page.url + " " + facts.get("title", ""))) or 1 <= len(adds) <= 3
        boxes = [it for it in items if it["k"] == "checkbox"]
        if not finals and not money and not places and not boxes and not (cartish and loose):
            out.append("nothing order-like on this page (no final button, totals, addresses or checkboxes)")
            if facts.get("title"):
                out.append(f'page title: "{facts["title"]}"')
            out += [f'open dialog: "{d}"' for d in facts.get("dialogs") or []]
            sections = []
        out += sections
        joined = " ".join(sections)
        out += [p for p in places if p not in joined][:6]
        out += money + (loose[:max(0, 6 - len(money))] if cartish else [])
        name = lambda it: it.get("t") or it.get("name") or it["k"]
        small = []                 # one-word boxes (card brand marks, filters) share a line; real choices get their own
        for it in items:
            if it["k"] == "checkbox":
                s = ("[x] " if it.get("on") else "[ ] ") + name(it)
                (out if " " in name(it).strip() else small).append(s)
            elif it["k"] == "radio" and it.get("on"):
                out.append("(•) " + name(it))
        if small:
            out.append("other boxes: " + ", ".join(dict.fromkeys(small)))
        fields = [it for it in items if it["k"] in ("input", "select") and not it.get("dis")]
        filled = [f'{name(it)} = {it["v"]}' for it in fields if it.get("v") and not (it.get("it") == "combobox" and it.get("v") == it.get("ph"))]
        if filled:
            out.append("filled: " + " | ".join(filled[:18]))
        empty = [name(it) for it in fields if it.get("req") and not it.get("v")]
        if empty:
            out.append("required but empty: " + ", ".join(empty[:10]))
        bad = [name(it) for it in fields if it.get("inv")]
        if bad:
            out.append("marked invalid: " + ", ".join(bad[:10]))
        out += ["! " + it["t"] for it in items if it["k"] == "!"][:3]
        # shops keep a mobile and a desktop copy of the same form: one line each is enough
        return [l[:300] for l in list(dict.fromkeys(out))[:44]]

    async def maybe_review(self, items):
        """The review, unasked, the first time the final button is enabled and whenever the order facts change after
        that. Reports of "ready" on the wrong store came from never reading this back."""
        try:
            return await self._maybe_review(items)
        except Exception:
            return ""                # an extra: it must never turn a command that worked into an error

    async def _maybe_review(self, items):
        if not any(not x.get("dis") for x in final_buttons(items)):
            self.last_review = None
            return ""
        lines = await self.review_lines(items)
        key = self.review_key(lines)
        if key == self.last_review:
            return ""
        self.last_review = key
        self.review_shown = (self.req_no, "\n".join(lines))
        return ("REVIEW (the final button is enabled). Compare every line with what was asked before you report or click it:\n"
                + "\n".join("  " + l for l in lines) + "\n")

    @staticmethod
    def review_key(lines):
        """The order facts of a review, to show each set once: typed field values do not count."""
        return "\n".join(l for l in lines if not l.startswith("filled: "))

    async def asked_review(self, items, again_ok=True):
        """A review the caller asked for (pb review, pb expect), as the lines to print under "REVIEW of the page:". The
        same facts are then not repeated unasked. again_ok=False (pb expect): when the command just before printed this
        very review (macys: `pb review; pb expect` showed it twice in a row), one line says so instead."""
        lines = await self.review_lines(items)
        if any(not x.get("dis") for x in final_buttons(items)):
            self.last_review = self.review_key(lines)
        full = "\n".join(lines)
        prev = self.review_shown
        self.review_shown = (self.req_no, full)
        if not again_ok and prev and prev[0] >= self.req_no - 1 and prev[1] == full:
            return ["(the same as printed by the last command, unchanged)"]
        return lines

    async def do_expect(self, a):
        """pb expect TEXT... [--in SECTION TEXT] [--not TEXT] [--checked|--unchecked LABEL] [--enabled|--disabled LABEL]
        Checks the page against what was asked, in code. One PASS or FAIL line per check, then the review."""
        items, meta = await self.collect()
        text = " ".join(meta.get("text") or [])
        norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()
        page_text = norm(text)
        flags = ("--not", "--checked", "--unchecked", "--enabled", "--disabled")
        usage = ('usage: pb expect "TEXT"... [--in "SECTION" "TEXT"] [--not "TEXT"] [--unchecked "LABEL"] [--checked "LABEL"] '
                 '[--enabled "BUTTON"] [--disabled "BUTTON"]')
        checks, i = [], 0
        while i < len(a):
            if a[i] == "--in":                       # --in SECTION TEXT: the text must be in the block under that heading
                if i + 2 >= len(a):
                    raise Err("pb expect: --in needs two values, the section and the text. " + usage)
                checks.append(("has", a[i + 2], a[i + 1]))
                i += 3
            elif a[i] in flags:
                if i + 1 >= len(a):
                    raise Err(f"pb expect: {a[i]} needs a value. " + usage)
                checks.append((a[i][2:], a[i + 1], None))
                i += 2
            else:
                checks.append(("has", a[i], None))
                i += 1
        if not checks:
            raise Err(usage)
        def has(hay, needle):
            """needle in hay, ignoring case and spacing. Where the needle starts or ends with a letter or digit, a word
            must start or end there too: "Total" is not in "Subtotal", "$29.79" is not in "$129.79"."""
            n = norm(needle)
            if not n:
                return True
            rx = (r"(?<![^\W_])" if n[0].isalnum() else "") + re.escape(n) + (r"(?![^\W_])" if n[-1].isalnum() else "")
            return re.search(rx, norm(hay)) is not None

        fields = None

        async def in_field(val, sc):
            """The visible field that holds the text (what was typed or chosen), never a masked or secret one. With a
            section, only fields under that heading or labelled with its name count."""
            nonlocal fields
            if fields is None:
                fields = await self.field_values(items)
            q = (sc or "").lower()
            for it, v in fields:
                if q and q not in (it.get("sec") or "").lower() and q not in (it.get("t") or "").lower():
                    continue
                if has(v, val):
                    return it
            return None

        blocks, hidden_parts = {}, None
        lines, fails = [], 0
        for kind, val, sc in checks:
            ok, why = False, ""
            if kind in ("has", "not"):
                where = f' in "{sc}"' if sc else ""
                big, hit = 0, None
                if sc:
                    if sc not in blocks:
                        try:
                            blocks[sc] = (await asyncio.wait_for(self.page.evaluate(REVIEW_JS, {"section": sc}), 4))["blocks"]
                        except Exception:
                            blocks[sc] = []
                    # Several blocks may match the name equally well (two "Pickup" labels): the text counts when it is
                    # in any of them, and the answer names the one it is in.
                    hit = next((b for b in blocks[sc] if has(b["text"].replace(" | ", " "), val)), None)
                    hay = (hit or {}).get("text") or " || ".join(b["text"] for b in blocks[sc])
                    big = (hit.get("size") or len(hit["text"])) if hit else max([b.get("size") or len(b["text"]) for b in blocks[sc]] or [0])
                else:
                    hay = text
                found = (hit is not None) if sc else (bool(hay) and has(hay.replace(" | ", " "), val))       # a label and its amount are often on separate lines
                field = None
                if kind == "has" and (not found or big > 1500):    # a field is better evidence than a page-sized block
                    field = await in_field(val, sc)
                    found = found or field is not None
                if sc and not blocks[sc] and not field:
                    lines.append(f'FAIL {kind} "{val}"{where}: no section or label "{sc}" on this page')
                    fails += 1
                    continue
                hidden = ""
                if kind == "has" and not found and not sc:
                    # not in the visible text: a collapsed "order summary", a product picture or a web component holds it
                    hidden = await self.hidden_find(val, has, hidden_parts)
                    hidden_parts = self._hidden_parts
                    found = bool(hidden)
                ok = found if kind == "has" else not found
                if field:
                    why = f'in field "{field.get("t") or field.get("name") or field["k"]}" ({field["ref"]} {field["k"]})'
                elif sc and hit:
                    why = f'"{hit["title"][:60]}" says: ' + hit["text"][:260]
                    if big > 1500:
                        why += f" (that section is about {big} characters long, so this match is weak)"
                elif sc:
                    # every block that was looked at, so the caller sees what the page says there instead
                    bl = blocks[sc]
                    why = ("looked at " + (f"{len(bl)} blocks: " if len(bl) > 1 else "") + "; ".join(f'"{b["title"][:60]}" says: {b["text"][:160 if len(bl) > 1 else 260]}' for b in bl[:3])
                           + (f"; and {len(bl) - 3} more" if len(bl) > 3 else ""))
                    if big > 1500:
                        why += f" (that section is about {big} characters long, so this match is weak)"
                elif hidden:
                    why = hidden
                else:
                    line = next((l for l in (meta.get("text") or []) if has(l, val)), "")
                    why = (f'found: "{line[:160]}"' if line else "found across lines") if found else "nowhere in the page text or its fields"
                lines.append(f'{"PASS" if ok else "FAIL"} {"has" if kind == "has" else "must not have"} "{val}"{where}: {why}')
            else:
                box = kind in ("checked", "unchecked")
                kinds = ("checkbox", "radio") if box else ("button", "link", "click")
                scored = sorted(((self.score(val, it, "check" if box else "click"), n, it) for n, it in enumerate(items) if it["k"] in kinds),
                                key=lambda x: (-x[0], x[1]))
                scored = [x for x in scored if x[0] > 0]
                if not scored:
                    # a box that is not there cannot be ticked, and a button that is not there cannot be pressed
                    ok = kind in ("unchecked", "disabled")
                    what = "checkbox" if box else "button"
                    lines.append(f'{"PASS" if ok else "FAIL"} {kind} "{val}": no such {what} on this page'
                                 + (" (missing counts as not enabled)" if kind == "disabled" else ""))
                    fails += 0 if ok else 1
                    continue
                top = [x[2] for x in scored if x[0] == scored[0][0]]
                state = (lambda it: bool(it.get("on"))) if box else (lambda it: not it.get("dis"))
                want = kind in ("checked", "enabled")
                ok = all(state(it) == want for it in top)
                lines.append(f'{"PASS" if ok else "FAIL"} {kind} "{val}": ' + "; ".join(self.line(it) for it in top[:3]))
            fails += 0 if ok else 1
        head = (f"EXPECT ok: all {len(checks)} checks passed" if not fails else
                f"EXPECT FAILED: {fails} of {len(checks)} checks failed. Do not report this page as ready; fix it or say what is wrong")
        return [head] + lines + ["REVIEW of the page:"] + ["  " + l for l in await self.asked_review(items, again_ok=False)]

    # Text a person may not see but that still names what is in the order: collapsed parts of the page (script and
    # style source left out), image alt texts (product thumbnails), aria-labels, and the text inside shadow roots.
    HIDDEN_JS = r"""
    () => {
      const skip = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE']);
      const textOf = (root) => {
        const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        const parts = [];
        let size = 0;
        for (let n = w.nextNode(); n && size < 2000000; n = w.nextNode()) {
          const p = n.parentElement;
          if (p && skip.has(p.tagName)) continue;
          parts.push(n.nodeValue);
          size += n.nodeValue.length;
        }
        return parts.join(' ');
      };
      const out = { text: document.body ? textOf(document.body) : '', shadow: '', alts: [], arias: [] };
      const walk = (root) => {
        for (const el of root.querySelectorAll('*')) {
          if (el.tagName === 'IMG' && el.alt && out.alts.length < 500) out.alts.push(el.alt);
          const al = el.getAttribute('aria-label');
          if (al && out.arias.length < 1000) out.arias.push(al);
          if (el.shadowRoot) { out.shadow += textOf(el.shadowRoot) + ' '; walk(el.shadowRoot); }
        }
      };
      walk(document);
      return out;
    }
    """

    async def hidden_find(self, val, has, parts):
        """Where on the page, outside its visible text, the text is: a sentence for the PASS line, or "" if nowhere."""
        if parts is None:
            try:
                parts = await asyncio.wait_for(self.page.evaluate(self.HIDDEN_JS), 3)
            except Exception:
                parts = {}
        self._hidden_parts = parts
        alt = next((x for x in parts.get("alts") or [] if has(x, val)), None)
        if alt is not None:
            return f'found in the alt text of an image: "{alt[:120]}" (the page text does not name it)'
        aria = next((x for x in parts.get("arias") or [] if has(x, val)), None)
        if aria is not None:
            return f'found in an aria-label: "{aria[:120]}" (the page text does not name it)'
        if has(parts.get("text") or "", val):
            return "found, but only in a collapsed or hidden part of the page (open that part to see it)"
        if has(parts.get("shadow") or "", val):
            return "found, but only in the hidden text of a web component (shadow root) on the page"
        return ""

    async def field_values(self, items):
        """(item, full value) of every visible field that shows what was typed or chosen. Masked and password fields
        are left out. A view cuts values at 40 characters; those are read again in full."""
        out = []
        for it in items:
            v = str(it.get("v") or "")
            if it["k"] not in ("input", "select") or not v or v.startswith("•") or it.get("it") == "password":
                continue
            if v.endswith("…") and it.get("ref") in self.refs:
                fr = self.refs[it["ref"]][0]
                with contextlib.suppress(Exception):
                    full = await asyncio.wait_for(fr.locator(f'[data-pb="{it["ref"]}"]').first.evaluate(
                        "e => e.tagName === 'SELECT' ? (e.selectedOptions[0] ? e.selectedOptions[0].textContent : '') "
                        ": ('value' in e ? e.value : e.innerText)", timeout=1000), 1.5)
                    if isinstance(full, str) and full:
                        v = full
            out.append((it, v))
        return out

    # ---- failure capture (test runs only: PB_CAPTURE=DIR in the environment of `pb start`)
    async def snapshot_html(self):
        """The page as one static HTML file: every frame's SNAP_JS copy, child frames put back as srcdoc, styles
        inlined, scripts removed. Loads offline and scans like the live page did."""
        counter = [0]

        async def snap(fr, prefix):
            doc = await asyncio.wait_for(fr.evaluate(SNAP_JS, {"prefix": prefix, "n": 0}), 8)
            html = doc["html"]
            for child in fr.child_frames:
                if child.is_detached() or TRACKERS.search(child.url.split("?")[0]):
                    continue
                try:
                    fe = await asyncio.wait_for(child.frame_element(), 1.0)
                    sid = await asyncio.wait_for(fe.evaluate("e => e.getAttribute('data-pb-snap')"), 1.0)
                    counter[0] += 1
                    sub = await snap(child, f"f{counter[0]}")
                except Exception:
                    continue
                if not sid:
                    continue
                tag = re.search(r"<i?frame\b[^>]*\bdata-pb-snap=\"" + re.escape(sid) + r"\"[^>]*>", html)
                if tag:
                    new = re.sub(r"\s(?:src|srcdoc)=\"[^\"]*\"", "", tag.group(0))[:-1] + f' data-pb-src="{child.url[:300]}" srcdoc="' \
                        + sub.replace("&", "&amp;").replace('"', "&quot;") + '">'
                    html = html[:tag.start()] + new + html[tag.end():]
            parts = []
            for c in doc["css"]:
                if "text" in c:
                    parts.append(c["text"])
                else:                               # a stylesheet from another origin: the page may not read it, the browser may fetch it
                    with contextlib.suppress(Exception):
                        r = await self.ctx.request.get(c["href"], timeout=5000)
                        parts.append(await r.text())
            html = re.sub(r"<script\b[\s\S]*?</script\s*>", "", html, flags=re.I)
            html = re.sub(r"<link\b[^>]*\brel=\"?(?:stylesheet|preload|modulepreload|prefetch)\"?[^>]*>|<meta\b[^>]*http-equiv[^>]*>|<base\b[^>]*>", "", html, flags=re.I)
            html = re.sub(r"<style\b(?![^>]*data-pb-snap-style)[^>]*>[\s\S]*?</style\s*>", "", html, count=0, flags=re.I) if "<template shadowrootmode" not in html else html
            style = '<meta charset="utf-8"><style data-pb-snap-css="1">' + "\n".join(parts).replace("</style", "<\\/style") + "</style>"
            return re.sub(r"(<head\b[^>]*>)", lambda m: m.group(1) + style, html, count=1) if re.search(r"<head\b", html) else style + html

        return await snap(self.page.main_frame, "f0")

    async def capture(self, args, out):
        """Keep what pb saw when a command failed, so the failure can be replayed offline: the static page copy, pb's
        scan of it, the command, the answer and the timing spans."""
        if self.captures >= int(os.environ.get("PB_CAPTURE_MAX", "30")):      # page copies are megabytes each
            return
        self.captures += 1
        name = re.sub(r"[^a-z0-9]+", "-", " ".join(args)[:40].lower()).strip("-") or "cmd"
        d = os.path.join(self.capture_dir, f"{self.captures:02d}-{name}")
        with contextlib.suppress(Exception):
            os.makedirs(d, exist_ok=True)
            info = {"url": self.page.url, "args": args, "out": out[:4000], "spans": self.spans, "t": round(time.time(), 1),
                    "scan": [self.line(it) for it in (self.scan or {}).get("items", [])][:400]}
            with open(os.path.join(d, "info.json"), "w", encoding="utf-8") as f:
                f.write(self.redact(json.dumps(info, ensure_ascii=False, indent=1)))
            html = await asyncio.wait_for(self.snapshot_html(), 25)
            with open(os.path.join(d, "page.html"), "w", encoding="utf-8") as f:
                f.write(self.redact(html))

    MARK_SECRET = "e => e.setAttribute('data-pb-secret', '1')"

    # Before a screenshot: tag what must not be readable in the picture. Fields pb typed a secret into, card fields
    # by their autocomplete hint or name, and any text that reads as a card number.
    MASK_JS = r"""
    (exps) => {
      for (const el of document.querySelectorAll('[data-pb-mask]')) el.removeAttribute('data-pb-mask');
      // The card's expiry as the page may print it once the card is in ("Exp: 12/2029" on lowes and nike): the spellings
      // come from the daemon (never the number or the code). Painted where a label says expiry, or where the same line
      // shows a card number or a masked one; a date that merely looks the same elsewhere stays readable.
      const EXPLAB = /\b(exp|expires?|expiry|expiration|valid\s*(thru|through|until)|good\s*thru)\b/i;
      const MASKED = /[•*●xX]{3,}[\s-]*\d{4}\b|\bending\s*(in\s*)?\d{4}\b|\d(?:[ -]?\d){12,18}/;
      const hasExp = (s) => (exps || []).some(e => { let i = s.indexOf(e); while (i >= 0) { const a = s[i - 1] || ' ', b = s[i + e.length] || ' ';
                                                                                  if (!/\d/.test(a) && !/\d/.test(b)) return true; i = s.indexOf(e, i + 1); }
                                                                           return false; });
      // card fields only, judged word by word as in COLLECT_JS (cardCvv -> card cvv, so "csc" inside another word does not count)
      const SENS = (s) => /\bcc (number|num|csc|cvv|cvc|exp\w*)\b|\bcard ?(num|number|no)\b|\bcardnumber\b|\bpan\b|\b(cvv|cvc|csc|cvn)\d?\b|\bsecurity ?code\b|\bexpir|\bexp ?(date|month|year|mm|yy)\b|\bmm ?yy\b/.test(
        String(s).replace(/([a-z])([A-Z])/g, '$1 $2').replace(/[^A-Za-z0-9]+/g, ' ').toLowerCase());
      let n = 0;
      for (const el of document.querySelectorAll('input, select')) {
        // only a field that holds something is painted: an empty box shows nothing, and leaving it visible shows
        // whether the card went in (ikea: the painted empty boxes hid that)
        if (el.tagName === 'SELECT') {
          if (el.hasAttribute('data-pb-secret') && el.selectedIndex > 0) { el.setAttribute('data-pb-mask', '1'); n++; }
          continue;
        }
        if (!el.value) continue;
        const ac = el.getAttribute('autocomplete') || '';
        const hint = [/^cc-/.test(ac) ? ac : '', el.name, el.id, el.placeholder, el.getAttribute('aria-label')].join(' ');
        // by hint alone only when the value also looks like card data (digits, spaces, a slash)
        const cardish = /^[\d\s\/•*-]{3,23}$/.test(el.value);
        if (el.hasAttribute('data-pb-secret') || (cardish && el.type !== 'password' && SENS(hint) && !/gift|promo|coupon/i.test(hint))) { el.setAttribute('data-pb-mask', '1'); n++; }
      }
      const luhn = (d) => { let s = 0; for (let i = 0; i < d.length; i++) { let v = +d[d.length - 1 - i]; if (i % 2) { v *= 2; if (v > 9) v -= 9; } s += v; } return s % 10 === 0; };
      const w = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
      for (let nd = w.nextNode(); nd; nd = w.nextNode()) {
        const v = nd.nodeValue || '', pe = nd.parentElement;
        if (pe && /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(pe.tagName)) continue;      // never drawn
        if (pe && hasExp(v)) {
          let near = v;
          // the label or the card may sit in the element next to it: look at the smallest block around it, if small
          for (let p = pe, i = 0; p && i < 3; p = p.parentElement, i++) { const t = p.textContent || ''; if (t.length > 300) break; near = t; if (EXPLAB.test(t) || MASKED.test(t)) break; }
          if (EXPLAB.test(near) || MASKED.test(near)) { pe.setAttribute('data-pb-mask', '1'); n++; continue; }
        }
        const m = v.match(/\d(?:[ \-   .]?\d){12,18}/g);
        if (!m || !pe) continue;
        const brand = (d) => { const n = d.length, p2 = +d.slice(0, 2), p3 = +d.slice(0, 3), p4 = +d.slice(0, 4);     // as card_like() in Python
          return (d[0] === '4' && (n === 13 || n === 16 || n === 19)) || (p2 >= 51 && p2 <= 55 && n === 16) || (p4 >= 2221 && p4 <= 2720 && n === 16)
            || ((p2 === 34 || p2 === 37) && n === 15) || ((p4 === 6011 || p2 === 65 || (p3 >= 644 && p3 <= 649)) && n >= 16)
            || (p4 >= 3528 && p4 <= 3589 && n >= 16) || (((p3 >= 300 && p3 <= 305) || p2 === 36 || p2 === 38) && n >= 14) || (p2 === 62 && n >= 16); };
        if (m.some(s => { const d = s.replace(/\D/g, ''); return d.length >= 13 && d.length <= 19 && luhn(d) && brand(d); })) { nd.parentElement.setAttribute('data-pb-mask', '1'); n++; }
      }
      return n;
    }
    """

    async def hrefs(self, items):
        """ref -> the address a link item leads to, asked in one round trip per frame. Script links and a bare "#" on
        this page are left out: they lead nowhere worth naming."""
        by_frame, out = {}, {}
        for it in items:
            if it.get("ref") in self.refs:
                by_frame.setdefault(self.refs[it["ref"]][0], []).append(it["ref"])

        async def ask(fr, refs):
            with contextlib.suppress(Exception):
                for r, h in zip(refs, await asyncio.wait_for(fr.evaluate(HREFS_JS, refs), 2)):
                    if h and not h.lower().startswith("javascript:") and h != fr.url.split("#")[0] + "#":
                        out[r] = h

        await asyncio.gather(*(ask(fr, refs) for fr, refs in by_frame.items()))
        return out

    # ---- general browsing commands
    async def do_scroll(self, a):
        """pb scroll down|up [N] | top | bottom | TARGET. Returns the status lines; the delta follows (what loaded)."""
        page = self.page
        how = a[0].lower() if a else "down"
        if how in ("down", "up") and (len(a) < 2 or re.fullmatch(r"\d+(\.\d+)?", a[1])) and len(a) <= 2:
            n = float(a[1]) if len(a) > 1 else 1.0
            r = await page.evaluate(SCROLL_JS, {"how": how, "n": n})
            await self.settle(max_s=3, react=0.3)
            head = f"ok scroll {how}" + (f" {a[1]}" if len(a) > 1 else "")
        elif how == "top" and len(a) == 1:
            r = await page.evaluate(SCROLL_JS, {"how": "top"})
            await self.settle(max_s=3, react=0.3)
            head = "ok scroll top"
        elif how == "bottom" and len(a) == 1:
            # An endless list loads more when its end comes into view: scroll to the bottom again after each load,
            # until a round brings nothing new (the page is no longer and has no more elements) or 15 rounds.
            first = await page.evaluate(SCROLL_JS, {"how": "measure"})
            last, rounds = first, 0
            for rounds in range(1, 16):
                if rounds > 1:
                    await self.mark()
                await page.evaluate(SCROLL_JS, {"how": "bottom"})
                # a list asks for more a moment after its end shows (scroll handlers are often debounced)
                await self.settle(max_s=6, react=0.7)
                r = await page.evaluate(SCROLL_JS, {"how": "measure"})
                if r["h"] <= last["h"] and r["els"] <= last["els"]:
                    break
                last = r
            if r["h"] > first["h"] or r["els"] > first["els"]:
                head = (f"ok scroll bottom: {rounds} rounds, the page grew from {first['h']} to {r['h']} px "
                        f"(+{max(0, r['els'] - first['els'])} elements)" + ("; stopped at 15 rounds, there may be more" if rounds == 15 else ""))
            else:
                head = "ok scroll bottom" + (" (nothing more loaded)" if rounds > 1 else "")
            r = await page.evaluate(SCROLL_JS, {"how": "bottom"})
        else:
            target = " ".join(a)
            loc, it = await self.find_any(target, "click")
            await loc.evaluate("e => e.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' })", timeout=3000)
            await self.settle(max_s=3, react=0.3)
            label = f'{it.get("ref", "")} {it.get("k", "")} "{it.get("t", "")}"'.strip() if it.get("k") not in ("text", "css") else it.get("t", "") if it.get("k") == "css" else f'"{target[:60]}"'
            inside = await loc.evaluate("""e => { for (let p = e.parentElement; p && p !== document.body && p !== document.documentElement; p = p.parentElement) {
                const o = getComputedStyle(p).overflowY; if ((o === 'auto' || o === 'scroll') && p.scrollHeight > p.clientHeight + 4) return true; } return false; }""")
            head = f"ok scroll {label} into view" + (" (inside a box with its own scrollbar)" if inside else "")
            r = await page.evaluate(SCROLL_JS, {"how": "measure"})
        where = (f" -> {r['y']} of {max(0, r['h'] - r['view'])} px" + (f" ({round(100 * r['y'] / max(1, r['h'] - r['view']))}%)" if r['h'] > r['view'] else "")
                 + (", at the bottom" if r["y"] >= r["h"] - r["view"] - 2 and r["h"] > r["view"] else "")
                 + (" (the page's main box; the window itself does not scroll)" if r["box"] else ""))
        if how in ("down", "up", "top") and r["y"] == r["y0"]:
            where += " (did not move: already at that end)"
        lines = [head + where]
        seen = []
        with contextlib.suppress(Exception):
            seen = await asyncio.wait_for(page.evaluate(INVIEW_JS), 3)
        if seen:
            s = " | ".join(seen)
            lines.append("in view: " + (s[:400] + "…" if len(s) > 400 else s))
        self.quiet_same = True
        return lines

    async def do_hover(self, target):
        loc, it = await self.find_any(target, "click")
        label = f'{it.get("ref", "")} {it.get("k", "")} "{it.get("t", "")}"'.strip() if it.get("k") not in ("text", "css") else it.get("t", "") if it.get("k") == "css" else f'"{target[:60]}"'
        st = await self.look(loc)
        if st.get("gone"):
            raise Err(f"{label} is no longer on the page. Take a fresh ref: pb view, or pb find TEXT")
        if not st["vis"]:
            raise Err(f"{label} is not visible, so the mouse cannot reach it. It may sit in a menu that opens first: hover what opens it")
        before = None
        if self.view_due:
            with contextlib.suppress(Exception):
                before = (await self.collect())[0]
        try:
            await loc.hover(timeout=1500 if st["cover"] else 2500)
        except Exception:
            # something lies over it: the mouse goes to its center all the same, as a person's would
            box = await loc.bounding_box(timeout=1000)
            await self.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        # menus that open on hover often wait a moment first (hover intent)
        await self.settle(max_s=2.5, react=0.5)
        title = ""
        with contextlib.suppress(Exception):
            title = await loc.evaluate("e => { const t = e.closest('[title]'); return t ? t.title : ''; }", timeout=1000)
        out = [f"ok hover {label}" + (f' (title: "{title[:120]}")' if title else "")]
        if before is not None:
            # the batch ends in a whole view, where a menu this hover opened reads like the rest of the page: what is
            # new goes under this step, as a page change would list it
            with contextlib.suppress(Exception):
                after = (await self.collect())[0]
                old = {}
                for x in before:
                    old[self.sig(x)] = old.get(self.sig(x), 0) + 1
                new = []
                for x in after:
                    s = self.sig(x)
                    if old.get(s, 0) > 0:
                        old[s] -= 1
                    elif x["k"] != "h":
                        new.append(x)
                new = self.fold_runs(new)
                out += ["+ " + self.line(x) for x in new[:12]] + ([f"+{len(new) - 12} more: pb view --grep REGEX"] if len(new) > 12 else [])
                if not new:
                    out.append("(nothing new showed)")
        return out

    # the file field an element stands for: itself, the field its label is for, or one inside it
    FILE_FIELD_JS = """e => { const f = (x) => x && x.tagName === 'INPUT' && x.type === 'file' ? x : null;
        if (f(e)) return e; if (f(e.control)) return e.control; const l = e.closest('label'); if (l && f(l.control)) return l.control;
        return e.querySelector('input[type=file]'); }"""

    async def do_upload(self, target, names):
        paths = [local_path(n, self.cwd) for n in names]
        missing = [n for n, p in zip(names, paths) if not os.path.isfile(p)]
        if missing:
            raise Err(f"no such file: {', '.join(missing)} (relative paths start in {slash(self.caller_dir())}). Nothing was uploaded")
        loc, it = await self.find_any(target, "click")
        label = f'{it.get("ref", "")} {it.get("k", "")} "{it.get("t", "")}"'.strip() if it.get("k") not in ("text", "css") else it.get("t", "") if it.get("k") == "css" else f'"{target[:60]}"'
        field = None
        with contextlib.suppress(Exception):
            field = (await loc.evaluate_handle(self.FILE_FIELD_JS, timeout=2000)).as_element()
        how = ""
        if field is not None:
            await field.set_input_files(paths, timeout=5000)
        else:
            # a button that opens the file chooser for a field the page keeps hidden: click it and answer the chooser
            try:
                async with self.page.expect_file_chooser(timeout=4000) as fc:
                    await self.do_click(loc, it)
                chooser = await fc.value
            except Exception as e:
                if "Timeout" not in str(e) and "timeout" not in str(e):
                    raise
                raise Err(f"{label} is not a file field and clicking it opened no file chooser. Name the file field itself: "
                          "pb find, or css=input[type=file]")
            await chooser.set_files(paths, timeout=5000)
            field, how = chooser.element, " (through the file chooser it opens)"
        # Read right after the files went in, before the page reacts (a form that sends and clears it on change).
        # (An element handle's evaluate takes no timeout argument: passing one failed every read, and the answer said
        # "nothing" while the field held the file.)
        held = None
        with contextlib.suppress(Exception):
            held = await asyncio.wait_for(field.evaluate("e => [...(e.files || [])].map(f => [f.name, f.size])"), 2)
        await self.settle(max_s=4, react=0.5)
        if held is None:
            return [f"ok upload {label}{how} (pb could not read the field back: look at the page to confirm)"]
        return [f"ok upload {label}{how}: the field now holds " + (", ".join(f"{n} ({s} bytes)" for n, s in held) or "nothing (the page refused the files)")]

    async def fetch_to_file(self, url, dest):
        """Fetch url with the browser's cookies and save it: into dest (a file, or a directory to put it in) or the
        caller's directory, under the name the server gives (or the last part of the address), never over a file."""
        import base64
        import mimetypes
        from urllib.parse import unquote, urlparse
        ctype, name = "", ""
        if url.startswith(("blob:", "data:")):
            # only the page can read its own blob: and data: addresses
            res = await self.page.evaluate("""async (u) => { const r = await fetch(u); const b = new Uint8Array(await r.arrayBuffer());
                let s = ''; for (let i = 0; i < b.length; i += 32768) s += String.fromCharCode.apply(null, b.subarray(i, i + 32768));
                return [btoa(s), r.headers.get('content-type') || '']; }""", url)
            body, ctype = base64.b64decode(res[0]), res[1]
        elif file_url_path(url) is not None:
            # a file: address is a file on this machine: read from the disk
            src = file_url_path(url)
            if not os.path.isfile(src):
                raise Err(f"no such file: {slash(src)} (from {url[:160]})")
            with open(src, "rb") as f:
                body = f.read()
            name = os.path.basename(src)
            ctype = mimetypes.guess_type(src)[0] or ""
        else:
            r = await self.ctx.request.get(url, timeout=60000)
            if not r.ok:
                raise Err(f"the server answered HTTP {r.status} for {url[:160]}, so nothing was saved")
            body = await r.body()
            ctype = r.headers.get("content-type", "")
            m = re.search(r"filename\*=(?:UTF-8'')?([^;]+)|filename=\"?([^\";]+)", r.headers.get("content-disposition", ""), re.I)
            if m:
                name = unquote((m.group(1) or m.group(2)).strip().strip('"'))
            if not name:
                name = unquote(os.path.basename(urlparse(url).path))
        if url.startswith(("data:", "blob:")):
            name = ""                          # (a data: address is the file itself: no name in it, only bytes)
        name = safe_name(name or "download")
        if "." not in name and ctype:
            name += mimetypes.guess_extension(ctype.split(";")[0].strip()) or ""
        if dest:
            p = local_path(dest, self.cwd)
            path = os.path.join(p, name) if os.path.isdir(p) else p
        else:
            path = os.path.join(self.caller_dir(), name)
        path = unique_path(path)
        with open(path, "wb") as f:
            f.write(body)
        twin = same_as_earlier(path) if not dest and body else None
        path = twin or path
        self.last_fetch = (path, body[:5] == b"%PDF-")
        kind = ctype.split(";")[0].strip()
        if twin:
            return f"DOWNLOAD the same file is already at {slash(path)} ({len(body)} bytes{', ' + kind if kind else ''}), so no second copy was saved"
        if not body:
            return f"DOWNLOAD saved {slash(path)}: an EMPTY file (0 bytes; the server sent nothing{', type ' + kind if kind else ''}) from {self.short_url(url)}"
        return f"DOWNLOAD saved {slash(path)} ({len(body)} bytes{', ' + kind if kind else ''}) from {self.short_url(url)}"

    @staticmethod
    def short_url(url):
        """An address as an answer names it: a data: or blob: address by its kind and length (it is the whole file)."""
        if url.startswith("data:"):
            return f"a data: address ({url[5:].split(',', 1)[0][:40]}, {len(url)} characters)"
        return url[:160]

    async def do_links(self, a):
        rx = re.compile(" ".join(a), re.I) if a else None
        links = await self.page.evaluate(LINKS_JS)
        hits = [l for l in links if rx is None or rx.search(l[0]) or rx.search(l[1])]
        if not hits:
            return [f"no link matches /{' '.join(a)}/ ({len(links)} links on the page)" if a else "no links on this page"]
        groups = {}
        for t, h, ref in hits:
            groups.setdefault((t, h), []).append(ref)
        cap = 40
        out = [(f"{len(hits)} links match /{' '.join(a)}/" if a else f"{len(hits)} links on the page")
               + (f" (showing {cap}; narrow with pb links REGEX, which matches text or address):" if len(groups) > cap else ":")]
        for (t, h), refs in list(groups.items())[:cap]:
            ref = next((r for r in refs if r), "")
            out.append((ref + " " if ref else "") + f'"{t}" -> {h}' + (f"  x{len(refs)}" if len(refs) > 1 else ""))
        if len(groups) > cap:
            out.append(f"({len(groups) - cap} more not shown; pb links REGEX narrows)")
        return out

    async def do_table(self, a):
        span = None
        if "--rows" in a:
            i = a.index("--rows")
            m = re.fullmatch(r"(\d+)\s*-\s*(\d+)|(\d+)", a[i + 1] if i + 1 < len(a) else "")
            if not m:
                raise Err("usage: pb table N|TEXT --rows A-B (row numbers from 1, header not counted)")
            span = (int(m.group(1)), int(m.group(2))) if m.group(1) else (int(m.group(3)), int(m.group(3)))
            a = a[:i] + a[i + 2:]
        q = " ".join(a)
        in_row = ""
        tables = await self.page.evaluate(TABLES_JS, {"pick": 0, "from": 1, "to": 0})
        name = lambda t: t["name"] or t["heading"] or "(no name)"
        if not tables:
            return ["no data tables on this page (no <table> with two columns or a header, and no role=table / grid)"]
        if not q:
            out = [f"{len(tables)} table{'s' if len(tables) != 1 else ''} (pb table N or pb table TEXT prints one):"]
            for i, t in enumerate(tables, 1):
                under = f' under "{t["heading"]}"' if t["name"] and t["heading"] and t["heading"] != t["name"] else ""
                cols = " | ".join(t["head"]) if t["head"] else f"{t['cols']} columns, no header row"
                out.append(f'{i} "{name(t)}"{under}: {cols}; {t["rows"]} rows')
            return out
        if re.fullmatch(r"\d+", q):
            pick = int(q)
            if not 1 <= pick <= len(tables):
                raise Err(f"there are {len(tables)} tables on this page; pb table lists them")
        else:
            ql = q.lower()
            fields = lambda t: [t["name"].lower(), t["heading"].lower()] + [h.lower() for h in t["head"]]
            pick = next((i for i, t in enumerate(tables, 1) if ql in (t["name"].lower(), t["heading"].lower())), None) \
                or next((i for i, t in enumerate(tables, 1) if any(ql in f for f in fields(t))), None)
            if pick is None:
                # a text in one of the rows: that row's table, from a little before that row
                found = await self.page.evaluate(TABLES_JS, {"pick": 0, "from": 1, "to": 0, "find": ql})
                pick = next((i for i, t in enumerate(found, 1) if t.get("row", 0) > 0), None)
                if pick is not None:
                    r0 = found[pick - 1]["row"]
                    in_row = f'; "{q}" first in row {r0}'
                    if span is None:
                        span = (max(1, r0 - 2), max(1, r0 - 2) + 39)
            if pick is None:
                raise Err(f'no table has "{q}" in its caption, header, the heading above it or a cell. Tables: '
                          + "; ".join(f'{i} "{name(t)}"' for i, t in enumerate(tables, 1)))
        lo, hi = span or (1, 40)
        t = (await self.page.evaluate(TABLES_JS, {"pick": pick, "from": lo, "to": min(hi, lo + 199)}))[pick - 1]
        rows, shown = t["rows"], t.get("data") or []
        last = lo + len(shown) - 1
        nh = len(t.get("headRows") or [])
        head = f'TABLE {pick} "{name(t)}": {t["cols"]} columns, {rows} rows' + (f" plus {nh} header rows" if nh > 1 else "") + in_row
        if shown and (lo > 1 or last < rows):
            head += f" (showing {lo}-{last}" + (f"; pb table {pick} --rows {last + 1}-{rows} for the rest" if last < rows else "") + ")"
        elif not shown:
            head += f" (no rows in {lo}-{hi})"
        out = [head] + [" | ".join(r) for r in t.get("headRows") or []] + [" | ".join(r)[:4000] for r in shown]
        return out

    async def do_drag(self, src_t, dst_t):
        page = self.page
        src, sit = await self.find_any(src_t, "click")
        dst, dit = await self.find_any(dst_t, "click")
        lab = lambda it, t: f'{it.get("ref", "")} {it.get("k", "")} "{it.get("t", "")}"'.strip() if it.get("k") != "text" else f'"{t[:60]}"'
        with contextlib.suppress(Exception):
            await dst.scroll_into_view_if_needed(timeout=1500)
        with contextlib.suppress(Exception):
            await src.scroll_into_view_if_needed(timeout=1500)
        sb, db = await src.bounding_box(timeout=2000), await dst.bounding_box(timeout=2000)
        if not sb or not db:
            raise Err(f"{lab(sit, src_t) if not sb else lab(dit, dst_t)} has no box on screen (hidden?), so nothing was dragged")
        sx, sy = sb["x"] + sb["width"] / 2, sb["y"] + sb["height"] / 2
        dx, dy = db["x"] + db["width"] / 2, db["y"] + db["height"] / 2
        p0 = await self.probe()
        # As a hand does it: press, a small first move (pages start a drag only past a few pixels), then the way over
        # in steps (pages that follow the mouse), a last nudge on the target (HTML5 drops need a dragover there).
        await page.mouse.move(sx, sy)
        await page.mouse.down()
        await page.mouse.move(sx + 6, sy + 6, steps=2)
        await page.mouse.move(dx, dy, steps=12)
        await page.mouse.move(dx + 1, dy + 1)
        await page.mouse.up()
        await self.settle(max_s=3, react=0.4)
        how = ""
        p1 = await self.probe()
        if p0 and p1 and p0["n"] == p1["n"] and p0["t0"] == p1["t0"]:
            # Nothing moved. A page that listens to HTML5 drag events only gets them by script.
            if await src.evaluate("e => !!e.closest('[draggable=true]')", timeout=1500):
                await self.mark()
                h = await src.evaluate_handle("e => e.closest('[draggable=true]')")
                await page.evaluate(DND_JS, [h, await dst.element_handle(timeout=1500)])
                await self.settle(max_s=3, react=0.4)
                how = " (by script: the page did not react to the mouse drag, so its HTML5 drag events were sent)"
        return [f"ok drag {lab(sit, src_t)} -> {lab(dit, dst_t)}{how}"]

    # Loading signs that show now, whether the page came up with them or an action brought them (pb shot waits them
    # out): spinners, progress bars, busy regions, and short "Loading..." texts
    LOADING_SIGNS_JS = r"""() => {
      const shown = (e) => { const r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4 && r.bottom > 0 && r.top < innerHeight
        && (!e.checkVisibility || e.checkVisibility({ checkVisibilityCSS: true, checkOpacity: true })); };
      let n = 0;
      for (const e of document.querySelectorAll('[aria-busy="true"],[role=progressbar],[class*="spinner" i],[class*="loader" i],[class*="loading" i],[id*="loading" i],[id*="spinner" i]'))
        if (e !== document.body && e !== document.documentElement && shown(e) && (e.innerText || '').trim().length < 60) n++;
      const w = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
      for (let t = w.nextNode(), k = 0; t && k < 5000; t = w.nextNode(), k++)
        if (/^\s*(loading|please wait|fetching)\b[^]{0,20}$/i.test(t.nodeValue) && t.parentElement && shown(t.parentElement)) { n++; break; }
      return n;
    }"""

    # pb text --headings: the page's outline, [level, text, shows] of every heading in page order (collapsed ones too)
    HEADINGS_JS = r"""() => {
      const T = (s) => (s || '').replace(/\s+/g, ' ').trim();
      const lvl = (h) => /^H\d$/.test(h.tagName) ? +h.tagName[1] : (+h.getAttribute('aria-level') || 2);
      // the page's own headings: not those of its header, menus, side boxes and footer (pmc: the NIH banner, ACTIONS,
      // RESOURCES, ON THIS PAGE; nytimes: 128 headings of collapsed menus), and a collapsed copy of a heading that
      // shows is not listed again (the guardian)
      const CHROME = 'header,nav,aside,footer,[role=navigation],[role=banner],[role=contentinfo],[role=complementary],[role=menu],[role=dialog]';
      const CLS = /(^|[-_\s])(sidenav|side-nav|sidebar|navbar|masthead|banner|footer|toolbar|breadcrumbs?|menu|megamenu|dropdown|popover|tooltip)([-_\s]|$)/i;
      const chromeish = (h) => { if (h.closest(CHROME)) return true;
        for (let p = h.parentElement, i = 0; p && i < 10 && p !== document.body; p = p.parentElement, i++) if (typeof p.className === 'string' && CLS.test(p.className)) return true;
        return false; };
      const all = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role=heading]')].slice(0, 2000).map(h => {
        const shows = !h.checkVisibility || h.checkVisibility({ checkVisibilityCSS: true });
        return [lvl(h), T(shows ? h.innerText : h.textContent).slice(0, 120), shows, chromeish(h)];
      }).filter(x => x[1]);
      // (collapsed ones are counted, not listed: author pop-ups, closed menus; pb text --section still reads a
      // collapsed section)
      const keep = all.filter(x => !x[3] && x[2]);
      return { hs: keep.map(x => x.slice(0, 3)), left: all.filter(x => x[3]).length, shut: all.filter(x => !x[3] && !x[2]).length };
    }"""

    async def do_headings(self):
        """pb text --headings (pb outline): every heading with its level, indented, in page order. The view leaves out a
        heading with no control under it (a PMC article's Results and Discussion), so this is where the outline is."""
        r = await self.page.evaluate(self.HEADINGS_JS)
        hs, left = r["hs"], r["left"]
        if not hs:
            return ["no headings on this page (no h1 to h6 and no role=heading outside its menus). pb text reads the page"
                    + (f"; {left} headings of its header, menus and footer were left out" if left else "")]
        shut = r.get("shut", 0)
        out = [f"{len(hs)} headings" + (f" ({shut} more in collapsed parts of the page, not listed: pb text --section NAME reads one)" if shut else "")
               + (f"; {left} of the page's header, menus, side boxes and footer left out" if left else "")
               + ' (pb text --section "NAME" reads one):']
        for lv, t, shows in hs[:300]:
            out.append("  " * (max(1, min(lv, 6)) - 1) + f"h{lv} {t}" + ("" if shows else "  (collapsed)"))
        if len(hs) > 300:
            out.append(f"... and {len(hs) - 300} more")
        return ["\n".join(out)]

    async def do_text_section(self, section, start, nth=1):
        r = await self.page.evaluate(SECTION_JS, {"name": section, "nth": nth})
        if not r.get("found"):
            # (short: the dozen names closest to the one asked for, not every heading of the page)
            heads = r.get("heads") or []
            more = r.get("total", len(heads)) - len(heads)
            raise Err(f'no heading like "{section}" on the page. Closest headings: ' + ("; ".join(heads) or "none")
                      + (f" (and {more} more: pb text --headings lists them all)" if more > 0 else "")
                      + f'. Text that is not a heading (a label, a table row): pb text "{section}" --context 3, or pb table "{section}"')
        t = r["text"]
        # The section as a slice of the lines pb text prints (pieces side by side kept apart, shadow roots in place),
        # from the heading's line to the line of the heading that ends it. The walk of SECTION_JS is the fallback; it is
        # all there is for a collapsed section (pb text leaves out what does not show).
        with contextlib.suppress(Exception):
            if r.get("hidden"):
                raise ValueError("collapsed")
            norm = lambda s: re.sub(r"\s+", " ", s).strip()
            lines = (await asyncio.wait_for(self.page.evaluate(TEXT_JS, {"main": True}), 5)).split("\n")
            key = lambda s: re.sub(r"[\s|#]+", "", s).lower()
            # A heading may take more than one line of the text (imdb: "Top Cast" and its count "41" drawn as a block of
            # its own): the heading's line is where one line, or two or three in a row, read as the heading does.
            # -> [(index of its first line, number of lines)]
            def heads_at(h):
                kh, out = key(h), []
                if not kh:
                    return out
                for i in range(len(lines)):
                    acc = ""
                    for k in range(1, 4):
                        if i + k > len(lines):
                            break
                        acc += key(lines[i + k - 1])
                        if acc == kh:
                            out.append((i, k))
                            break
                        if not kh.startswith(acc):
                            break
                return out
            at = heads_at(r["head"])
            # wikipedia, MDN: the heading's words are also an entry of the page's table of contents, and that line comes
            # first. The right line is the one followed by what the walk found under the heading.
            want = key(t)[:30]
            if want and len(at) > 1:
                # (the nearest: the contents entry is followed by the same words too, only further down)
                near = [(key("".join(lines[i + k:i + k + 60])).find(want), (i, k)) for i, k in at]
                at = [ik for pos, ik in sorted(near) if pos >= 0][:1]
            hit = at[min(r["nth"], len(at) - 1)] if at and not want else (at[0] if at else None)
            if hit is not None:
                i0 = hit[0] + hit[1] - 1
                i1 = next((j for j, _ in heads_at(r["end"]) if j > i0), len(lines)) if r["end"] else len(lines)
                inner = set(r["inner"])
                cut = "\n".join(("# " if norm(l) in inner else "") + l for l in lines[i0 + 1:i1])
                if len(key(cut)) >= 0.5 * len(key(t)):      # a slice that lost most of the section is the wrong slice
                    t = cut
        if start >= len(t) and t:
            return [f'(the section "{r["name"]}" has {len(t)} characters: nothing from {start})']
        chunk = t[start:start + 6000]
        q = f'"{section}"' if '"' not in section else f"'{section}'"
        head = f'SECTION "{r["name"]}" ({r["tag"]}, {len(t)} characters' + (f", from {start}" if start else "") + ")"
        if r.get("count", 1) > 1:
            k = r.get("pick", 1)
            head += (f" ({k} of {r['count']} headings by that name, the higher level first; "
                     + (f"the next: pb text --section {q} --nth {k + 1}" if k < r["count"] else f"the first: pb text --section {q}") + ")")
        if r.get("hidden"):
            # (the page may load the rest of a collapsed section only when it is opened: dailymed)
            opener = None
            with contextlib.suppress(Exception):
                opener = await self.page.evaluate("""() => { const T = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                    const c = [...document.querySelectorAll('button,a,[role=button],summary')].find(e => /^(view|show|expand|open) (all|more)\\b|^expand\\b/i.test(T(e.innerText))
                      && e.getClientRects().length && (!e.checkVisibility || e.checkVisibility({ checkVisibilityCSS: true })));
                    return c ? [T(c.innerText).slice(0, 40), c.getAttribute('data-pb') || ''] : null; }""")
            # (by its ref when the last scan gave it one: dailymed has two "VIEW ALL SECTIONS", and the name was ambiguous)
            how = (f'pb click {opener[1]} ("{opener[0]}")' if opener and opener[1] else f'pb click "{opener[0]}"' if opener else "")
            head += (" (in a collapsed part of the page, read from what of it is loaded; "
                     + (f"{how} shows it all)" if how else "a click on what expands it shows it all)"))
        head += ":"
        tail = (f"\n... (the section has {len(t)} characters; continue: pb text --section {q} --from {start + 6000})"
                if start + 6000 < len(t) else "")
        return [head + "\n" + (chunk or "(no text under it)") + tail]

    # ---- reading the page (pb text, pb items): what a visitor reads, in every frame that shows
    @staticmethod
    def frame_path(fr):
        """Where a frame sits in the tree of frames, as positions from the top: sorts frames in document order."""
        path = []
        while fr.parent_frame is not None:
            p = fr.parent_frame
            try:
                path.append(p.child_frames.index(fr))
            except ValueError:
                path.append(999)
            fr = p
        return path[::-1]

    @staticmethod
    def frame_label(fr):
        """A frame as pb text names it: its name, else its address without the query."""
        if fr.name:
            return fr.name[:40]
        u = fr.url.split("?")[0].split("#")[0]
        if not re.match(r"^https?://", u):
            return "frame"
        return (host_of(u) + "/" + u.split("://", 1)[-1].partition("/")[2])[:50].rstrip("/")

    async def read_wait(self, max_s=6.0):
        """The reading commands (text, links, table, items) read the finished page: while the document is loading or
        the site's own requests are pending, wait for them, at most max_s (1 s on a page that ran out the full wait
        before). Returns a NOTE line when it gave up waiting, else ''."""
        t0 = time.time()
        while True:
            p = await self.probe()
            if p is not None and p["rs"] != "loading" and not self.own_pending(12.0, p["ld"]):
                return ""
            if p is not None and self.read_gave_up == (p.get("t0"), self.page.url) and time.time() - t0 > 1.0:
                break
            if p is not None and p["rs"] != "loading" and p["now"] - p["t0"] > 8000 and not p["ld"] and time.time() - t0 > 1.0:
                # finance.yahoo.com: a page that has been up for a while and still has requests out is one that keeps
                # fetching (quotes, feeds), not one that is still coming: each first read of a page cost 6 s there
                break
            if time.time() - t0 >= max_s:
                if p is not None:
                    self.read_gave_up = (p.get("t0"), self.page.url)
                break
            await asyncio.sleep(0.1)
        return (f"NOTE the page was still loading after {time.time() - t0:.0f} s (its own requests pending): this is what had "
                "loaded. Run the command again for the rest, or pb wait TEXT for what you expect")

    async def doc_kind(self):
        """(content type, characters) of the page when it is not a web page (a JSON, text, XML or PDF document), else None."""
        with contextlib.suppress(Exception):
            ct, n = await asyncio.wait_for(self.page.evaluate(DOCKIND_JS), 3)
            ct = ct.split(";")[0].strip().lower()
            if ct and "html" not in ct:
                return ct, n
        return None

    @staticmethod
    def doc_words(ct):
        if ct == "application/pdf":
            return "a PDF document"
        if "json" in ct:
            return "a JSON document"
        if "xml" in ct:
            return "an XML document"
        if ct == "text/plain":
            return "a plain text document"
        if ct == "text/csv":
            return "a CSV document"
        if "javascript" in ct:
            return "a script file"
        return f"a {ct} document"

    async def pdf_text(self, path=None):
        """The text of the PDF the tab shows: the file saved (as pb download does) into a temporary directory, then read
        with pdftotext. path: a PDF already saved (one the page sent as a download). Returns (text or None, a line that
        says where the file is and how it was read)."""
        import shutil
        import tempfile
        if path is None and file_url_path(self.page.url) is not None and os.path.isfile(file_url_path(self.page.url)):
            path = slash(file_url_path(self.page.url))        # a PDF on this machine (file:): read where it is
            local = True
        else:
            local = False
        if path is None:
            d = tempfile.mkdtemp(prefix="pb-pdf-")
            await self.fetch_to_file(self.page.url, d)
            names = os.listdir(d)
            path = slash(os.path.join(d, names[0])) if names else d
        w = "on this machine, at" if local else "saved to"
        exe = shutil.which("pdftotext") or next((p for p in (r"C:\Program Files\Git\mingw64\bin\pdftotext.exe",
                                                               "/usr/bin/pdftotext", "/opt/homebrew/bin/pdftotext") if os.path.exists(p)), None)
        if not exe:
            return None, (f"(a PDF document, {w} {path}. pdftotext is not installed, so pb cannot read it: install poppler "
                          "(Git for Windows has it in /mingw64/bin), or read the file with another PDF tool)")
        proc = await asyncio.create_subprocess_exec(exe, "-enc", "UTF-8", path, "-", stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.DEVNULL)
        try:
            data, _ = await asyncio.wait_for(proc.communicate(), 60)
        except asyncio.TimeoutError:
            proc.kill()
            return None, f"(a PDF document, {w} {path}; pdftotext took over 60 s, so there is no text)"
        t = data.decode("utf-8", "replace").replace("\f", "\n")
        if not t.strip():
            return None, f"(a PDF document, {w} {path}; it has no text layer: it is scanned images. pb shot shows a page)"
        return t, f"(a PDF document, {w} {path}, read with pdftotext)"

    async def text_chunks(self):
        """[(frame label, text)] of the main frame ("") and every frame that shows, in document order, and the kind of
        document the page is (doc_kind). Only frames a person can see: payment, captcha and tag-manager frames that hold
        nothing but script flooded the answer with their source."""
        page = self.page
        frames = [page.main_frame] + await self.visible_frames()
        frames.sort(key=self.frame_path)
        texts = await asyncio.gather(self.doc_kind(), *(asyncio.wait_for(fr.evaluate(TEXT_JS, {"main": fr is page.main_frame}), 3)
                                                        for fr in frames), return_exceptions=True)
        kind, texts = texts[0] if not isinstance(texts[0], BaseException) else None, texts[1:]
        return [("" if fr is page.main_frame else self.frame_label(fr), t) for fr, t in zip(frames, texts)
                if isinstance(t, str) and t.strip()], kind

    async def do_text(self, rx, start, ctx_n=1):
        tail = []
        if self.pdf_dl and self.pdf_dl[1] == self.page.url and os.path.isfile(self.pdf_dl[0]):
            # the last command's link or address was a PDF the site sent as a download, or one pb download saved
            # (dailymed): that is what was opened, so that is what is read, ahead of what the tab shows (a PDF opened
            # before it, from the disk); the page itself is still there for pb view
            t, line = await self.pdf_text(slash(self.pdf_dl[0]))
            line = (line.replace("(a PDF document, saved to", "(the PDF the last command downloaded, at").rstrip(")")
                    + f": this answer is read from that file, not from the page. The tab still shows {self.page.url[:120]};"
                    " a pb text after this one reads that page)")
            self.pdf_dl = None                 # only this once (dailymed: later reads meant for the page got the PDF)
            chunks, tail, kind = ([("", t)] if t else []), [line], None
            if not t:
                return tail
        else:
            chunks, kind = await self.text_chunks()
            if kind and kind[0] == "application/pdf":
                t, line = await self.pdf_text()
                chunks, tail = ([("", t)] if t else []), [line]
                if not t:
                    return tail
        if rx is None:
            parts = []
            for label, t in chunks:
                t = re.sub(r"\n\s*\n+", "\n", t).strip("\n")
                parts.append((f"[frame {label}]\n" if label else "") + t)
            t = "\n".join(parts)
            if start:
                if start >= len(t):
                    return [f"(the page text has {len(t)} characters: nothing from {start})"]
                t = t[start:]
            more = f", or continue: pb text --from {start + 4000}"
            return [t[:4000] + (f"\n... ({len(t) + start} chars total; use pb text REGEX{more})" if len(t) > 4000 else "")] + tail
        # A matched line is shown whole up to LONG characters (an abstract's paragraph is 1500 to 2500); a longer one as
        # the sentences around the match, about WINDOW characters (the end of a paragraph was cut off before: europepmc,
        # semanticscholar, uspstf). A line next to a match is shown up to NEAR.
        LONG, WINDOW, NEAR = 3000, 1600, 300
        cut = lambda l, n: l if len(l) <= n else l[:n] + f"... ({len(l) - n} more characters)"

        def around(l):
            if len(l) <= LONG:
                return l
            m = rx.search(l)
            a = max(0, m.start() - WINDOW // 2) if m else 0
            b = min(len(l), a + WINDOW)
            a = max(0, b - WINDOW)
            # widen to whole sentences when one ends close by
            s0 = max(l.rfind(". ", 0, a + 1), l.rfind("? ", 0, a + 1), l.rfind("! ", 0, a + 1))
            if s0 >= 0 and a - s0 < 300:
                a = s0 + 2
            ends = [i for i in (l.find(". ", b), l.find("? ", b), l.find("! ", b)) if i >= 0]
            if ends and min(ends) - b < 300:
                b = min(ends) + 1
            return ((f"({a} characters before) ..." if a else "") + l[a:b]
                    + (f" ... ({len(l) - b} more characters)" if b < len(l) else ""))
        out, hits, full, in_table = [], 0, False, False
        for label, t in chunks:
            doc = not label and kind is not None          # the lines of a JSON or text document are its content, not code
            lines = [l for l in (ZERO_WIDTH.sub("", x).strip() for x in t.split("\n")) if l and (doc or not code_like(l))]
            # A line repeated right next to itself is one line with a count. A line repeated elsewhere stays where it is,
            # so that each match is read with its own neighbours (one card's time with that card's name).
            runs = []
            for l in lines:
                if runs and runs[-1][0] == l:
                    runs[-1][1] += 1
                else:
                    runs.append([l, 1])
            match = [bool(rx.search(l)) for l, _ in runs]
            hits += sum(n for (l, n), m in zip(runs, match) if m)
            keep = sorted({j for i, m in enumerate(match) if m for j in range(i - ctx_n, i + ctx_n + 1) if 0 <= j < len(runs)})
            in_table = in_table or any(m and " | " in l for (l, _), m in zip(runs, match))
            last = None
            for i in keep:
                if full:
                    break
                if out and (last is None or i != last + 1):
                    out.append("...")
                l, n = runs[i]
                out.append((f"[{label}] " if label else "") + (around(l) if match[i] else cut(l, NEAR)) + (f"  (x{n})" if n > 1 else ""))
                last = i
                full = len(out) >= 300
        # the count comes first, so a caller that cuts the output short still knows how much there was
        if not out:
            pat = getattr(rx, "pattern", "")
            return [f"(no text matches /{pat}/; all the words given are one pattern)" if " " in pat else "(no text matches)"] + tail
        near = ("the line before and after; --context N for more" if ctx_n == 1 else f"{ctx_n} lines before and after" if ctx_n
                else "no lines around")
        head = (f"{hits} line{'s' if hits != 1 else ''} match{'' if hits != 1 else 'es'} (each shown with {near}"
                + ("; a match is a table row: pb table TEXT prints its table" if in_table else "") + "):")
        body = "\n".join(out)
        CAP = 10000                             # (room for a few whole abstracts)
        if len(body) > CAP or full:             # a broad pattern on a big page: keep the answer readable
            body = (body[:CAP].rsplit("\n", 1)[0] + f"\n... (cut at {CAP} characters of {len(body)}{' and more' if full else ''}. Narrow the "
                    "pattern, or read one part: pb text --section HEADING, pb table TEXT, pb items REGEX for a list of results)")
        return [head, body] + tail

    async def do_text_of(self, target):
        """pb text --of TARGET: the whole text of one element, then its useful attributes (link address, value, date...)."""
        loc, it = await self.find_any(target, "click")
        if re.fullmatch(r"e\d+", target) and (await self.look(loc, scroll=False)).get("gone"):
            # a ref whose element the page re-rendered: say so at once, as click does (it waited 5 s, then timed out)
            raise Err(f"{target} is no longer on the page (the page re-rendered that part or moved on). Take a fresh ref: pb view, or pb find TEXT")
        r = await loc.evaluate(OF_JS, timeout=5000)
        t = r["text"]
        if len(t) > 4000:
            t = t[:4000] + f"\n... ({len(r['text']) - 4000} more characters; pb text --section HEADING or pb text REGEX for a part)"
        name = f'{it.get("ref", "")} {it.get("k", "")}'.strip() if it.get("k") not in (None, "text", "css") else r["tag"]
        head = f"TEXT of {name} ({len(r['text'])} characters):" if t else f"{name} has no text of its own"
        return [head] + ([t] if t else []) + [f"{k}: {v}" for k, v in r["attrs"]]

    async def do_items(self, a):
        """pb items [REGEX] [--n N] [--from K] [--in TARGET]: the repeated cards or rows of the page (see ITEMS_JS)."""
        usage = "usage: pb items [REGEX] [--n N] [--from K] [--in TARGET] (TARGET: a ref, css=SELECTOR, a group named by pb items, or text)"
        n, frm, pick, words, i = 10, 1, None, [], 0
        while i < len(a):
            x = a[i]
            if x in ("--n", "--from", "--in"):
                if i + 1 >= len(a) or (x != "--in" and not a[i + 1].isdigit()):
                    raise Err(usage)
                if x == "--in":
                    pick = a[i + 1]
                elif x == "--n":
                    n = max(1, int(a[i + 1]))
                else:
                    frm = max(1, int(a[i + 1]))
                i += 2
            else:
                words.append(x)
                i += 1
        pat = " ".join(words)
        try:
            rx = re.compile(pat, re.I) if pat else None
        except re.error as e:
            raise Err(f"pb items: {pat!r} is not a valid pattern ({e})")
        arg = {"pick": None}
        if pick:
            arg["pick"] = ({"ref": pick} if re.fullmatch(r"e\d+", pick) else {"css": pick[4:]} if pick.startswith("css=")
                           else {"label": pick})
        page = self.page
        with contextlib.suppress(Exception):
            await self.collect()                # the links carry refs then, and pb click knows them
        frames = [page.main_frame] + await self.visible_frames()
        frames.sort(key=self.frame_path)
        res = await asyncio.gather(*(asyncio.wait_for(fr.evaluate(ITEMS_JS, arg), 8) for fr in frames), return_exceptions=True)
        got = [(fr, r) for fr, r in zip(frames, res) if isinstance(r, dict)]
        if pick and not any(r.get("items") for _, r in got):
            err = next((r["error"] for _, r in got if r.get("error")), None)
            if err:
                raise Err(f"--in {pick}: {err}")
            if any(r.get("outside") for _, r in got):
                raise Err(f'"{pick}" is on the page, but in no group of three or more repeated items. pb text --of "{pick}" reads that element')
            raise Err(f'nothing on the page matches "{pick}" (no group of that name, no element, no visible text). pb items lists the groups')
        best = max(((fr, r) for fr, r in got if r.get("items")), key=lambda x: x[1]["score"], default=None)
        if best is None:
            nl = next((r for _, r in got if r.get("noList")), None)
            if nl:
                said = nl.get("said") or []
                return ["no result list on this page" + (": it says " + " ".join(f'"{s}"' for s in said) if said else "")
                        + f" (the largest group is {nl['noList']} blocks of different kinds: page parts, not records). pb text reads the page"]
            if any(r.get("lines") for _, r in got):
                return ["no repeated cards on this page (one result?): the largest group is lines of one block. pb text reads it"]
            return ["no repeated items on this page (no three or more sibling elements of one kind with text). pb text, pb table or pb links may read it"]
        fr, r = best
        where = f" [frame {self.frame_label(fr)}]" if fr is not page.main_frame else ""
        others = [f"{k} x {lab}" for lab, k, _ in r["others"]]
        if not pick:
            others += [f"{x['n']} x {x['label']} [frame {self.frame_label(f2)}]" for f2, x in got if x is not r and x.get("items")][:3]
        total = len(r["items"])
        listed = [(k, it) for k, it in enumerate(r["items"], 1) if rx is None or rx.search(it[0])]
        head = (f"{len(listed)} of {total} items match /{pat}/" if rx else f"{total} items") + f" ({r['label']}){where}"
        if r.get("left"):
            head += f"; {r['left']} other block{'s' if r['left'] > 1 else ''} left out (no link or text like the rest)"
        if others:
            head += "; other groups: " + ", ".join(others[:6]) + " (pb items --in GROUP picks one)"
        later = [(k, it) for k, it in listed if k >= frm]
        shown = later[:n]
        out = [head]
        if not shown:
            out.append(f"(none from item {frm})" if listed else "(no item matches; pb items without a pattern lists them all)")
        for k, it in shown:
            t, u, ref = it[0], it[1], (it[2] if len(it) > 2 else "")
            # "#1": the record's number, apart from a rank the site prints itself ("31." on Hacker News)
            out.append(f"#{k} {t or '(no text)'}")
            if u:
                # Amazon's sponsored redirects run to 1.5 KB: six of them used up the answer. The ref first: pb click eN
                # opens the record
                r0 = f"{ref} " if ref and ref in self.refs else ""
                # a long address (ebay's 550-character tracking links, ten records no longer fit): its scheme, host, path and
                # the start of its query, and the ref that opens it
                if len(u) > 200:
                    from urllib.parse import urlsplit
                    with contextlib.suppress(Exception):
                        sp = urlsplit(u)
                        short = f"{sp.scheme}://{sp.netloc}{sp.path[:120]}" + (f"?{sp.query[:40]}..." if sp.query else "")
                        u = short + (f" (link shortened; pb click {ref} opens it)" if r0 else " (link shortened; pb links gives it whole)")
                out.append(f"   -> {r0}{u}")
        if len(later) > len(shown):
            rest = len(later) - len(shown)
            out.append(f"(showing {len(shown)} of {len(listed)}, from item {shown[0][0]}; pb items {repr(pat) + ' ' if pat else ''}--from "
                       f"{later[len(shown)][0]} for more" + (f", add --n {rest} for the other {rest} at once" if rest <= 60 else "") + ")")
        body = "\n".join(out)
        if len(body) > 6000:
            body = body[:6000].rsplit("\n", 1)[0] + f"\n... (cut at 6000 characters; pb items --n with a smaller N, or a REGEX)"
        return [body]

    async def masks(self):
        """Paint-over masks for a screenshot: card fields and card numbers in every frame that shows (see MASK_JS)."""
        frames = [self.page.main_frame] + await self.visible_frames()
        exps = self.exp_spellings()
        counts = await asyncio.gather(*(asyncio.wait_for(fr.evaluate(self.MASK_JS, exps), 3) for fr in frames), return_exceptions=True)
        return [fr.locator("[data-pb-mask]") for fr in frames], sum(c for c in counts if isinstance(c, int))

    # ---- command dispatch
    async def run(self, args, batch=False):
        """Returns (status_lines, observe) where observe says whether a delta should follow."""
        cmd, a = args[0], args[1:]
        page = self.page
        self.pick_nth = None
        flags = self.FLAGS.get(cmd)
        if flags is not None:
            # `text --help` in a batch was searched for as text ("no text matches"): an option the command does not have
            # is an error that names the ones it has. After a bare "--" every word is taken as it is (a pattern that
            # starts with dashes).
            cut = a.index("--") if "--" in a else len(a)
            bad = next((x for x in a[:cut] if x.startswith("--") and x not in flags), None)
            if bad:
                raise Err(f"pb {cmd} has no option {bad}. Its options: " + (" ".join(sorted(flags)) or "none")
                          + (f". A pattern or text that starts with dashes goes after a bare --: pb {cmd} -- {bad}" if cmd in ("text", "find", "items", "links") else ""))
            if cut < len(a):
                a = a[:cut] + a[cut + 1:]
        if cmd in ("view", "find", "text", "read", "items", "links", "table") and any(x in ("-i", "--ignore-case") for x in a):
            # `pb view --grep -i "..."` took -i for the pattern. Every pattern is matched ignoring case already.
            a = [x for x in a if x not in ("-i", "--ignore-case")]
        if cmd in ("open", "goto"):
            if not a:
                raise Err("usage: pb open URL")
            url = a[0] if re.match(r"^[a-z]+:", a[0]) else "https://" + a[0]
            self.base = None
            self.cover_said.clear()            # a page opened afresh: what covers its targets is said in full again
            # (opened in this tab: not "in a NEW TAB", which a tab event from before had left set on an about:blank tab)
            self.tab_switched = False
            doc = {}                           # how the server answered for the page itself

            def on_doc(resp):
                with contextlib.suppress(Exception):
                    if resp.request.is_navigation_request() and resp.frame is page.main_frame:
                        doc["status"], doc["auth"] = resp.status, resp.headers.get("www-authenticate", "")

            page.on("response", on_doc)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            except Exception as e:
                # an address that is a file, not a page: the browser downloads it (see save_download)
                if "Download is starting" not in str(e):
                    if doc.get("status") == 401 or (doc.get("auth") and "ERR_HTTP_RESPONSE_CODE_FAILURE" in str(e)):
                        with_login = re.sub(r"^([a-z]+://)", r"\1USER:PASSWORD@", url)
                        raise Err(f"{host_of(url)} asks for a login before it shows this page (HTTP 401, {doc.get('auth', '')[:60] or 'HTTP authentication'}). "
                                  f"Put the user and password in the address: pb open {with_login[:140]}")
                    if "ERR_HTTP_RESPONSE_CODE_FAILURE" in str(e) and doc.get("status"):
                        raise Err(f"{host_of(url)} answered HTTP {doc['status']} with no page for {url[:140]}")
                    why = explain_open_error(str(e), url)      # the bare browser error told agents nothing they could act on
                    if why:
                        raise Err(why)
                    raise
                # (saved before the next step of a batch: `open PDF; text X` reads it)
                with contextlib.suppress(Exception):
                    await asyncio.sleep(0.2)
                    live = [t for t in self.dl_pending if not t.done()]
                    if live:
                        await asyncio.wait(live, timeout=60)
                return [f"ok open {url}: that address is a file, so it was downloaded, not shown"], "delta"
            finally:
                with contextlib.suppress(Exception):
                    page.remove_listener("response", on_doc)
            await self.settle(max_s=5)
            self.note_plain_http()
            # the-internet /status_codes/404: an error page looks like any page, and the status was nowhere in the answer.
            # It is read when the answer is written (execute), from the page that shows then: a challenge page answered
            # 403 that passes by itself and loads the real page (stackoverflow.com) is not an error page.
            self.status_due = True
            norm = lambda u: re.sub(r"^www\.", "", u.split("://", 1)[-1].split("?")[0].split("#")[0].rstrip("/").lower())
            if norm(self.page.url) != norm(url):
                # kroger: the cart URL landed on login.kroger.com and nothing said so
                with contextlib.suppress(Exception):
                    items, meta = await self.collect()
                    wall = self.wall_note(items, meta)
                    self.notes.append(f"redirected: asked for {url[:100]}, landed on {self.page.url[:100]}" + (f". {wall}" if wall else ""))
            kind = await self.doc_kind()
            if kind:
                # a JSON answer, a text, XML or PDF file: the view has no controls to list, so say what it is
                if kind[0] == "application/pdf" and file_url_path(self.page.url) is not None:
                    self.notes.append("a PDF document on this machine (Chrome's PDF viewer, which pb cannot look into): pb text "
                                      "prints its text, read from the file, and pb text REGEX searches it")
                elif kind[0] == "application/pdf":
                    self.notes.append("a PDF document (Chrome's PDF viewer, which pb cannot look into): pb text saves the file and "
                                      "prints its text, pb text REGEX searches it, pb download URL keeps a copy")
                else:
                    self.notes.append(f"{self.doc_words(kind[0])}, {kind[1]} characters: pb text prints it, pb text REGEX searches it")
            return [f"ok open {url}"], "view"
        if cmd == "view":
            grep = None
            if "--grep" in a:
                grep = re.compile(a[a.index("--grep") + 1], re.I)
            # --all --grep: the filter over the full list (--all alone dropped it)
            return [], (("grep", grep, "--all" in a) if grep else "viewall" if "--all" in a else "view")
        grx = None
        if cmd in ("find", "text", "read") and "--grep" in a[:-1]:
            # samsung: `pb do '...; find usb-c cable' --grep 'usb|cable'` and `pb text RE --grep X`: the flag became part
            # of the text searched for. Here it narrows the answer, as it does for pb view.
            i = a.index("--grep")
            grx = re.compile(a[i + 1], re.I)
            a = a[:i] + a[i + 2:]
        if cmd == "find":
            if not a:
                raise Err("usage: pb find TEXT")
            items, _ = await self.collect()
            q = " ".join(a)
            scored = sorted(((self.score(q, it, "any"), i, it) for i, it in enumerate(items)), key=lambda x: (-x[0], x[1]))
            hits = [x[2] for x in scored if x[0] > 0]
            if grx is not None:
                hits = [it for it in hits if grx.search(self.line(it))]
            hits = hits[:14]
            if not hits and grx is None:
                # plain text that may react to a click (a sortable table header): listed, marked as not a control
                with contextlib.suppress(Exception):
                    if await self.text_locator(q, exact_only=True) is not None:
                        return [f'text "{q[:80]}" (plain text, not a control; pb click "{q[:80]}" clicks it, pb hover too)'], None
            if not hits:
                if self.in_batch:              # in pb do, a find that finds nothing stops the batch like any failed step
                    raise NotFound(f'no element matches "{q}" (pb text "{q}" searches static text; `try find` does not stop the batch)')
                return [f'no element matches "{q}" (pb text "{q}" searches static text)'], None
            hrefs = await self.hrefs([it for it in hits if it["k"] == "link"])
            return [self.line(it) + (f"  -> {hrefs[it['ref']]}" if hrefs.get(it.get("ref")) else "")
                    + (f'  [under "{it["sec"]}"]' if it.get("sec") else "") + (f"  [frame {it['fr']}]" if it.get("fr") else "") for it in hits], None
        if cmd in ("click", "check", "uncheck", "fill", "select", "secret"):
            need = {"click": 1, "check": 1, "uncheck": 1, "fill": 2, "select": 2, "secret": 2}[cmd]
            if len(a) < need:
                raise Err(f"usage: pb {cmd} TARGET" + (" VALUE" if need == 2 else ""))
            button, a = click_kind(a) if cmd == "click" else (None, a)
            pick = None
            if cmd == "fill" and "--pick" in a:
                # pb fill TARGET VALUE --pick [TEXT]: the words after it, up to the next --option, name the suggestion
                i = j = a.index("--pick")
                j += 1
                while j < len(a) and not a[j].startswith("--"):
                    j += 1
                pick, a = " ".join(a[i + 1:j]), a[:i] + a[j:]
            near, a = take_near(a)
            self.pick_nth = None
            if "--nth" in a:
                # several equal matches in one block (the-internet: three Delete buttons) that --near cannot tell apart
                i = a.index("--nth")
                if i + 1 >= len(a) or not a[i + 1].isdigit() or int(a[i + 1]) < 1:
                    raise Err(f"usage: pb {cmd} TARGET --nth N (the Nth of the equal matches, in page order, from 1)")
                self.pick_nth, a = int(a[i + 1]), a[:i] + a[i + 2:]
            if near and not a and cmd in ("check", "uncheck"):
                a = [near]                     # pb check --near "Buy milk": the box in the row of that text
            if len(a) < need:
                raise Err(f"usage: pb {cmd} TARGET" + (" VALUE" if need == 2 else ""))
            if need == 1 and len(a) > 1:
                if a[0].startswith("css=") or re.fullmatch(r"e\d+", a[0]):
                    # `click css=X, click Y`: a comma or space used where pb do wants ';'. Acting on part of it would
                    # either fail on a broken selector or act on the wrong thing
                    raise Err(f"{cmd} takes one target, but got {' '.join(a)[:80]!r}. In pb do, separate steps with ';', and quote "
                              "a target that has spaces")
                a = [" ".join(a)]              # pb click Add to cart: the words are one text
            purpose = {"click": "click", "check": "check", "uncheck": "check"}.get(cmd, "fill")
            async def act(loc, it, known):
                label = it.get("t", "") if it.get("k") == "css" else f'{it.get("ref", "")} {it.get("k", "")} "{it.get("t", "")}"'.strip()
                self.dirty = True
                st = await self.look(loc)
                if st.get("gone"):
                    if known and cmd != "fill":
                        # a ref from the last scan whose element is gone: say so at once, do not look for a stand-in (a field
                        # is looked for again: one rebuilt with the same name is the same field, see refind)
                        raise Err(f"{a[0]} is no longer on the page (the page re-rendered that part or moved on). "
                                  "Take a fresh ref: pb view, or pb find TEXT")
                    raise Gone()
                if cmd == "click":
                    if (it.get("k") in ("button", "link", "click", "css") or it.get("dis")) and st["dis"]:
                        # clicking it does nothing, and waiting for it to wake up costs seconds: say what is the matter
                        raise Err(f"{label} is disabled, so nothing was clicked. Something the page requires is still missing: "
                                  "pb review lists required fields that are empty or invalid")
                    # A link that opens a new tab (product links on macys, etsy, ebay): the tab can take a second to
                    # appear, long after this page has gone quiet. Knowing it is coming, wait for it, so the answer
                    # describes the new page and the next step of a batch runs there.
                    blank = False
                    with contextlib.suppress(Exception):
                        blank = await loc.evaluate("e => { const a = e.closest('a,area'); return !!(a && a.target && !/^_(self|top|parent)$/i.test(a.target)); }",
                                                   timeout=800)
                    tabs_before = len(self.ctx.pages)
                    with self.span("act"):
                        how = await (self.do_mouse_click(loc, st, button) if button else self.do_click(loc, it, st))
                    if blank:
                        t0 = time.time()
                        while len(self.ctx.pages) <= tabs_before and time.time() - t0 < 3:
                            await asyncio.sleep(0.05)
                    if len(self.ctx.pages) > tabs_before:
                        self.base = None           # a new tab took over: wait for its page as for any new page
                        t0 = time.time()
                        while self.page.url in ("", "about:blank") and time.time() - t0 < 4:
                            await asyncio.sleep(0.05)
                    await self.settle()
                    if it.get("k") == "text":
                        return [f"ok {how} {label} (plain text, not a control: no button or link has these words; check that it "
                                "did something)"], "delta"
                    return [f"ok {how} {label}"], "delta"
                if cmd in ("check", "uncheck"):
                    with self.span("act"):
                        await self.do_check(loc, it, cmd == "check", st)
                    await self.settle(max_s=2, quiet=0.25, react=0.3)
                    return [f"ok {cmd} {label}"], "delta"
                if cmd == "fill":
                    value = " ".join(a[1:])
                    if st.get("tag") == "SELECT" and pick is None:
                        # a dropdown named by fill: typing into it only moved its type-ahead (selenium.dev left "Three")
                        with self.span("act"):
                            shown = await self.do_select(loc, it, value, st)
                        await self.settle(max_s=2, react=0.3)
                        return [f'ok select {label} -> shows "{shown}" (a dropdown: pb fill did what pb select does)'], "delta"
                    if st.get("tag") == "INPUT" and st.get("type") == "file":
                        if not os.path.isfile(local_path(value, self.cwd)):
                            raise Err(f"{label} is a file field: use pb upload TARGET FILE (no file {value!r} in {slash(self.caller_dir())})")
                        return await self.do_upload(a[0], [value]), "delta"
                    kind = it.get("it") or (st.get("type") if st.get("tag") == "INPUT" else "")
                    if it.get("k") == "css" and st.get("tag") != "INPUT":
                        kind = await loc.evaluate("e => e.getAttribute('role') === 'slider' ? 'slider' : ''", timeout=1500)
                    if kind in ("range", "slider") or kind in VALUE_FORMATS:
                        with self.span("act"):
                            line = await self.fill_special(loc, kind, value, label)
                        await self.settle(max_s=1.5, quiet=0.15, react=0.2)
                        return [line], "delta"
                    if not st.get("edit") and st.get("tag") not in ("INPUT", "TEXTAREA", "SELECT", ""):
                        # a css= or ref target that is a form, a list, a box holding several fields: typing at it would
                        # land in whatever its middle holds, or nowhere, and the answer read as ok
                        what = None
                        with contextlib.suppress(Exception):
                            what = await loc.evaluate(self.NOT_FIELD_JS, timeout=1500)
                        if what:
                            hint = ("; quote a selector that has spaces: pb fill \"css=#a b\" VALUE"
                                    if a[0].startswith("css=") and len(a) > 2 else "")
                            raise Err(f"{a[0]} is a {what}, not a field, so nothing was typed. Name the field itself "
                                      f"(pb find TEXT, or css= of the input){hint}")
                    if pick is not None:
                        # a state field's suggestion list: a US state code is typed and picked as the state's name
                        typed, want = value, pick
                        if (len(value.strip()) == 2 and state_alts(value) and pick in ("", value)
                                and re.search(r"\bstate\b", " ".join([label, it.get("name", ""), it.get("id", "")]), re.I)):
                            typed = want = state_alts(value)[0]
                        with self.span("act"):
                            return [await self.fill_pick(loc, it, st, typed, want, label)], "delta"
                    words =" ".join([it.get("t", ""), it.get("name", ""), it.get("ph", "")])
                    keys = it.get("it") in ("combobox", "search") or it.get("k") == "combo" or (
                        it.get("it") in ("text", None) and bool(re.search(r"search", words, re.I)))
                    # search boxes and address fields answer after a typing pause (suggestions): give those time to start
                    suggests = it.get("it") == "combobox" or it.get("k") == "combo" or (
                        it.get("it") in ("text", "search", None) and re.search(r"search|address|street|zip|postal|location|find", words, re.I)
                        and not re.search(r"e-?mail", words, re.I))
                    sfr = self.refs[it["ref"]][0] if it.get("ref") in self.refs else self.page.main_frame
                    if suggests:
                        # what is clickable now, to tell the suggestions the typing brings up (see the hint below)
                        with contextlib.suppress(Exception):
                            await asyncio.wait_for(sfr.evaluate(self.SUG_JS, ["mark", False]), 2)
                    # a text field for a date (its words say so): typed with real keys, then left as a person leaves it
                    dateish = (it.get("it") in ("text", None) and not suggests and bool(re.search(r"(?<![a-z])date", words, re.I))
                               and not str(it.get("ac", "")).startswith("cc-"))
                    # a date typed into a plain text field (Google Flights' "Departure"): the calendars that show before
                    # the typing, to tell one the fill opens and leaves open (close_left_picker)
                    datey = (it.get("it") in ("text", None) and not suggests and not str(it.get("ac", "")).startswith("cc-")
                             and (dateish or field_value("date", value) is not None))
                    pickers_before = None
                    if datey:
                        with contextlib.suppress(Exception):
                            pickers_before = (await asyncio.wait_for(sfr.evaluate(self.PICKERS_JS), 1.5))[0]
                    with self.span("act"):
                        actual = await self.do_fill(loc, value, keys=keys or dateish, st=st)
                    picker = False
                    if not suggests and it.get("it") in ("text", None):
                        with contextlib.suppress(Exception):
                            picker = await asyncio.wait_for(sfr.evaluate(self.PICKER_JS), 1.5)
                    if dateish or picker or pickers_before is not None:
                        # (a date in a field whose label does not say so: the page may take it only once the field is
                        # left; Google Flights opened its calendar over the next click, on Search, instead)
                        actual = await self.leave_date_field(loc, value, label, actual)
                    closed = ""
                    if pickers_before is not None:
                        await self.settle(max_s=1.0, quiet=0.15, react=0.3, net=False)      # a calendar slides in
                        with self.span("calendar left open"):
                            closed = await self.close_left_picker(sfr, loc, label, pickers_before, actual)
                    if suggests:
                        await self.settle(max_s=2.5, quiet=0.25, react=0.75)
                        # suggestions opened: the answer ends with how to choose one (execute adds it, see sugg_hint)
                        sug = await self.sug_list(sfr)
                        if sug["items"] and sug["kind"] != "datalist":
                            t1 = sug["items"][0]["t"][:60]
                            self.sugg_hint = (t1, f'suggestions open: pb click "{t1}" (or another entry), or pb fill {self.quote_arg(a[0])} '
                                                  f'{self.quote_arg(value)} --pick "TEXT"')
                    else:
                        await self.settle(max_s=1.5, quiet=0.15, react=0.15, net=False)
                    secretish = str(it.get("v", "")).startswith("•") or it.get("it") == "password" or st.get("type") == "password"
                    if actual is None or actual == value:
                        note = ""
                    elif secretish:
                        note = f" (field now holds {len(actual)} characters)"         # a card or password field: never echo it
                    else:
                        nz = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
                        if not (nz(actual) == nz(value) or (nz(value) and nz(actual).startswith(nz(value))) or re.search("[*" + chr(0x2022) + "]", actual)
                                or (pickers_before is not None and same_date(value, actual))):
                            # the field did not take what was typed (a length limit, a script that rejects it)
                            if not actual.strip() and value.strip():
                                raise Err(f"{label}: nothing stayed in the field after typing (the page emptied it, or it takes no "
                                          "typing). Look at it with pb view, or pick from what it offers")
                            return [f'fill {label}: the field holds "{actual}", not what was typed ("{value}"). It may cut or '
                                    "reformat what it takes: check it before going on"], "delta"
                        note = f' (field now shows "{actual}")'
                    return [f"ok fill {label}{note}{closed}{getattr(self, 'fill_leak', '')}"], "delta"
                if cmd == "select":
                    extra = ""
                    if st.get("tag") == "INPUT" and len(a) == 2:
                        # a dropdown built from a text box and a list (demoqa's react-select): typing and picking the entry
                        # is how it is chosen, as pb fill --pick does it
                        # a US state code is typed as the state's name: "MA" typed into a list of state names offers
                        # Maine first (advanceautoparts.com billing state, blind run 2026-11-17)
                        opt = a[1]
                        if len(opt.strip()) == 2 and state_alts(opt):
                            opt = state_alts(opt)[0]
                        with self.span("act"):
                            return [await self.fill_pick(loc, it, st, opt, opt, label)], "delta"
                    with self.span("act"):
                        try:
                            shown = await self.do_select(loc, it, a[1:] if len(a) > 2 else a[1], st)
                        except (Err, Gone):
                            raise
                        except Exception:
                            # saucedemo: the page replaces the select right after the choice went in. Look the field
                            # up again and judge by what it shows; the usual retry only when it does not show the choice.
                            shown = await self.replaced_select_shows(loc, it, a, purpose, near)
                            if shown is None:
                                raise
                            extra = " (the page re-rendered the list after the choice)"
                    await self.settle(max_s=2, react=0.3)
                    return [f'ok select {label} -> shows "{shown}"{extra}'], "delta"
                if cmd == "secret":
                    with self.span("act"):
                        line = await self.secret_into(loc, a[1], label, self.refs[it["ref"]][0] if it.get("ref") in self.refs else None)
                    await self.settle(max_s=1.5, quiet=0.2, react=0.2)
                    return [line], "delta"

            try:
                loc, it, known = await self.find_target(a[0], purpose, near)
            except NotFound as e:
                if cmd in ("fill", "select") and not near and not re.fullmatch(r"e\d+", a[0]) and not a[0].startswith("css="):
                    # no field is named so: a radio group under that legend, the one select that has the option, the
                    # field next to a text that is not tied to it (see field_by_text)
                    got = await self.field_by_text(cmd, a[0], " ".join(a[1:]))
                    if got is None and cmd == "fill":
                        # amtrak: once a station is chosen, "From" is a box that shows it ("From BOS Boston, MA South
                        # Station") and turns back into the combobox when clicked. pb clicks that box itself, once.
                        items0, _ = await self.collect()
                        q0 = fold(a[0]).strip()
                        boxes = [x for x in items0 if "ref" in x and x["k"] in ("click", "button") and not x.get("dis")
                                 and fold(x.get("t", "")).startswith(q0 + " ")]
                        if len(boxes) == 1:
                            bl, _ = self.loc(boxes[0]["ref"])
                            with contextlib.suppress(Exception):
                                await self.do_click(bl, boxes[0])
                            await self.settle(max_s=2, react=0.3)
                            self.scan = None
                            with contextlib.suppress(NotFound):
                                loc, it, known = await self.find_target(a[0], purpose, near)
                                self.notes.append(f'"{a[0]}" was a box showing a value ({self.line(boxes[0])}): pb clicked it, and the field it opened was filled')
                                got = "opened"
                    if got is None:
                        msg = str(e).replace(" for fill", f" for {cmd}")
                        raise NotFound(msg + ("; for radio buttons use pb check" if cmd == "select" else ""))
                    if got == "opened":
                        pass                       # the box opened its field: loc, it, known are that field's
                    elif got[0] == "done":
                        return got[1], "delta"
                    else:
                        _, loc, it, note = got
                        known = False
                        self.notes.append(note)
                # the-internet /tables: a sortable header is plain text with a script click handler. No control matches,
                # so a click goes to the element that shows exactly these words (never for fill, select or check).
                elif cmd != "click" or near or self.pick_nth or re.fullmatch(r"e\d+", a[0]) or a[0].startswith("css="):
                    raise
                elif not self.batch_acted and self.page.url.split("#")[0] != (self.batch_url or self.page.url).split("#")[0]:
                    # petsmart: the page went to another address by itself as the command began. The words were meant for
                    # the page before: a heading that happens to show them here is not what was asked for (execute says so).
                    raise
                else:
                    loc = await self.text_locator(a[0], exact_only=True)
                    if loc is None:
                        raise
                    it, known = {"k": "text", "t": a[0][:60]}, False
            t_first = time.time()
            for attempt in range(4):
                t_act = time.time()
                try:
                    lines, obs = await act(loc, it, known and attempt == 0)
                    if attempt:
                        lines[0] += " (the page had re-rendered that element; pb found it again)"
                    return lines, obs
                except Err:
                    raise
                except Gone:
                    shown = await self.select_took(cmd, loc, it, a, purpose, near)
                    if shown:
                        return shown, "delta"
                except Exception:
                    shown = await self.select_took(cmd, loc, it, a, purpose, near)
                    if shown:
                        return shown, "delta"
                    if cmd == "click" and self.navigating(t_act):
                        # the click went through and the page is leaving: wait for the new one instead of calling it lost
                        await self.settle()
                        return [f'ok click {it.get("ref", "")} {it.get("k", "")} "{it.get("t", "")}"'.strip()], "delta"
                    # Playwright gave up on the element. If it is gone, the page replaced it between the scan and the
                    # action (some shops re-render their product grid every second): find the same thing again.
                    gone = False
                    with contextlib.suppress(Exception):
                        gone = await asyncio.wait_for(loc.count(), 2) == 0
                    if not gone:
                        raise
                if time.time() - t_first > 12:
                    break                      # each try has its own time limits: four of them must not add up to a minute
                loc, it = await self.refind(a[0], it, purpose, near)
            raise Err("the page keeps replacing that element while pb acts on it. Wait for the page to finish (pb view), then try again")
        if cmd == "card":
            if a and a[0].startswith("-"):
                return [self.card_usage()], None
            self.dirty = True
            s, complete = await self.do_card(a[0] if a else None)       # it ends with the wait for the page and a read-back
            if not complete:
                # a card that is not all in must fail the command (exit 1) and stop a pb do batch
                raise Err(s)
            return [s], "delta"
        if cmd == "press":
            if not a:
                raise Err("usage: pb press KEY (Enter, Tab, Escape, ArrowDown, Control+A ...)")
            key = key_name(" ".join(a))
            self.dirty = True
            try:
                await page.keyboard.press(key)
            except Exception as e:
                if "Unknown key" not in str(e):
                    raise
                raise Err(f"unknown key {' '.join(a)!r}. Keys: Enter, Tab, Escape, Backspace, Delete, Space, ArrowUp/Down/Left/Right, "
                          "Home, End, PageUp, PageDown, F1-F12, a single character; modifiers ctrl/alt/shift/cmd joined with + (ctrl+a)")
            await self.settle(max_s=3, react=0.7 if key in ("Enter", "NumpadEnter") else 0.3)
            return [f"ok press {key}"], "delta"
        if cmd == "type":
            self.dirty = True
            await page.keyboard.type(" ".join(a), delay=15)
            await self.settle(max_s=2, quiet=0.25, react=0.7)
            return ["ok type"], "delta"
        if cmd == "expect":
            return await self.do_expect(a), None
        if cmd == "snap":
            if not self.capture_dir:
                raise Err("pb snap needs PB_CAPTURE=DIR in the environment of `pb start` (test runs)")
            return [f"SNAP page copy saved under {self.capture_dir}"], None
        if cmd == "review":
            items, _ = await self.collect()
            return ["REVIEW of the page:"] + ["  " + l for l in await self.asked_review(items)], None
        if cmd in ("text", "read"):
            start, section, nth = 0, None, 1
            for flag in ("--from", "--section", "--nth"):
                if flag in a:
                    i = a.index(flag)
                    if i + 1 >= len(a) or (flag in ("--from", "--nth") and not a[i + 1].isdigit()):
                        raise Err(f"usage: pb text --from N | pb text --section HEADING [--nth K] [--from N] | pb text --headings")
                    if flag == "--from":
                        start = int(a[i + 1])
                    elif flag == "--nth":
                        nth = max(1, int(a[i + 1]))
                    else:
                        section = a[i + 1]
                    a = a[:i] + a[i + 2:]
            if "--headings" in a:
                await self.read_wait()
                return await self.do_headings(), None
            ctx_n = 1
            if "--context" in a:
                i = a.index("--context")
                if i + 1 >= len(a) or not a[i + 1].isdigit():
                    raise Err("usage: pb text REGEX --context N (lines before and after each match, 0 to 5)")
                ctx_n = min(5, int(a[i + 1]))
                a = a[:i] + a[i + 2:]
            note = await self.read_wait()
            if "--of" in a:
                i = a.index("--of")
                if i + 1 >= len(a):
                    raise Err('usage: pb text --of TARGET (a ref, css=SELECTOR or the visible text of the element)')
                return await self.do_text_of(" ".join(a[i + 1:])) + ([note] if note else []), None
            if section is not None:
                return await self.do_text_section(section, start, nth) + ([note] if note else []), None
            rx = re.compile(" ".join(a), re.I) if a else grx
            if rx is not None and rx.search(""):
                # "Attic|" or a stray empty word: a pattern that matches nothing at all matches every line
                raise Err(f"the pattern /{rx.pattern}/ matches an empty text, so every line would match. Leave out the empty "
                          "alternative (a trailing |), or run pb text without a pattern for the whole page")
            if rx is not grx and grx is not None:
                import types
                both, one = rx, grx                 # a line must match the pattern and the --grep one
                rx = types.SimpleNamespace(search=lambda l: both.search(l) and one.search(l), pattern=both.pattern)
            out = await self.do_text(rx, start, ctx_n)
            # what was read comes first when it is the downloaded PDF, not the page the tab shows
            lead = [l for l in out if l.startswith("(the PDF the last command downloaded")]
            return lead + [l for l in out if l not in lead] + ([note] if note else []), None
        if cmd == "wait":
            if a[:1] == ["--ms"]:
                await asyncio.sleep(float(a[1]) / 1000)
                return [f"ok waited {a[1]} ms"], "delta"
            limit = 20.0
            if "--timeout" in a:
                i = a.index("--timeout")
                try:
                    limit = float(a[i + 1])
                except (IndexError, ValueError):
                    raise Err("usage: pb wait TEXT --timeout SECONDS | pb wait --gone TEXT --timeout SECONDS")
                a = a[:i] + a[i + 2:]
            inside = None
            if "--in" in a:
                # the text inside one element (uitestingplayground: `wait "75%" --in id=progressBar`, the scenario text
                # above the bar says "75%" too)
                i = a.index("--in")
                if i + 1 >= len(a):
                    raise Err("usage: pb wait TEXT --in TARGET (a ref, id=X, css=SELECTOR or a text)")
                inside, a = a[i + 1], a[:i] + a[i + 2:]
                box, _ = await self.find_any(inside, "click")
            gone = a[:1] == ["--gone"]
            q = " ".join(a[1:] if gone else a)
            t0, k = time.time(), 0
            ql = q.lower()
            was_there = None
            while time.time() - t0 < limit and inside is not None:
                present = False
                with contextlib.suppress(Exception):
                    present = ql in (await box.inner_text(timeout=500)).lower()
                if present != gone:
                    took = time.time() - t0
                    if not self.steps_left:
                        await self.settle(max_s=2)
                    return [f'ok "{q}" {"gone from" if gone else "visible in"} {inside} after {took:.1f}s'], "delta"
                await asyncio.sleep(0.05)
            if inside is not None:
                raise Err(f'timed out waiting for "{q}" to {"disappear from" if gone else "appear in"} {inside}')
            while time.time() - t0 < limit:
                # every 50 ms in the page's own text (uitestingplayground's progress bar: `wait "75%"; click Stop` landed
                # at 100% when a look took 300 ms and a settle followed); the frames every few rounds
                present = False
                base = getattr(self, "batch_text0", None)
                anew = bool(base and not gone and base[0] == page.url and ql in base[1])
                need = (base[1].count(ql) + 1) if anew else 1
                # also there when a line holding the text is one the batch did not begin with (a status line rewritten in
                # place: the count stays the same, the line is new); the lines it began with are matched as a multiset
                old = [ln.strip() for ln in base[1].split("\n") if ql in ln] if anew else []
                with contextlib.suppress(Exception):
                    present = await asyncio.wait_for(page.evaluate(
                        "([q, n, old]) => { if (!document.body) return false; const t = document.body.innerText.toLowerCase(); let c = 0, i = -1;"
                        " while ((i = t.indexOf(q, i + 1)) >= 0) if (++c >= n) return true; if (n <= 1) return false;"
                        " const left = {}; for (const l of old) left[l] = (left[l] || 0) + 1;"
                        " for (const raw of t.split('\\n')) { const l = raw.trim(); if (!l.includes(q)) continue;"
                        "   if (left[l]) left[l]--; else return true; } return false; }", [ql, need, old]), 1)
                if not present and k % 5 == 0 and need == 1:
                    for fr in page.frames:
                        with contextlib.suppress(Exception):
                            if await fr.get_by_text(q).first.is_visible(timeout=300):
                                present = True
                                break
                if k == 0:
                    was_there = present
                k += 1
                if present != gone:
                    # what was waited for is there: a "still loading" NOTE of an earlier step of this batch is stale now
                    # (it stayed in the answer under the result it had asked to wait for)
                    self.notes = [n for n in self.notes if not self.LOADING_NOTE.match(n)]
                    self.unfinished = False
                    took = time.time() - t0
                    if not self.steps_left:
                        await self.settle(max_s=2)     # (a next step in the batch goes at once: it waited for this moment)
                    if was_there and not gone and not anew:
                        self.notes.append(f'"{q}" was on the page already when the wait began, so it ended at once. To wait for '
                                          f'it in one element: pb wait "{q}" --in TARGET (a ref, id=X or css=)')
                    return [f'ok "{q}" {"gone" if gone else "visible"} after {took:.1f}s'], "delta"
                await asyncio.sleep(0.05)
            raise Err(f'timed out waiting for "{q}" to {"disappear" if gone else "appear"}')
        if cmd == "eval":
            raw = a[:1] == ["-r"]
            res = await page.evaluate(" ".join(a[1:] if raw else a), isolated_context=False)
            if raw and isinstance(res, str):
                return [res[:4000]], None               # pb eval -r: a string as it is, not JSON-encoded a second time
            return [json.dumps(res, ensure_ascii=False, default=str)[:4000]], None
        if cmd == "py":
            code = " ".join(a[1:]) if a[:1] == ["-c"] else open(local_path(a[0], self.cwd), encoding="utf-8").read()
            g = {"page": page, "ctx": self.ctx, "S": self, "asyncio": asyncio, "re": re, "json": json}
            exec("async def __pb_main():\n" + textwrap.indent(code, "    ") + "\n", g)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                res = await g["__pb_main"]()
                if asyncio.iscoroutine(res) or isinstance(res, asyncio.Future):
                    res = await res                 # `return page.title()`: the API is async and the await was left out
            out = buf.getvalue()
            if res is not None:
                out += ("\n" if out and not out.endswith("\n") else "") + repr(res)
            await self.settle(max_s=2)
            return [out[:5000] or "ok"], None
        if cmd == "shot":
            full = "--full" in a
            a = [x for x in a if x != "--full"]
            # an argument that names an image file is where it goes; anything else names the element to picture
            path = next((x for x in a if re.search(r"\.(png|jpe?g)$", x, re.I)), None)
            target = " ".join(x for x in a if x != path)
            path = local_path(path, self.cwd) if path else os.path.join(STATE_DIR, f"{self.session}-{int(time.time())}.png")
            loc = it = None
            # the finished page, as the reading commands wait for it (6 s at most): dailymed's label was pictured under
            # its loading spinner. A loading sign still up after the requests are answered is waited out too.
            note = await self.read_wait()
            with self.span("shot waits for loading signs"):
                t0 = time.time()
                while time.time() - t0 < 6:
                    busy = 0
                    with contextlib.suppress(Exception):
                        busy = await asyncio.wait_for(page.evaluate(self.LOADING_SIGNS_JS), 2)
                    if not busy:
                        break
                    # on a page that has been up for a while a sign that is still there stays (a decoration, a
                    # loader parked out of the way): only a page that is still coming is waited for
                    p = await self.probe()
                    if p is None or p["now"] - p["t0"] > 10000:
                        break
                    await asyncio.sleep(0.15)
            if target:
                loc, it = await self.find_any(target, "click")
            # A picture is read by the same model as the text, so card fields and card numbers are painted over.
            masks, n = await self.masks()
            if loc is not None:
                await loc.screenshot(path=path, mask=masks, mask_color="#333333", timeout=10000)
            else:
                await page.screenshot(path=path, full_page=full, mask=masks, mask_color="#333333")
            return [path + (f"  ({n} card field(s) or number(s) painted over)" if n else "")] + ([note] if note else []), None
        if cmd == "window":
            if a:
                if not re.fullmatch(r"\d{3,5}x\d{3,5}", a[0]):
                    raise Err("usage: pb window [WIDTHxHEIGHT]   (for example pb window 1366x900; no argument prints the size)")
                await self.set_window(*a[0].split("x"))
                await self.settle(max_s=1.5, quiet=0.2, react=0.2)      # the layout follows the new width
            ow, oh, iw, ih = await self.window_size()
            return [f"window {ow}x{oh} (the page gets {iw}x{ih})"], None
        if cmd == "tabs":
            return [f'{i}{"*" if p is page else " "} {p.url[:100]}' for i, p in enumerate(self.ctx.pages)], None
        if cmd == "tab":
            if a[:1] == ["new"]:
                self.prev_page = page
                self.page = await self.ctx.new_page()
                self.tab_at, self.base = time.time(), None
                if len(a) > 1:
                    url = a[1] if re.match(r"^[a-z]+:", a[1]) else "https://" + a[1]
                    try:
                        await self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    except Exception as e:
                        if "Download is starting" not in str(e):
                            raise
                        # an address that is a file (dailymed's label PDF): downloaded, as pb open does it; the blank
                        # tab it leaves is closed and the tab before comes back, where pb text reads the file next
                        with contextlib.suppress(Exception):
                            await asyncio.sleep(0.2)
                            live = [t for t in self.dl_pending if not t.done()]
                            if live:
                                await asyncio.wait(live, timeout=60)
                        blank, self.page = self.page, self.prev_page
                        with contextlib.suppress(Exception):
                            await blank.close()
                        with contextlib.suppress(Exception):
                            await self.page.bring_to_front()
                        if self.pdf_dl:
                            self.pdf_dl = (self.pdf_dl[0], self.page.url)
                        self.tab_switched, self.base = False, None
                        return [f"ok tab new {url[:120]}: that address is a file, so it was downloaded, not shown (the blank tab was "
                                f"closed; back on tab {self.ctx.pages.index(self.page)})"], None
                    await self.settle(max_s=5)
                self.tab_switched = False
                return [f"ok tab new (tab {len(self.ctx.pages) - 1})"], "view"
            if a[:1] == ["close"]:
                pages = self.ctx.pages
                if len(a) > 1 and not a[1].isdigit():
                    raise Err("usage: pb tab close [N] (N from pb tabs; default the current tab)")
                idx = int(a[1]) if len(a) > 1 else pages.index(page) if page in pages else len(pages) - 1
                if not 0 <= idx < len(pages):
                    raise Err(f"no tab {idx}: pb tabs lists {len(pages)}")
                victim = pages[idx]
                if len(pages) == 1:
                    await self.ctx.new_page()          # the browser keeps one tab open
                await victim.close()
                if victim is self.page or self.page.is_closed():
                    back = self.prev_page if self.prev_page is not None and not self.prev_page.is_closed() else self.ctx.pages[-1]
                    self.page = back
                    with contextlib.suppress(Exception):
                        await back.bring_to_front()
                self.tab_switched, self.base = False, None
                return [f"ok closed tab {idx}"], "view"
            if not a or not a[0].isdigit():
                raise Err("usage: pb tab N | pb tab new [URL] | pb tab close [N]")
            if int(a[0]) >= len(self.ctx.pages):
                raise Err(f"no tab {a[0]}: tabs are numbered from 0, and there are {len(self.ctx.pages)}: "
                          + "; ".join(f"{i} {p.url[:80]}" for i, p in enumerate(self.ctx.pages)))
            self.page = self.ctx.pages[int(a[0])]
            await self.page.bring_to_front()
            return [f"ok tab {a[0]}"], "view"
        if cmd == "forward":
            self.base = None
            was = page.url
            try:
                await page.go_forward(wait_until="commit", timeout=5000)
            except Exception as e:
                if "Timeout" not in str(e):
                    raise
                if self.page.url == was:           # a single-page app: its views are history entries (see back)
                    with contextlib.suppress(Exception):
                        await asyncio.wait_for(page.evaluate("() => history.forward()"), 3)
            await self.settle()
            return ["ok forward"], "view"
        self.any_near = None
        if cmd in ("scroll", "hover", "upload"):
            self.any_near, a = take_near(a)        # read by find_any
        if cmd == "scroll":
            return await self.do_scroll(a), "delta"
        if cmd == "hover":
            if not a:
                raise Err("usage: pb hover TARGET")
            return await self.do_hover(" ".join(a)), "delta"
        if cmd == "drag":
            if len(a) != 2:
                raise Err('usage: pb drag SOURCE TARGET (quote texts with spaces: pb drag "Card A" "Done")')
            return await self.do_drag(a[0], a[1]), "delta"
        if cmd == "upload":
            if len(a) < 2:
                raise Err("usage: pb upload TARGET FILE [FILE...] (TARGET: the file field, or the button or label that opens it)")
            return await self.do_upload(a[0], a[1:]), "delta"
        if cmd == "download":
            if not a or len(a) > 2:
                raise Err("usage: pb download TARGET|URL [PATH]")
            from urllib.parse import urljoin
            if re.match(r"^(https?:|blob:|data:|file:|/|\./|\.\./)", a[0], re.I):
                url = urljoin(page.url, a[0])
            else:
                loc, it = await self.find_any(a[0], "click")
                url = await loc.evaluate(HREF_OF_JS, timeout=3000)
                if not url:
                    raise Err(f'"{a[0]}" has no address behind it (no link or image). Click it instead: a download it starts is saved')
            self.last_fetch = None
            line = await self.fetch_to_file(url, a[1] if len(a) > 1 else None)
            if self.last_fetch and self.last_fetch[1]:
                # a PDF pb saved: the next pb text reads it, once, as after a link that downloads one (dailymed: `pb
                # download PDF_URL PATH`, then pb text read the label page)
                self.pdf_dl = (self.last_fetch[0], page.url)
                line += " (a PDF: the next pb text reads it, as the tab stayed on this page)"
            return [line], None
        if cmd == "outline":
            note = await self.read_wait()
            return await self.do_headings() + ([note] if note else []), None
        if cmd in ("links", "table", "items"):
            note = await self.read_wait()
            out = await (self.do_links(a) if cmd == "links" else self.do_table(a) if cmd == "table" else self.do_items(a))
            return out + ([note] if note else []), None
        if cmd == "dialog":
            if not a or a[0] not in ("accept", "dismiss") or (a[0] == "dismiss" and len(a) > 1):
                raise Err('usage: pb dialog accept [TEXT] | pb dialog dismiss (sets what happens to the next JS dialog only)')
            self.dialog_next = ("dismiss", None) if a[0] == "dismiss" else ("accept", " ".join(a[1:]) if len(a) > 1 else None)
            self.dialog_until = self.req_no + (0 if self.steps_left else 1)
            what = "dismissed" if a[0] == "dismiss" else (f'accepted, a prompt answered "{" ".join(a[1:])}"' if len(a) > 1 else "accepted")
            return [f"ok the next JS dialog will be {what}" + (" (during the rest of this batch)" if self.steps_left else " (during the next command)")], None
        if cmd == "back":
            self.base = None
            was = page.url
            try:
                # "commit": the wait for the page before is settle()'s job, as after any other step
                await page.go_back(wait_until="commit", timeout=5000)
            except Exception as e:
                if "Timeout" not in str(e):
                    raise
                # No page load came of it within 5 s. In a single-page app there is none to come (lego: 30 s, then an
                # error): its views are history entries of one document. Ask the page itself, unless it has moved.
                if self.page.url == was:
                    with contextlib.suppress(Exception):
                        await asyncio.wait_for(page.evaluate("() => history.back()"), 3)
            await self.settle()
            return ["ok back"], "view"
        if cmd == "recover":
            url = await self.recover()
            return [f"ok reopened {url} in a new tab"], "view"
        if cmd == "reload":
            self.base = None
            await page.reload(wait_until="domcontentloaded", timeout=30000)
            await self.settle()
            return ["ok reload"], "view"
        if cmd == "status":
            return [f"session {self.session} | {len(self.ctx.pages)} tab(s) | {page.url} | page {'responding' if await self.ping() else 'NOT RESPONDING (pb recover)'}"], None
        if cmd == "stop":
            # the browser is gone when the answer comes (`pb status` right after said it was still running): its windows
            # are closed and the session's state file removed first, 10 s at most
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self.ctx.close(), 10)
            with contextlib.suppress(Exception):
                os.remove(state_path(self.session))
            self.closed.set()
            return ["ok stopping (the browser is closed)"], None
        raise Err(f"unknown command '{cmd}'. Commands: " + ", ".join(self.COMMANDS) + ". Run pb help")

    ACTIONS ={"click", "check", "uncheck", "fill", "select", "secret", "card", "press", "type", "py", "scroll", "hover", "drag", "upload"}
    LOOKS = {"scroll", "hover"}       # actions that only look around: no unasked order review after them
    READERS = {"text", "read", "find", "links", "table", "items", "outline"}   # commands that only read the page

    # The options each command takes (run() refuses others). Commands not listed are not checked.
    FLAGS = {"view": {"--all", "--grep", "--ignore-case"}, "find": {"--grep", "--ignore-case"},
             "text": {"--from", "--section", "--nth", "--of", "--context", "--grep", "--headings", "--ignore-case"},
             "read": {"--from", "--section", "--nth", "--of", "--context", "--grep", "--headings", "--ignore-case"},
             "items": {"--n", "--from", "--in", "--ignore-case"}, "links": {"--ignore-case"}, "table": {"--rows", "--ignore-case"},
             "outline": set(), "click": {"--near", "--nth", "--right", "--double"}, "fill": {"--pick", "--near", "--nth"},
             "select": {"--near", "--nth"}, "check": {"--near", "--nth"}, "uncheck": {"--near", "--nth"},
             "hover": {"--near"}, "scroll": {"--near"}, "wait": {"--gone", "--timeout", "--ms", "--in"}, "shot": {"--full"}}

    # Every command run() knows. pb do checks its steps against this list before running any of them.
    COMMANDS = ("open", "goto", "view", "find", "click", "check", "uncheck", "fill", "select", "secret", "card", "press", "type",
                "expect", "snap", "review", "text", "read", "wait", "eval", "py", "shot", "tabs", "tab", "window", "back", "recover",
                "reload", "status", "stop", "scroll", "hover", "drag", "upload", "download", "links", "table", "items", "dialog", "forward", "outline")

    async def execute(self, args):
        if args and args[0] == "do":
            rest = args[1:]
            first = lambda s: (s[1] if len(s) > 1 and s[0] == "try" else s[0]) if s else ""
            try:
                per_arg = [split_cmds(x) for x in rest] if len(rest) > 1 else None
            except ValueError:                 # an unbalanced quote inside one argument: read them as one line
                per_arg = None
            if per_arg and all(sts and first(sts[0]) in self.COMMANDS for sts in per_arg):
                # pb do 'click X' 'fill Y z': each quoted argument is a step (or several), not words of one step
                steps = [st for sts in per_arg for st in sts]
            else:
                steps = split_cmds(" ".join(rest))
            if not steps:
                raise Err("usage: pb do 'cmd; cmd; ...'")
            bad = next((st for st in steps if first(st) not in self.COMMANDS), None)
            if bad:
                raise Err(f"unknown command '{first(bad)}' in step `{' '.join(bad)[:80]}`, so nothing was run. Commands: "
                          + ", ".join(self.COMMANDS) + ". Separate steps with ';'")
        else:
            steps = [args]
        self.in_batch = len(steps) > 1
        self.view_due = False
        # the page's text as the batch begins, when a later step waits for a text: the wait is for that text to show up
        # anew, not for words the page had all along (uitestingplayground's progress bar: its instructions say "75%")
        self.batch_text0 = None
        if len(steps) > 1 and any(x and (x[1] if x[0] == "try" and len(x) > 1 else x[0]) == "wait" for x in steps[1:]):
            with contextlib.suppress(Exception):
                self.batch_text0 = (self.page.url, (await asyncio.wait_for(self.page.evaluate(
                    "() => document.body ? document.body.innerText.toLowerCase() : ''"), 2)))
        # a PDF an earlier command downloaded is what pb text reads only until the next action or page change
        if any(x and (x[1] if x[0] == "try" and len(x) > 1 else x[0]) in (self.ACTIONS | {"open", "goto", "back", "forward", "reload", "tab", "recover"})
               for x in steps):
            self.pdf_dl = None
        self.quiet_same = False
        self.sugg_hint = None
        t_batch = time.time()
        url_start = self.page.url
        self.batch_url, self.batch_acted = url_start, False
        self.status_due = False
        if self.unfinished:
            # The last answer was cut off while the page was loading. A command that looks at the page gets the
            # finished page; a command that acts goes ahead as soon as its target is there (find_target waits for it).
            if steps[0] and steps[0][0] in ("view", "find", "text", "read", "expect", "review", "shot", "eval", "links", "table", "items", "outline"):
                await self.finish_loading()
            self.unfinished = False
        passive = {"view", "find", "text", "read", "eval", "shot", "tabs", "window", "status", "stop", "open", "goto", "tab", "back", "recover", "reload",
                   "links", "table", "items", "download", "dialog", "forward", "outline"}
        if all(st and st[0] in passive for st in steps):
            before, meta_b = [], {"url": self.page.url, "title": "", "text": None}
        else:
            before, meta_b = await self.collect()
        status, last_obs, texts = [], None, []
        failed, acted_yet = None, False
        si, human_stop, hf_batch = 0, False, self.human_flag
        for si, st in enumerate(steps):
            t_step = time.time()
            # `try click "No thanks"`: an optional step. A popup that may or may not be there must not stop the batch.
            optional = len(st) > 1 and st[0] == "try"
            if optional:
                st = st[1:]
            self.patience = 1.5 if optional else 8
            self.steps_left = len(steps) - si - 1
            if (self.batch_text0 is not None and self.page.url != self.batch_text0[0] and st and st[0] != "wait"
                    and any(x and (x[1] if x[0] == "try" and len(x) > 1 else x[0]) == "wait" for x in steps[si + 1:])):
                # an earlier step led to another page (`open .../progressbar; click Start; wait "75%"`): the text the wait
                # must see anew is counted on that page, before the step that makes it change
                with contextlib.suppress(Exception):
                    self.batch_text0 = (self.page.url, (await asyncio.wait_for(self.page.evaluate(
                        "() => document.body ? document.body.innerText.toLowerCase() : ''"), 2)))
            if si and self.human_flag != hf_batch and self.human_flag == self.page.url.split("?")[0]:
                # an earlier step led to a human check (pubmed's reCAPTCHA after a search): the steps after it would only
                # fail with "nothing matches" on the check page
                failed = (f"ERR at step `{' '.join(st)[:60]}` (not run): HUMAN CHECK after step `{' '.join(steps[si - 1])[:80]}`: "
                          f"{self.human_text}. Stopped there; stop and report it")
                human_stop = True
                break
            try:
                if st and st[0] in self.ACTIONS:
                    await self.mark()
                self.sugg_hint = None          # only the last step's suggestions are worth a line
                self.any_near = None
                # the batch's answer will be a whole view (an earlier step opened a page), not a page change: a hover
                # says itself what it opened (the-internet /jqueryui/menu: `open; hover Enabled; hover Downloads`)
                self.view_due = last_obs in ("view", "viewall") or isinstance(last_obs, tuple)
                lines, obs = await self.run(st)
                acted_yet =acted_yet or st[0] in self.ACTIONS or st[0] in ("open", "goto", "back", "forward", "reload", "tab", "recover")
                self.batch_acted = acted_yet
            except Err as e:
                if optional:
                    status.append(f"skipped optional step `{' '.join(st)[:60]}`: {str(e)[:110]}")
                    continue
                failed = f"ERR at step `{' '.join(st)}`: {e}"
                if si and self.human_flag != hf_batch and self.human_flag == self.page.url.split("?")[0]:
                    # what the step looked for is not there because the page is a human check now (pubmed: "nothing
                    # matches 'Search:'" on its reCAPTCHA page, with no clear word about the check)
                    failed = (f"ERR at step `{' '.join(st)[:60]}`: HUMAN CHECK after step `{' '.join(steps[si - 1])[:80]}`: {self.human_text}. "
                              "This step found nothing on that page. Stop and report it")
                elif isinstance(e, NotFound) and not acted_yet and self.page.url.split("#")[0] != url_start.split("#")[0]:
                    # petsmart: the search page moved on to a product page by itself (its router) as the batch began;
                    # the product title was no longer a link there, and the answer read as if pb's click had moved it
                    failed += (f". Meanwhile the page went to another address by itself (from {url_start[:120]}); nothing was "
                               f"{st[0] + 'ed' if st[0] in ('click', 'check', 'uncheck') else 'done'}. Look at the new page first: pb view")
                break
            except Exception as e:
                failed = f"ERR at step `{' '.join(st)}`: {str(e).splitlines()[0][:220]}"
                break
            finally:
                self.spans.append(("step:" + " ".join(st)[:50], round(time.time() - t_step, 3)))
                # the page answered a moment ago (the step's own wait or scan ended with a look at it): no need to ask again
                answered = self.end is not None and self.end[0] is not None and time.time() - self.end[1] < 0.3
                if st and st[0] not in ("stop", "status", "recover") and not answered and not await self.ping():
                    return (f"ERR the page froze during `{' '.join(st)[:80]}` (a script on it is spinning). Run `pb recover` to reopen it "
                            "in a new tab, then do that step another way (keyboard instead of click). Typed form fields may be lost.\n")
            if obs in ("delta", "view", "viewall") or isinstance(obs, tuple):
                status += lines
                # a view asked for after open (or tab, back) is the one shown, with its --grep (it was dropped)
                looks = lambda o: o in ("view", "viewall") or isinstance(o, tuple)
                last_obs = obs if not looks(last_obs) or looks(obs) else last_obs
            elif status:
                status += lines                    # after the lines of the steps before it, in the order they ran
            else:
                texts += lines
        # The unasked review follows an action only. Not when the batch already read the page back (expect and review
        # print their own), and not when it ends by reading the page (text, find, view answer only what was asked).
        names = [(st[1:] if len(st) > 1 and st[0] == "try" else st)[:1] for st in steps]
        names = [n[0] for n in names if n]
        unasked = (any(n in self.ACTIONS and n not in self.LOOKS for n in names) and not any(n in ("expect", "review") for n in names)
                   and bool(names) and names[-1] not in ("text", "read", "find", "view", "eval", "shot", "links", "table", "items", "outline"))
        acted = any(n in self.ACTIONS for n in names)
        final = None               # the page as the answer will describe it, once it has been looked at
        if acted and not failed and last_obs == "delta" and not self.noisy:
            final = await self.collect()
            # (after a scroll the answer says what is in view, and the scroll waited for what it loads)
            if self.unchanged(before, meta_b, *final) and names[-1] != "scroll":
                with self.span("late look"):
                    final = await self.late_look() or final
        with contextlib.suppress(Exception):
            self.note_plain_http()             # a click or a redirect may have led to a plain-HTTP site
        # downloads the steps started: saved by now, and named in the answer
        dl = await self.take_downloads() if self.dl_pending or self.dl_lines else []
        if dl:
            if last_obs is not None:
                status += dl
                self.quiet_same = True         # the download is what happened
            else:
                texts += dl
        if acted:
            errs = list(dict.fromkeys(e for t, e in self.http_errs if t >= t_batch))
            if not failed and self.page.url.split("#")[0] != url_start.split("#")[0]:
                # the action led to another page: when the server answered that page itself with an error, say that (as
                # pb open does), not that "a request" failed
                st = await self.page_status()
                if st >= 400:
                    path = "/" + self.page.url.split("?")[0].split("://", 1)[-1].partition("/")[2]
                    errs = [e for e in errs if f" {path[:80]} -> HTTP {st}" not in e]
                    self.notes.append(f"the server answered HTTP {st} for this page: what shows is its error page")
            if errs and not failed:
                # A failed background request is news when it may explain why nothing happened: the page did not
                # change, or what failed was a submission (POST). A side request that failed while the page went on
                # to show the result is not (cochranelibrary.com: HTTP 414 on GET /en/search under a results page that
                # loaded fine; europepmc.org: HTTP 500 on GET /api/get/spellCheck after a filter that applied).
                moved = self.page.url.split("#")[0] != url_start.split("#")[0]
                changed = moved or (final is not None and not self.unchanged(before, meta_b, *final))
                if changed:
                    errs = [e for e in errs if not e.startswith("GET ")]
            if errs:
                # amtrak: "ok click FIND TRAINS" above a NOTE about a 403: the first line must not read as plain ok
                m = re.match(r"(\S+) (\S+) -> HTTP (\d+)", errs[-1])
                i = next((k for k in range(len(status) - 1, -1, -1) if status[k].startswith("ok ")), None)
                if m and i is not None:
                    status[i] += f", but the site answered HTTP {m.group(3)} to {m.group(1)} {m.group(2)}"
                self.notes.append(f"the site answered {len(errs)} of its own background request(s) with an error during this command: "
                                  + "; ".join(errs[:4]) + (" ..." if len(errs) > 4 else "") + ". The action may not have taken effect")
        out = ""
        if failed and len(steps) > 1:
            left = len(steps) - si - (0 if human_stop else 1)
            status.append(failed + f" ({si} earlier step(s) done" + (f", {left} not run" if left else "") + ")")
        elif failed:
            return failed + "\n"
        if texts:
            out += "\n".join(texts) + "\n"
        if last_obs == "viewall":
            out += "\n".join(status) + ("\n" if status else "") + await self.view_text(show_all=True)
        elif isinstance(last_obs, tuple):
            # the steps' own lines first, as for the other views ("ok click ..." was left out of a batch ending in view --grep)
            out += "\n".join(status) + ("\n" if status else "") + await self.view_text(grep=last_obs[1], show_all=len(last_obs) > 2 and last_obs[2])
        elif last_obs == "view":
            items, meta = await self.collect()
            if acted_yet and not failed:       # a page was opened (open, back, tab...): an empty one is waited for
                items, meta = await self.wait_for_content(items, meta)
            if self.human_flag and self.human_flag == self.page.url.split("?")[0]:
                # (amazon: "ok open" stood first on its human-check page)
                i = next((k for k, l in enumerate(status) if l.startswith(("ok open ", "ok back", "ok forward"))), None)
                if i is not None:
                    status[i] = "HUMAN CHECK: " + status[i] + " led to a human check or block page (NOTE below)"
            if self.status_due and not failed:
                st = await self.page_status()
                if st >= 400:
                    self.notes.append(f"the server answered HTTP {st} for this page: what shows is its error page")
            # (pb back and pb forward: the page's first lines and a count, as after a click that leads to another page;
            # pb open and pb view print it all)
            short = self.NAV_MAX if names and names[-1] in ("back", "forward", "tab") else None
            out += self.clip(status + self.header(meta) + self.render(items, limit=short) + self.text_if_bare(items, meta)) + (await self.maybe_review(items) if unasked else "")
        elif last_obs == "delta" and not failed and names and names[-1] in self.READERS:
            # a batch that ends by reading: its answer is what was read, not the page change of the action before it
            # (dailymed: `open` of a PDF address, then text, printed 146 "page changed" lines above the PDF's lines)
            if self.page.url.split("#")[0] != url_start.split("#")[0]:
                out += f"URL -> {self.page.url}\n"
            out += "".join(f"NOTE {n}\n" for n in self.notes)
            self.notes = []
            out += "\n".join(status) + "\n"
        elif last_obs == "delta" or (failed and status):
            after, meta_a = final or await self.collect()
            if not failed and self.page.url.split("#")[0] != url_start.split("#")[0]:
                after, meta_a = await self.wait_for_content(after, meta_a)
            out += self.delta(before, meta_b, after, meta_a, status)
            hint, self.sugg_hint = self.sugg_hint, None
            if hint and not failed and not re.search(r"^\+ e\d+ .*" + re.escape(hint[0]), out, re.M):
                out += hint[1] + "\n"          # unless the answer lists the suggestions with refs already
            out += await self.maybe_review(after) if unasked else ""
        elif status:
            out += "\n".join(status) + "\n"
        if names and all(n in self.READERS for n in names) and self.human_flag and self.human_flag == self.page.url.split("?")[0]:
            # jamanetwork.com (Cloudflare, HTTP 403): "no text matches" read as "the article lacks the words"
            out = f"NOTE this page is a human check or block page, not the content asked for ({self.human_text}). What follows is read from it:\n" + out
        return out

    async def handle(self, reader, writer):
        try:
            req = json.loads((await reader.readline()).decode("utf-8"))
            self.last_cmd, self.cwd = time.time(), req.get("cwd")
            async with self.lock:
                self.spans, t_req = [], time.time()
                self.req_no += 1
                if self.dialog_next and self.req_no > self.dialog_until:
                    self.dialog_next = None        # a pb dialog choice no dialog came for: the default again
                self.steps_left = 0
                try:
                    out = await asyncio.wait_for(self.execute(req["args"]), 280)
                except Err as e:
                    out = f"ERR {e}\n"
                except Exception as e:
                    out = "ERR " + str(e).splitlines()[0][:300] + "\n"
                finally:
                    self.steps_left = 0
                    if self.dialog_next and self.req_no >= self.dialog_until:
                        self.dialog_next = None
                if self.capture_dir and (out.startswith("ERR") or "\nERR at step `" in out or out.startswith("SNAP")):
                    with self.span("capture"):            # test runs only: the page copy of a failed command
                        await self.capture(req["args"], out)
            out = self.redact(out)
            with contextlib.suppress(Exception):
                with open(os.path.join(STATE_DIR, self.session + ".timing.jsonl"), "a", encoding="utf-8") as f:
                    f.write(self.redact(json.dumps({"t": round(t_req, 2), "total": round(time.time() - t_req, 3),
                                                    "cmd": req["args"][0] if req["args"] else "", "spans": self.spans, "out": len(out)},
                                                   ensure_ascii=False)) + "\n")
            writer.write(out.encode("utf-8"))
            await writer.drain()
        except Exception:
            pass
        finally:
            with contextlib.suppress(Exception):
                writer.close()


MULT_SIGN, ELLIPSIS = chr(0xD7), chr(0x2026)
# "(opens in a new window or tab)", "- opens in new tab", "link opens in a new window": screen-reader boilerplate
NEW_WINDOW_RX = re.compile(r"[\s,.;:(-]*\b(this )?(link )?opens? (in )?(a )?new (browser )?(window|tab)( or tab)?\)?\.?", re.I)


def fold(s):
    """Text as targets are compared: lower case, and for text beyond ASCII also Unicode NFKC with case folding and the
    multiplication sign read as x (ikea: "RÖDALM Frame, black, 12x16" against a page that writes 12×16 with a
    no-break space and a decomposed Ö). Plain ASCII text, nearly all of it, skips the normalising."""
    s = (s or "").lower()
    if s.isascii():
        return s
    import unicodedata
    # the ellipsis a view puts at the end of a cut text must stay one character (NFKC makes it three dots; see score)
    return unicodedata.normalize("NFKC", s.replace(ELLIPSIS, "\0")).casefold().replace(MULT_SIGN, "x").replace("\0", ELLIPSIS)


US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut",
    "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "PR": "Puerto Rico", "GU": "Guam", "VI": "Virgin Islands",
}
US_STATE_CODES = {v.lower(): k for k, v in US_STATES.items()}


def state_alts(option):
    """The other form of a US state: "MA" -> ["Massachusetts"], "Massachusetts" -> ["MA"], anything else -> []."""
    o = option.strip()
    if o.upper() in US_STATES and len(o) == 2:
        return [US_STATES[o.upper()]]
    code = US_STATE_CODES.get(o.lower())
    return [code] if code else []


KEY_ALIASES = {
    "ctrl": "Control", "control": "Control", "ctl": "Control", "cmd": "Meta", "command": "Meta", "meta": "Meta", "win": "Meta",
    "super": "Meta", "alt": "Alt", "option": "Alt", "opt": "Alt", "shift": "Shift", "esc": "Escape", "escape": "Escape",
    "return": "Enter", "enter": "Enter", "del": "Delete", "delete": "Delete", "backspace": "Backspace", "bksp": "Backspace",
    "space": "Space", "spacebar": "Space", "tab": "Tab", "up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft",
    "right": "ArrowRight", "arrowup": "ArrowUp", "arrowdown": "ArrowDown", "arrowleft": "ArrowLeft", "arrowright": "ArrowRight",
    "pageup": "PageUp", "pgup": "PageUp", "pagedown": "PageDown", "pgdn": "PageDown", "home": "Home", "end": "End",
    "insert": "Insert", "ins": "Insert", "numpadenter": "NumpadEnter", "plus": "+", "minus": "-",
}


def key_name(s):
    """A key as callers spell it (ctrl+a, CMD-Shift-z, esc, arrow down) in Playwright's names (Control+a, Meta+Shift+z,
    Escape, ArrowDown). A lone "-" or "+" is the key itself."""
    s = s.strip()
    if len(s) == 1:
        return s
    parts = [p for p in re.split(r"\s*[+]\s*|(?<=\w)-(?=\w)", s) if p] if re.search(r"\w[+-]\w|\w\s*\+\s*\w", s) else [s]

    def one(p):
        k = KEY_ALIASES.get(re.sub(r"[\s_]", "", p).lower())
        if k:
            return k
        if re.fullmatch(r"[fF]\d{1,2}", p):
            return p.upper()
        return p if len(p) == 1 or not p.islower() else p[0].upper() + p[1:]

    return "+".join(one(p) for p in parts)


def take_near(a):
    """-> (near text or None, the other words). --near takes the words after it up to the next --option or the end:
    `click 15 --near January 2027` (in pb do the words arrive one by one) became the target "15 2027"."""
    if "--near" not in a:
        return None, a
    i = a.index("--near")
    j = i + 1
    while j < len(a) and not a[j].startswith("--"):
        j += 1
    return (" ".join(a[i + 1:j]) or None), a[:i] + a[j:]


def click_kind(a):
    """-> ("right" | "double" | None, the other words) for pb click TARGET --right | --double."""
    kind = "right" if "--right" in a else "double" if "--double" in a else None
    return kind, [x for x in a if x not in ("--right", "--double")]


RAW_STEP = re.compile(r"^\s*((?:try\s+)?(?:eval|py\s+-c))\s+(.*)$", re.S)


def split_cmds(s):
    """Steps of a pb do line, split at ';' and newlines outside quotes, each one split into words as a shell does. An
    eval or py -c step keeps the rest of its step as written (quotes too), and a ';' inside its brackets does not end
    it: `eval document.querySelectorAll(".quote").length` lost its quotes to the word splitting."""
    parts, cur, q, depth = [], [], None, 0
    for ch in s:
        if q:
            cur.append(ch)
            if ch == q:
                q = None
        elif ch in "\"'" or (ch == "`" and RAW_STEP.match("".join(cur))):
            q = ch
            cur.append(ch)
        elif ch in ";\n" and not (depth > 0 and RAW_STEP.match("".join(cur))):
            parts.append("".join(cur))
            cur, depth = [], 0
        else:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth = max(0, depth - 1)
            cur.append(ch)
    parts.append("".join(cur))
    out = []
    for p in parts:
        if not p.strip():
            continue
        m = RAW_STEP.match(p)
        if not m:
            out.append(shlex.split(p))
            continue
        code = m.group(2).strip()
        if len(code) >= 2 and code[0] == code[-1] and code[0] in "\"'":
            with contextlib.suppress(ValueError):
                one = shlex.split(code)
                if len(one) == 1:
                    code = one[0]          # the whole code quoted as one word: eval "document.title"
        out.append(m.group(1).split() + [code])
    return out


WINDOW_DEFAULT = "1366x900"
# test runs: names of this machine that the daemon takes for public sites (comma separated), to test the plain-HTTP guard
PUBLIC_FOR_TESTS = {h.strip().lower() for h in os.environ.get("PB_TREAT_AS_PUBLIC", "").split(",") if h.strip()}


def plain_http(url, treat_public=()):
    """True for a plain-HTTP page of another machine. This machine itself (localhost, *.localhost, 127.x, ::1) is exempt:
    nothing leaves it."""
    m = re.match(r"^http://(?:[^/?#@]*@)?(\[[^\]]+\]|[^/:?#]+)", url or "", re.I)
    if not m:
        return False
    host = m.group(1).lower().strip("[]")
    if host in treat_public:
        return True
    return not (host == "localhost" or host.endswith(".localhost") or re.fullmatch(r"127(\.\d{1,3}){3}", host) or host == "::1")


def explain_open_error(msg, url):
    """What a failed navigation means and what to try, for the browser errors an agent cannot act on as they are.
    None when the error has no better wording."""
    m = re.search(r"net::(ERR_[A-Z_]+)", msg or "")
    code = m.group(1) if m else ""
    host = host_of(url) or url
    as_http = re.sub(r"^https:", "http:", url, flags=re.I)
    as_https = re.sub(r"^http:", "https:", url, flags=re.I)
    if code == "ERR_BLOCKED_BY_CLIENT" and url.lower().startswith("http://"):
        return (f"Chrome refused {url[:120]} because it is plain HTTP (its 'Always use secure connections' setting; {code}). pb turns that "
                f"setting off when it starts a profile: run pb stop, then pb start again with the same profile. Or try {as_https[:120]}")
    if code.startswith("ERR_CERT_") or code in ("ERR_SSL_PROTOCOL_ERROR", "ERR_SSL_VERSION_OR_CIPHER_MISMATCH"):
        return (f"{host} has no valid HTTPS at this address ({code}: a bad or missing certificate), and Chrome's warning page cannot be "
                f"clicked through from here. If the site is plain HTTP only, open {as_http[:120]}")
    if code == "ERR_NAME_NOT_RESOLVED":
        return f"the site name {host} does not exist ({code}): check the spelling of the address"
    if code in ("ERR_CONNECTION_REFUSED", "ERR_CONNECTION_RESET", "ERR_CONNECTION_CLOSED", "ERR_EMPTY_RESPONSE", "ERR_ADDRESS_UNREACHABLE"):
        return f"{host} did not answer ({code}): nothing serves that address right now, or it refuses this connection"
    if code in ("ERR_CONNECTION_TIMED_OUT", "ERR_TIMED_OUT") or re.search(r"Timeout \d+ms exceeded", msg or ""):
        return f"{host} did not answer in time ({code or 'no response in 45 s'}). pb status shows where the browser is; the page may still be usable: pb view"
    if code in ("ERR_INTERNET_DISCONNECTED", "ERR_NETWORK_CHANGED", "ERR_PROXY_CONNECTION_FAILED"):
        return f"this machine has no working network connection right now ({code})"
    if code in ("ERR_HTTP2_PROTOCOL_ERROR", "ERR_QUIC_PROTOCOL_ERROR", "ERR_ACCESS_DENIED"):
        return (f"{host} cut the connection ({code}). Sites that block automated browsers do this: treat it as a block, do not retry in a "
                "loop; a profile the site already trusts may get through")
    return None


def ensure_prefs(profile_dir):
    """Chrome's native bubbles (breached-password warning, save password/card/address) are modal: while one is open
    every click on the page is swallowed. Pages cannot see these prefs, so turning the prompts off costs no stealth."""
    p = os.path.join(profile_dir, "Default", "Preferences")
    fresh = not os.path.exists(p)
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    d.setdefault("profile", {})["password_manager_leak_detection"] = False
    # Chrome 154 and later refuse every plain-HTTP page of a public site until someone clicks through a warning, and no
    # script can click it: the open fails with net::ERR_BLOCKED_BY_CLIENT (uitestingplayground.com, neverssl.com). Either
    # setting, set by hand to off, lets such pages load. pb then guards what the warning was for: it names a plain-HTTP
    # page in a NOTE and types no card data on one (plain_http, card_allowed).
    d["https_only_mode_enabled"] = False
    d["https_first_balanced_mode_enabled"] = False
    if fresh:
        d["credentials_enable_service"] = False
        d["profile"]["password_manager_enabled"] = False
        d.setdefault("autofill", {}).update({"profile_enabled": False, "credit_card_enabled": False})
        d.setdefault("translate", {})["enabled"] = False
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f)


def chrome_stamp():
    """What identifies the installed Chrome without starting it: the version folders next to chrome.exe ('' when it is
    not where Chrome installs itself)."""
    for base in (os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Google", "Chrome", "Application"),
                 os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Google", "Chrome", "Application"),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application"),
                 "/opt/google/chrome", "/Applications/Google Chrome.app/Contents/Frameworks/Google Chrome Framework.framework/Versions"):
        with contextlib.suppress(Exception):
            vs = sorted(d for d in os.listdir(base) if re.fullmatch(r"\d+(\.\d+){3}", d))
            if vs:
                return base + "|" + ",".join(vs)
    return ""


async def headed_user_agent(pw):
    """The user agent this Chrome sends in a window. A headless Chrome says "HeadlessChrome/157.0.0.0" instead of
    "Chrome/157.0.0.0", and that alone got pb --headless refused by walls (2026-11-17: headless read 2 of 16 walled pages,
    headed 10; with only the user agent corrected, headless read 4 of the 5 retried). Read from the browser itself once
    per installed version (a headless start of a few hundred ms), kept in ~/.pb/chrome_ua.json."""
    cache, stamp = os.path.join(STATE_DIR, "chrome_ua.json"), chrome_stamp()
    with contextlib.suppress(Exception):
        with open(cache, encoding="utf-8") as f:
            c = json.load(f)
        if stamp and c.get("stamp") == stamp and c.get("ua"):
            return c["ua"]
    ua = None
    with contextlib.suppress(Exception):
        b = await pw.chromium.launch(channel="chrome", headless=True)
        try:
            pg = await b.new_page()
            ua = await pg.evaluate("navigator.userAgent")
        finally:
            await b.close()
    if not ua:
        return None
    ua = ua.replace("HeadlessChrome/", "Chrome/")
    with contextlib.suppress(Exception):
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(cache, "w", encoding="utf-8") as f:
            json.dump({"stamp": stamp, "ua": ua}, f)
    return ua


async def serve(session, opts):
    from patchright.async_api import async_playwright
    prof = opts.get("profile") or session
    if not (os.path.isabs(prof) or os.sep in prof or "/" in prof):
        prof = os.path.join(os.path.expanduser("~"), ".patchright-" + prof)
    ensure_prefs(prof)
    pw = await async_playwright().start()
    # chromium_sandbox=True keeps Chrome's sandbox on, so no "--no-sandbox" warning bar (Playwright's default turns it off).
    extra = {}
    if os.environ.get("PB_HAR"):
        # test runs: keep the session's HTTP traffic (bodies inside the zip), written when the browser closes
        extra = {"record_har_path": os.environ["PB_HAR"], "record_har_content": "attach"}
    if opts.get("headless"):
        # A headless Chrome comes up 780x580 on an 800x600 screen, and sites answer that with their phone or tablet
        # layout (search box behind an icon, menu behind a hamburger). Headed windows are sized after launch (fit_window),
        # so a headed Chrome gets no extra flag.
        w, h = (opts.get("window") or WINDOW_DEFAULT).split("x")
        # (a screen with a taskbar strip, as a desktop has: a headless screen's available height equals its height)
        extra["args"] = [f"--window-size={w},{h}", "--screen-info={%dx%d workAreaBottom=48}" % (max(1920, int(w)), max(1080, int(h)))]
        # the user agent of a window, not "HeadlessChrome": set for the whole context, so pages, frames and workers say
        # it, and the client hints (Sec-CH-UA, navigator.userAgentData with its full version list) stay those of Chrome
        ua = await headed_user_agent(pw)
        if ua and "Headless" not in ua:
            extra["user_agent"] = ua
    ctx = await pw.chromium.launch_persistent_context(prof, channel="chrome", headless=bool(opts.get("headless")), no_viewport=True,
                                                      chromium_sandbox=True, **extra)
    S = Session(ctx, opts, session)
    await S.init()
    if not opts.get("headless"):
        with contextlib.suppress(Exception):
            await S.fit_window(opts.get("window"))
    server = await asyncio.start_server(S.handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    with open(state_path(session), "w", encoding="utf-8") as f:
        json.dump({"port": port, "pid": os.getpid(), "profile": prof, "started": time.time()}, f)
    ctx.on("close", lambda *_: S.closed.set())

    async def watchdog():
        while not S.closed.is_set():
            await asyncio.sleep(30)
            if time.time() - S.last_cmd > 3 * 3600:
                S.closed.set()

    asyncio.ensure_future(watchdog())
    await S.closed.wait()
    async with S.lock:                 # the request that closed the browser (pb stop) finishes and sends its answer first
        pass
    await asyncio.sleep(0.2)
    server.close()
    with contextlib.suppress(Exception):
        await ctx.close()
    with contextlib.suppress(Exception):
        await pw.stop()
    with contextlib.suppress(Exception):
        os.remove(state_path(session))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "__serve":
        asyncio.run(serve(sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}))
    else:
        client_main()
