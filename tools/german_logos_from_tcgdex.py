"""Gives a sub-set the German logo of the set it belongs to.

A Trainer Gallery, a Shiny Vault, a Classic Collection: TCGdex lists them as
sets of their own and serves no logo for any of them, in any language. We fill
that from pokemontcg.io, but pokemontcg.io is English-only, so the German view
ended up showing "SILVER TEMPEST" above a set the app calls "Silberne
Sturmwinde", right next to the parent set wearing the German logo properly.

The fix needs no new artwork. A sub-set wears its parent's logo anyway -- the
pictures we fetched are the parent wordmarks -- and TCGdex does serve that
parent logo in German. So each entry below says which set's German logo to
borrow, and the file lands in images/logos/de/ under the *sub-set's* name.

Pairs are written out rather than derived. The ids do not follow one rule
(swsh12tg belongs to swsh12, swsh12.5gg to swsh12.5, cel25cc to cel25), and a
rule that guessed wrong would put a confident, wrong logo on a tile.

Usage:  python tools/german_logos_from_tcgdex.py [setId ...]

Idempotent: a logo already on disk is kept. Run `node tools/build.mjs`
afterwards, or nothing reaches the app.
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
TCGDEX = "https://api.tcgdex.net/v2/de/sets"
AGENT = "HoloChase/1.0 (private collection tracker; github.com/miXXed234)"

LOGO_WIDTH = 480
PAUSE = 0.4
RETRIES = 5

# Sub-set -> the set whose German logo it should wear.
PARENTS = {
    "swsh9tg": "swsh9",        # Strahlende Sterne
    "swsh10tg": "swsh10",      # Astralglanz
    "swsh11tg": "swsh11",      # Verlorener Ursprung
    "swsh12tg": "swsh12",      # Silberne Sturmwinde
    "swsh12.5gg": "swsh12.5",  # Zenit der Könige
    "cel25cc": "cel25",        # Celebrations
    "swsh4.5sv": "swsh4.5",    # Glänzendes Schicksal, dessen Shiny Vault
}

# Sub-sets whose parent has no German logo at TCGdex either, but whose German
# logo we already hold ourselves. "30 Jahre" came from PokeWiki.
COPIES = {"30th-c": "30th"}


def slug(set_id):
    return re.sub(r"[^a-z0-9]", "_", set_id.lower()) + ".png"


def fetch(url):
    """Reads a url, retrying: TCGdex answers the odd 502/503 under load.

    Backing off rather than hammering. Five tries a fifth of a second apart is
    not a retry, it is the same request five times inside one bad moment, which
    is exactly how the first run still fell over on a 503.
    """
    last = None
    for attempt in range(RETRIES):
        time.sleep(PAUSE * (1 + 4 * attempt))
        try:
            request = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except Exception as error:
            last = error
    raise last


def german_logo_url(set_id):
    return json.loads(fetch(f"{TCGDEX}/{urllib.parse.quote(set_id)}")).get("logo")


def save_logo(raw, path):
    image = Image.open(BytesIO(raw)).convert("RGBA")
    width = min(LOGO_WIDTH, image.width)
    height = round(image.height * width / image.width)
    image.resize((width, height), Image.LANCZOS).save(path, "PNG", optimize=True)


def main():
    chosen = sys.argv[1:] or sorted(PARENTS) + sorted(COPIES)
    unknown = [s for s in chosen if s not in PARENTS and s not in COPIES]
    if unknown:
        raise SystemExit(f"unknown set(s): {', '.join(unknown)}")

    logo_file = ROOT / "src" / "set_logos.json"
    catalogue = json.loads(logo_file.read_text(encoding="utf-8"))
    german = catalogue["logosDe"]
    done = 0

    for set_id in chosen:
        path = ROOT / "images" / "logos" / "de" / slug(set_id)
        if path.exists():
            german.setdefault(set_id, slug(set_id))
            print(f"{set_id:12s} kept")
            continue

        if set_id in COPIES:
            source = ROOT / "images" / "logos" / "de" / slug(COPIES[set_id])
            if not source.exists():
                print(f"{set_id:12s} ! no German logo for {COPIES[set_id]} to copy")
                continue
            path.write_bytes(source.read_bytes())
        else:
            url = german_logo_url(PARENTS[set_id])
            if not url:
                print(f"{set_id:12s} ! TCGdex serves no German logo for {PARENTS[set_id]}")
                continue
            save_logo(fetch(url + ".webp"), path)

        german[set_id] = slug(set_id)
        done += 1
        print(f"{set_id:12s} new (from {PARENTS.get(set_id) or COPIES[set_id]})")

    logo_file.write_text(json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n{done} German logos. Now run: node tools/build.mjs")


if __name__ == "__main__":
    main()
