#!/usr/bin/env python3
"""Read house rules, cancellation deadline and bed setup from Airbnb listing pages.

The Airbnb MCP (`airbnb_listing_details`) returns amenities only - its POLICIES,
LOCATION and DESCRIPTION sections come back empty - so check-in windows and the
cancellation deadline have to be read from the listing page. Same CDP Chrome as
booking_rooms.py; signed-out is fine for these fields.

    python airbnb_rules.py --checkin 2026-09-23 --checkout 2026-09-26 38306412 52779244
"""

import argparse
import json
import re
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from booking_rooms import Page  # noqa: E402

TEXT_JS = "document.body ? document.body.innerText : ''"

PATTERNS = {
    "checkin":  re.compile(r"Check-in(?:\s*time)?:?\s*(?:after\s+)?([0-9]{1,2}:[0-9]{2}\s*[AP]M(?:\s*[-–]\s*[0-9]{1,2}:[0-9]{2}\s*[AP]M)?)", re.I),
    "checkout": re.compile(r"Check-?out(?:\s*time)?:?\s*(?:before\s+)?([0-9]{1,2}:[0-9]{2}\s*[AP]M)", re.I),
    "cancel":   re.compile(r"(Free cancellation (?:before|until|for 48 hours)[^\n.]{0,80})", re.I),
    "cancelPolicy": re.compile(r"Cancellation policy\s*\n\s*([^\n]{0,160})", re.I),
    "selfCheckin": re.compile(r"(Self check-in[^\n]{0,80})", re.I),
    "beds":     re.compile(r"((?:\d+\s+(?:king|queen|double|full|single|twin|sofa|futon|bunk)[^\n,]{0,20}(?:,\s*)?)+)", re.I),
    "guests":   re.compile(r"(\d+)\s+guests?", re.I),
    "total":    re.compile(r"\$([\d,]+)\s+(?:total|for \d+ nights)", re.I),
    "rating":   re.compile(r"(\d\.\d{1,2})\s*(?:\(|·)\s*(\d+)\s*reviews?", re.I),
}


def read(page, lid, ci, co, adults, settle):
    url = "https://www.airbnb.com/rooms/%s?check_in=%s&check_out=%s&adults=%d" % (lid, ci, co, adults)
    page.goto(url, settle=settle)
    page.wait_for("/Check-in|Cancellation policy|House rules/i.test(document.body ? document.body.innerText : '')", timeout=20)
    # Dismiss the translation / login modal if it sits over the page.
    page.eval("(()=>{const b=[...document.querySelectorAll('button[aria-label=\"Close\"]')];b.forEach(x=>x.click());return b.length})()")
    time.sleep(0.8)
    body = page.eval(TEXT_JS) or ""
    out = {"id": lid, "url": url, "title": page.eval("document.title")}
    for k, rx in PATTERNS.items():
        m = rx.search(body)
        out[k] = (m.group(1).strip() if m else None)
    m = PATTERNS["rating"].search(body)
    if m:
        out["rating"], out["reviews"] = m.group(1), int(m.group(2))
    out["bodyLen"] = len(body)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--checkin", required=True)
    ap.add_argument("--checkout", required=True)
    ap.add_argument("--adults", type=int, default=2)
    ap.add_argument("--settle", type=float, default=3.0)
    ap.add_argument("--out", default="airbnb_rules.json")
    args = ap.parse_args()
    page = Page.attach()
    res = []
    for lid in args.ids:
        try:
            r = read(page, lid, args.checkin, args.checkout, args.adults, args.settle)
        except RuntimeError as e:
            r = {"id": lid, "error": str(e)}
        res.append(r)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1, ensure_ascii=False)
        print("  %s: in %s | out %s | %s | beds %s" % (lid, r.get("checkin"), r.get("checkout"),
              r.get("cancel") or r.get("cancelPolicy"), r.get("beds")), file=sys.stderr)
    page.close()
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
