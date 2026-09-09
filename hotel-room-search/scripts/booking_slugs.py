#!/usr/bin/env python3
"""Harvest Booking.com property slugs from one or more search-results pages.

booking_rooms.py takes slugs, not names. Guessing them is unreliable; this reads
them off the search page in the same CDP Chrome, together with the card's
headline price and rating so you can shortlist before fetching room tables.

    python booking_slugs.py --checkin 2026-09-23 --checkout 2026-09-26 \
        "Gion, Kyoto" "Kawaramachi, Kyoto" --out slugs.json
"""

import argparse
import json
import sys
import time
import urllib.parse

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from booking_rooms import Page  # noqa: E402

CARDS_JS = r"""
(() => {
  const t = el => (el ? el.innerText.replace(/\s+/g, ' ').trim() : '');
  return [...document.querySelectorAll('[data-testid="property-card"]')].map(c => {
    const a = c.querySelector('a[href*="/hotel/"]');
    const m = a ? a.href.match(/\/hotel\/([a-z]{2})\/([^.?]+)\./) : null;
    return {
      cc: m ? m[1] : null, slug: m ? m[2] : null,
      name: t(c.querySelector('[data-testid="title"]')),
      price: t(c.querySelector('[data-testid="price-and-discounted-price"]')),
      rating: t(c.querySelector('[data-testid="review-score"]')).slice(0, 40),
      distance: t(c.querySelector('[data-testid="distance"]')),
      beds: t(c.querySelector('[data-testid="recommended-units"]')).slice(0, 120),
      avail: t(c.querySelector('[data-testid="availability-single"]')).slice(0, 80),
    };
  }).filter(x => x.slug);
})()
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("queries", nargs="+", help='search strings, e.g. "Gion, Kyoto"')
    ap.add_argument("--checkin", required=True)
    ap.add_argument("--checkout", required=True)
    ap.add_argument("--adults", type=int, default=2)
    ap.add_argument("--currency", default="USD")
    ap.add_argument("--order", default="distance_from_search")
    ap.add_argument("--pages", type=int, default=2, help="result pages per query (25 cards each)")
    ap.add_argument("--out", default="slugs.json")
    args = ap.parse_args()

    page = Page.attach(match="booking.com")
    seen = {}
    for q in args.queries:
        for pg in range(args.pages):
            url = ("https://www.booking.com/searchresults.en-gb.html?ss=%s&checkin=%s&checkout=%s"
                   "&group_adults=%d&no_rooms=1&group_children=0&selected_currency=%s&order=%s&offset=%d"
                   % (urllib.parse.quote(q), args.checkin, args.checkout, args.adults,
                      args.currency, args.order, pg * 25))
            page.goto(url, settle=2.5)
            page.wait_for("document.querySelectorAll('[data-testid=\"property-card\"]').length > 0", timeout=20)
            time.sleep(1.0)
            cards = page.eval(CARDS_JS) or []
            for c in cards:
                c["query"] = q
                seen.setdefault(c["slug"], c)
            print("  %r page %d: %d cards" % (q, pg + 1, len(cards)), file=sys.stderr)
    page.close()
    out = list(seen.values())
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    for c in out:
        print("%-45s %-9s %-28s %s | %s" % (c["slug"][:45], c["price"][:9], c["name"][:28], c["distance"][:22], c["beds"][:50]))
    print("\n%d unique properties -> %s" % (len(out), args.out), file=sys.stderr)


if __name__ == "__main__":
    main()
