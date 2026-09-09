#!/usr/bin/env python3
"""Extract Booking.com room-level availability from a signed-in Chrome over CDP.

Why this exists: the room table (bed configuration, per-rate price, per-rate
free-cancellation deadline) is the only place the real answer lives, and no
metasearch API exposes it. Writing this extractor inline in the page costs ~24
tool calls and loses its state on every navigation. It lives here instead.

Launch Chrome once (Chrome 136+ refuses --remote-debugging-port on the default
profile, so use a dedicated one that persists your Booking.com login):

    chrome.exe --remote-debugging-port=9222 \
        --user-data-dir=C:\\Users\\jcamino\\Code\\.chrome-cdp-profile

Then sign in to booking.com in that window, once. After that:

    python booking_rooms.py --checkin 2026-09-19 --checkout 2026-09-23 \
        trunk sequence-miyashita-park-tokyo all-day-place-shibuya

Results append to --out (default rooms.json) after every property, so an
interrupted run keeps everything it already fetched.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from datetime import date

try:
    import websocket  # websocket-client
except ImportError:
    sys.exit("pip install websocket-client")

CDP_HOST = "http://localhost:9222"


# --------------------------------------------------------------------------
# CDP client (same shape as ~/Code/united-award/cdp.py, kept self-contained)
# --------------------------------------------------------------------------
class Page:
    def __init__(self, ws_url):
        # Chrome 111+ enforces an Origin check on the CDP socket and 403s a real
        # one; omitting the header entirely satisfies it.
        self.ws = websocket.create_connection(ws_url, timeout=90, suppress_origin=True)
        self._id = 0

    @classmethod
    def attach(cls, match=None):
        try:
            with urllib.request.urlopen(CDP_HOST + "/json", timeout=10) as r:
                targets = json.loads(r.read())
        except Exception:
            sys.exit("no CDP at %s - launch Chrome with --remote-debugging-port=9222" % CDP_HOST)
        pages = [t for t in targets if t["type"] == "page"]
        if match:
            pages = [t for t in pages if match in t.get("url", "")] or pages
        if not pages:
            sys.exit("no page targets in that Chrome")
        return cls(pages[0]["webSocketDebuggerUrl"])

    def send(self, method, **params):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise RuntimeError("%s: %s" % (method, msg["error"]))
                return msg.get("result", {})

    def eval(self, expr):
        r = self.send("Runtime.evaluate", expression=expr,
                      returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")

    def goto(self, url, settle=1.0):
        self.send("Page.enable")
        self.send("Page.navigate", url=url)
        time.sleep(settle)

    def wait_for(self, js_predicate, timeout=25, interval=0.7):
        """Poll OUTSIDE the evaluate. Sleeps inside one evaluate time it out at 45s."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if self.eval(js_predicate):
                    return True
            except RuntimeError:
                pass
            time.sleep(interval)
        return False

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


# --------------------------------------------------------------------------
# Room table extraction
# --------------------------------------------------------------------------
# Booking renders one <tr> per RATE. The room-type cell carries a rowspan and so
# appears only on the first rate row of each room block; every later row in that
# block must inherit it. Missing that is what makes hand-rolled parsers wrong.
EXTRACT_JS = r"""
(() => {
  const t = el => (el ? el.innerText.replace(/\s+/g, ' ').trim() : '');
  const table = document.querySelector('#hprt-table');
  if (!table) {
    // No room table means sold out for these dates far more often than a broken
    // page. Say which, so "no availability" is reported as a finding.
    const b = document.body ? document.body.innerText : '';
    const so = /sold out|no availability|not available on our site|no rooms available|fully booked/i.test(b);
    return { error: so ? 'SOLD OUT for these dates' : 'no #hprt-table', soldOut: so, title: document.title };
  }

  const rows = [...table.querySelectorAll('tbody tr')];
  const out = [];
  let name = '', bed = '', features = [];

  for (const tr of rows) {
    const rt = tr.querySelector('td.hprt-table-cell-roomtype, .hprt-table-cell-roomtype');
    if (rt) {
      name = t(rt.querySelector('.hprt-roomtype-link, .hprt-roomtype-icon-link'))
             || t(rt).split(' - ')[0];
      bed = t(rt.querySelector('.hprt-roomtype-bed, [class*="bed-types"], [data-testid="bed-types"]'));
      features = [...rt.querySelectorAll('.hprt-facilities-facility')].map(t).filter(Boolean);
    }
    // A rate row must have a price cell; skip header and spacer rows.
    const priceCell = tr.querySelector('.hprt-table-cell-price, [class*="table-cell-price"]');
    if (!priceCell) continue;

    out.push({
      name: name,
      bedType: bed,
      features: features,
      priceDisplay: t(priceCell),
      occupancy: t(tr.querySelector('.hprt-table-cell-occupancy, .hprt-occupancy-occupancy-info')),
      cancellation: t(tr.querySelector('.hprt-table-cell-conditions, [class*="cell-conditions"]')),
      selectText: t(tr.querySelector('.hprt-table-cell-select, [class*="cell-select"]')),
    });
  }
  // House rules: check-in / check-out windows matter for late arrivals and
  // early departures, and they live outside the room table.
  const pol = document.querySelector(
    '[data-testid="property-policies"], #hotelPoliciesInc, .hp_policies_box, [data-section-id="policies"]');
  const polText = t(pol) || '';
  const body = document.body ? document.body.innerText : '';
  const grab = (label, src) => {
    const m = src.match(new RegExp(label + '\\s*(?:\\n|\\s)+((?:From|Until|Available)[^\\n]{0,60})', 'i'));
    return m ? m[1].trim() : '';
  };
  const rawPol = pol ? pol.innerText : body;
  // Review score and count: a recommendation without both is a guess.
  const rsEl = document.querySelector('[data-testid="review-score-component"], [data-testid="review-score-right-component"]');
  const rsText = t(rsEl) || body.slice(0, 20000);
  const sc = rsText.match(/(?:Scored\s+)?(\d(?:\.\d)?)\s+(?:\d(?:\.\d)?\s+)?(Exceptional|Wonderful|Superb|Fabulous|Very good|Good|Pleasant|Review score)?\s*[·•]?\s*([\d,]+)\s+reviews?/i)
          || body.match(/Scored\s+(\d(?:\.\d)?)[\s\S]{0,80}?([\d,]+)\s+reviews?/i);
  return {
    rooms: out, title: document.title, url: location.href,
    checkin: grab('Check-in', rawPol), checkout: grab('Check-out', rawPol),
    policies: polText.slice(0, 1200),
    reviewScore: sc ? sc[1] : null,
    reviewCount: sc ? (sc[3] || sc[2] || '').replace(/,/g, '') : null,
    noReviewsYet: /No review score yet/i.test(body),
    // "3,100 ft walking from Gion Shijo Station" - the only walk figure on the
    // page that was measured rather than estimated. Use it over a guessed pin.
    stationLine: (body.match(/[\d,.]+\s*(?:ft|mi|m|km)\s+walking from\s+[^\n]{0,60}/i) || [null])[0],
  };
})()
"""

# Booking writes dates as "September 12, 2026", sometimes "18:00 on September 12, 2026".
DEADLINE = re.compile(
    r"free cancellation\s+before\s+"
    r"((?:\d{1,2}:\d{2}\s+on\s+)?(?:[A-Z][a-z]+\s+\d{1,2},\s*\d{4}|\d{1,2}\s+[A-Z][a-z]+\s+\d{4}))",
    re.I,
)
PAY_LATER = re.compile(r"pay nothing until\s+([A-Z][a-z]+\s+\d{1,2},\s*\d{4})", re.I)
LEFT = re.compile(r"only\s+(\d+)\s+(?:rooms?\s+)?left", re.I)
# "Current price $2,230" is authoritative; the first "$N per night" is the nightly rate.
CURRENT = re.compile(r"current price\s*[^\d]{0,3}([\d,]+)", re.I)
PER_NIGHT = re.compile(r"[^\d]([\d,]+)\s*per night", re.I)
MONEY = re.compile(r"[^\d]([\d,]{3,})")
EXCLUDED = re.compile(r"excluded:\s*([^A-Z]*?(?:VAT|tax|charge)[^,]*)", re.I)

# Bed COUNT decides whether a room sleeps two people separately. "1 twin bed" is a
# single and fails two adults; "2 twin beds" is what a twin request actually means.
BED_TOKEN = re.compile(
    r"(\d+)\s+(twin|single|full|double|queen|king|large double|semi-double|bunk|sofa|futon|tatami)",
    re.I,
)
SINGLE_SIZE = {"twin", "single"}
DOUBLE_SIZE = {"full", "double", "queen", "king", "large double", "semi-double"}
EXTRA = {"sofa", "futon", "bunk", "tatami"}


BARE_KIND = re.compile(
    r"\b(twin|single|full|double|queen|king|semi-double|bunk)\b", re.I)


def parse_beds(bed_type, room_name=None):
    """-> (beds list, summary). Summary is the field that answers the user's question.

    two_beds : two or more separate sleeping surfaces (2 twins, 2 singles, bunks)
    double   : one double/queen/king/full - sleeps two together
    single   : one single bed - FAILS two adults
    """
    beds = [{"count": int(n), "kind": k.lower()} for n, k in BED_TOKEN.findall(bed_type or "")]
    if not beds and room_name:
        # Some rows ship an empty bed cell but name the bed ("Double Queen Size Bed").
        # Weaker evidence than the bed cell - callers see bedSource="room-name".
        beds = [{"count": int(n), "kind": k.lower(), "from": "name"}
                for n, k in BED_TOKEN.findall(room_name)]
        if not beds:
            kinds = [k.lower() for k in BARE_KIND.findall(room_name)]
            if "twin" in kinds and re.search(r"\btwin\b", room_name, re.I):
                beds = [{"count": 2, "kind": "twin", "from": "name"}]
            elif kinds:
                beds = [{"count": 1, "kind": kinds[0], "from": "name"}]
    if not beds:
        return beds, "unknown"
    singles = sum(b["count"] for b in beds if b["kind"] in SINGLE_SIZE)
    doubles = sum(b["count"] for b in beds if b["kind"] in DOUBLE_SIZE)
    bunks = sum(b["count"] for b in beds if b["kind"] == "bunk")
    # Futons on tatami are the Japanese twin: two laid out separately are two
    # beds. One futon is a single. Sofa beds never count toward the answer.
    futons = sum(b["count"] for b in beds if b["kind"] == "futon")
    if doubles >= 1:
        return beds, "double"
    if singles >= 2 or bunks >= 1 or futons >= 2:
        return beds, "two_beds"
    if singles == 1 or futons == 1:
        return beds, "single"
    return beds, "unknown"


def _money(m):
    try:
        return float(m.group(1).replace(",", ""))
    except (ValueError, AttributeError):
        return None


def normalise(raw, nights):
    pd = raw.get("priceDisplay") or ""
    # The price cell reads "$479 per night $2,478 $2,230 Original price $2,478
    # Current price $2,230 4 nights 10% off ...". Grabbing the first number gives
    # the nightly rate and calling it a total - the bug this parser exists to avoid.
    total = _money(CURRENT.search(pd))
    per_night = _money(PER_NIGHT.search(pd))
    if total is None:
        cands = [float(x.replace(",", "")) for x in MONEY.findall(pd)]
        cands = [c for c in cands if per_night is None or c > per_night]
        total = min(cands) if cands else None
    if total is None and per_night is not None and nights:
        total = round(per_night * nights, 2)
    if per_night is None and total is not None and nights:
        per_night = round(total / nights, 2)

    cond = raw.get("cancellation") or ""
    dl = DEADLINE.search(cond)
    pay_later = PAY_LATER.search(cond)
    left = LEFT.search((raw.get("selectText") or "") + " " + cond)
    mo = re.search(r"(\d+)", raw.get("occupancy") or "")
    excl = EXCLUDED.search(pd)
    beds, summary = parse_beds(raw.get("bedType"), raw.get("name"))
    return {
        "name": raw.get("name"),
        "bedType": raw.get("bedType"),
        "beds": beds,
        "bedSummary": summary,
        "bedSource": ("bed-cell" if raw.get("bedType")
                      else "room-name" if beds else "none"),
        "total": total,
        "perNight": per_night,
        "priceDisplay": pd,
        "taxExcluded": excl.group(1).strip() if excl else "",
        "sleeps": int(mo.group(1)) if mo else None,
        "features": raw.get("features") or [],
        "cancellation": cond,
        "cancelDeadline": dl.group(1) if dl else None,
        "payNothingUntil": pay_later.group(1) if pay_later else None,
        "refundable": bool(re.search(r"free cancellation", cond, re.I)),
        "breakfast": "yes" if re.search(r"breakfast", cond, re.I) else "",
        "roomsLeft": int(left.group(1)) if left else None,
    }


def fetch(page, slug, cc, q, nights, settle):
    url = "https://www.booking.com/hotel/%s/%s.en-gb.html?%s" % (cc, slug, q)
    page.goto(url, settle=settle)
    ok = page.wait_for("!!document.querySelector('#hprt-table')", timeout=25)
    res = page.eval(EXTRACT_JS) or {}
    if not ok or res.get("error"):
        return {"slug": slug, "url": url, "rooms": [], "title": res.get("title"),
                "error": res.get("error") or "timeout waiting for room table"}
    return {"slug": slug, "url": url, "title": res.get("title"),
            "checkin": res.get("checkin"), "checkout": res.get("checkout"),
            "policies": res.get("policies"),
            "reviewScore": res.get("reviewScore"), "reviewCount": res.get("reviewCount"),
            "noReviewsYet": res.get("noReviewsYet"), "stationLine": res.get("stationLine"),
            "rooms": [normalise(r, nights) for r in res.get("rooms", [])]}


def main():
    ap = argparse.ArgumentParser(
        description="Booking.com room-level extractor (signed-in Chrome via CDP)")
    ap.add_argument("slugs", nargs="+",
                    help="booking.com hotel slugs, e.g. trunk all-day-place-shibuya")
    ap.add_argument("--checkin", required=True)
    ap.add_argument("--checkout", required=True)
    ap.add_argument("--adults", type=int, default=2)
    ap.add_argument("--rooms", type=int, default=1)
    ap.add_argument("--currency", default="USD")
    ap.add_argument("--cc", default="jp", help="country segment in the hotel URL path")
    ap.add_argument("--out", default="rooms.json")
    ap.add_argument("--settle", type=float, default=2.5,
                    help="seconds after navigate before polling")
    ap.add_argument("--bed", default="any",
                    choices=["two-beds", "double", "sleeps-two", "single", "any"],
                    help="sleeps-two = two separate beds OR one double/larger "
                         "(excludes single-bed rooms)")
    ap.add_argument("--refundable-only", action="store_true")
    ap.add_argument("--refetch", action="store_true", help="ignore cached entries in --out")
    args = ap.parse_args()

    nights = (date.fromisoformat(args.checkout) - date.fromisoformat(args.checkin)).days
    if nights < 1:
        sys.exit("checkout must be after checkin")

    q = ("checkin=%s&checkout=%s&group_adults=%d&no_rooms=%d&group_children=0"
         "&selected_currency=%s" % (args.checkin, args.checkout, args.adults,
                                    args.rooms, args.currency))

    page = Page.attach(match="booking.com")
    # Genius badges only render for a signed-in member, which makes them the most
    # reliable signal; the header selectors change too often to trust alone.
    signed_in = bool(page.eval(
        "!!document.querySelector('[data-testid*=\"header-profile\"], a[href*=\"myreservations\"], a[href*=\"mybookings\"]')"
        " || /\\bGenius\\b/.test(document.body ? document.body.innerText : '')"
    ))
    if not signed_in:
        print("  warning: Chrome does not look signed in to booking.com - "
              "member/Genius rates will be missing", file=sys.stderr)

    results = []
    if os.path.exists(args.out) and not args.refetch:
        try:
            results = json.load(open(args.out, encoding="utf-8"))
        except Exception:
            results = []
    done = set(r["slug"] for r in results if not r.get("error"))

    for slug in args.slugs:
        if slug in done:
            print("  skip %s (cached in %s)" % (slug, args.out), file=sys.stderr)
            continue
        try:
            rec = fetch(page, slug, args.cc, q, nights, args.settle)
        except RuntimeError as e:
            rec = {"slug": slug, "rooms": [], "error": str(e)}
        rec["signedIn"] = signed_in
        results = [r for r in results if r["slug"] != slug] + [rec]
        # Persist after every property: a crash or navigation never costs the batch.
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=1, ensure_ascii=False)
        print("  %s: %d rate rows%s" % (slug, len(rec.get("rooms") or []),
              " - " + rec["error"] if rec.get("error") else ""), file=sys.stderr)
    page.close()

    print(json.dumps({"checkin": args.checkin, "checkout": args.checkout,
                      "nights": nights, "adults": args.adults,
                      "signedIn": signed_in, "properties": len(results)},
                     ensure_ascii=False))
    for rec in results:
        if rec.get("error"):
            print("\n## %s  !! %s" % (rec["slug"], rec["error"]))
            continue
        rooms = rec.get("rooms") or []
        want = {"two-beds": {"two_beds"}, "double": {"double"}, "single": {"single"},
                "sleeps-two": {"two_beds", "double"}}.get(args.bed)
        shown = [r for r in rooms if r["bedSummary"] in want] if want else list(rooms)
        if args.refundable_only:
            shown = [r for r in shown if r["refundable"]]
        # Collapse duplicate rate rows: keep the cheapest per (room, bed, refundable).
        best = {}
        for r in shown:
            k = (r["name"], r["bedType"], r["refundable"])
            if k not in best or (r["total"] or 9e9) < (best[k]["total"] or 9e9):
                best[k] = r
        shown = list(best.values())
        print("\n## %s  (%d rooms / %d rate rows)" % (rec["slug"], len(shown), len(rooms)))
        if rec.get("checkin") or rec.get("checkout"):
            print("   check-in %s | check-out %s" % (rec.get("checkin") or "?", rec.get("checkout") or "?"))
        if rec.get("reviewScore"):
            print("   Booking score %s (%s reviews)" % (rec["reviewScore"], rec.get("reviewCount") or "?"))
        for r in sorted(shown, key=lambda x: (x["total"] is None, x["total"] or 0)):
            print("  - %s" % r["name"])
            print("    bed: %s  -> %s%s" % (
                r["bedType"] or "(bed cell empty)", r["bedSummary"],
                "  [inferred from room name - verify]"
                if r.get("bedSource") == "room-name" else ""))
            print("    total %s / %s nights   (%s per night)" % (r["total"], nights, r["perNight"]))
            if r["taxExcluded"]:
                print("    NOT in total: %s" % r["taxExcluded"])
            print("    cancel: %s" % (
                "free until " + r["cancelDeadline"] if r["cancelDeadline"]
                else "refundable, DATE UNPARSED - read the row" if r["refundable"]
                else "NON-REFUNDABLE"))
            if r["payNothingUntil"]:
                print("    pay nothing until %s" % r["payNothingUntil"])
            if r["roomsLeft"]:
                print("    only %d left" % r["roomsLeft"])


if __name__ == "__main__":
    main()
