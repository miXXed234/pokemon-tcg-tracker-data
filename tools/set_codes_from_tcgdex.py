"""Collects the short set codes printed on cards (POR, CRI, PBL) from TCGdex.

The code in a card's bottom-left corner is the only thing many people can read
off a card, and the set browser shows logos, which do not spell it out. So the
browser can show codes instead, and this is where it gets them.

TCGdex has them, but only in the *set detail*: `GET /sets` returns id, name and
card counts and nothing else, so filling 373 sets from the app would be 373
requests of a heavy endpoint for a cosmetic toggle. Collecting them here once
costs the app nothing, works offline, and never goes stale -- a set's code is
printed on cardboard and cannot change.

This only seeds what already exists. A newly released set fills its own code in
on the app side, out of the set detail that `syncSetCardBriefs` fetches anyway,
so this does not have to be re-run for every release. Re-running it is harmless
and will pick up codes TCGdex has added since.

Japanese sets have no code at all here (0 of 172) -- the series does not print
them -- and 15 promo sets have none either. Those simply keep their logo.

Usage:  python tools/set_codes_from_tcgdex.py

Run `node tools/build.mjs` afterwards, or nothing reaches the app.
"""

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.tcgdex.net/v2"
AGENT = "HoloChase/1.0 (private collection tracker; github.com/miXXed234)"

PAUSE = 0.25
RETRIES = 4


def fetch(url):
    """Reads a url, backing off: TCGdex answers the odd 502/503 under load."""
    last = None
    for attempt in range(RETRIES):
        time.sleep(PAUSE * (1 + 2 * attempt))
        try:
            request = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.load(response)
        except Exception as error:
            last = error
    print(f"  ! {url}: {last}")
    return None


def set_ids(language):
    return [s["id"] for s in (fetch(f"{API}/{language}/sets") or [])]


def main():
    codes = {}
    for language in ("en", "ja"):
        ids = set_ids(language)
        found = 0
        for index, set_id in enumerate(ids, 1):
            detail = fetch(f"{API}/{language}/sets/{urllib.parse.quote(set_id)}")
            abbreviation = (detail or {}).get("abbreviation") or {}
            # "official" is what is printed on the card, and it is the same in
            # every language -- checked against the /de mount, where every set
            # reports the identical code and "localized" is always absent.
            # Preferring "localized" anyway costs nothing and would pick up a
            # language that one day prints its own.
            code = abbreviation.get("localized") or abbreviation.get("official")
            if code:
                codes[set_id] = code
                found += 1
            if index % 60 == 0:
                print(f"  {language} {index}/{len(ids)} …", flush=True)
        print(f"{language}: {found} of {len(ids)} sets have a code")

    path = ROOT / "src" / "set_codes.json"
    path.write_text(
        json.dumps(dict(sorted(codes.items())), indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"\n{len(codes)} codes written. Now run: node tools/build.mjs")


if __name__ == "__main__":
    main()
