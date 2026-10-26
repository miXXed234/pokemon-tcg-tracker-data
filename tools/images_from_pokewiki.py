"""Pulls card images off PokeWiki for sets neither TCGdex nor pokemontcg.io has.

The third source, and the last resort. It is German-language, so what it has is
the German print of a card, which suits this app: its cards are browsed under
German names. It is thin on coverage -- one card of the 30th Classic Collection,
none of the Trainer Galleries -- so it only gets asked where the other two have
nothing, and the entries are named by hand rather than searched for.

That naming is deliberate. PokeWiki files are titled after the card and the set
in German ("Basis-Feuer-Energie (Mega-Entwicklung).png") with no number
anywhere, so there is no key to match on and no way to check a guess. Writing
the pairs out is the only honest option at this size; a search would be
guessing, which is exactly what went wrong the one time the Bulbapedia run
guessed from a name.

Usage:  python tools/images_from_pokewiki.py [setId ...]

Idempotent: files already on disk are skipped. Run `node tools/build.mjs`
afterwards, or nothing reaches the app.
"""

import json
import sys
import time
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
API = "https://www.pokewiki.de/api.php"
AGENT = "HoloChase/1.0 (private collection tracker; github.com/miXXed234)"

CARD_WIDTH = 500
PAUSE = 0.4

# Our card id -> the PokeWiki file holding that card, without the "Datei:".
# TCGdex lists 16 cards for the Mega Evolution energies and pictures none; the
# first eight are already covered here, these are the Basic prints.
CARDS = {
    "mee-009": "Basis-Pflanzen-Energie (Mega-Entwicklung).png",
    "mee-010": "Basis-Feuer-Energie (Mega-Entwicklung).png",
    "mee-011": "Basis-Wasser-Energie (Mega-Entwicklung).png",
    "mee-012": "Basis-Elektro-Energie (Mega-Entwicklung).png",
    "mee-013": "Basis-Psycho-Energie (Mega-Entwicklung).png",
    "mee-014": "Basis-Kampf-Energie (Mega-Entwicklung).png",
    "mee-015": "Basis-Finsternis-Energie (Mega-Entwicklung).png",
    "mee-016": "Basis-Metall-Energie (Mega-Entwicklung).png",
}


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def api(params):
    time.sleep(PAUSE)
    return json.loads(fetch(API + "?" + urllib.parse.urlencode(params)))


def file_urls(titles):
    """Direct download urls for file titles, 50 at a time as the API allows."""
    urls = {}
    for start in range(0, len(titles), 50):
        batch = titles[start:start + 50]
        data = api({
            "action": "query",
            "titles": "|".join("Datei:" + t for t in batch),
            "prop": "imageinfo",
            "iiprop": "url",
            "format": "json",
        })
        for page in data["query"]["pages"].values():
            info = page.get("imageinfo")
            if info:
                urls[page["title"][len("Datei:"):]] = info[0]["url"]
    return urls


def save_card(raw, path):
    image = Image.open(BytesIO(raw)).convert("RGB")
    height = round(image.height * CARD_WIDTH / image.width)
    image.resize((CARD_WIDTH, height), Image.LANCZOS).save(path, "JPEG", quality=82, optimize=True)


def main():
    chosen = sys.argv[1:]
    wanted = {
        card_id: title for card_id, title in CARDS.items()
        if (not chosen or card_id.rsplit("-", 1)[0] in chosen)
        and not (ROOT / "images" / "cards" / f"{card_id}.jpg").exists()
    }
    if not wanted:
        print("nothing to do, every listed card is already on disk")
        return

    urls = file_urls(sorted(set(wanted.values())))
    done = 0
    for card_id, title in sorted(wanted.items()):
        url = urls.get(title)
        if not url:
            print(f"  ! {card_id}: PokeWiki has no \"{title}\"")
            continue
        time.sleep(PAUSE)
        try:
            save_card(fetch(url), ROOT / "images" / "cards" / f"{card_id}.jpg")
        except Exception as error:  # one bad file must not stop the run
            print(f"  ! {card_id}: {error}")
            continue
        done += 1

    print(f"\n{done} card images. Now run: node tools/build.mjs")


if __name__ == "__main__":
    main()
