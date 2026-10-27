"""Fills the logo gaps from PokeCardex, for sets nobody else pictures.

TCGdex serves a logo for most international sets, and the German ones we curate
ourselves outrank it. What is left over are the promo sets, the trainer kits,
the McDonald's collections and a handful of oddities -- around 30 sets whose
tile had nothing at all.

The folder matters. `logos/<slug>.png` is PokeCardex's French edition: the
trainer kit reads "Kit Dresseur Leviator" and the McDonald's sets sit under a
"NOIR & BLANC" banner. `logos/US/<slug>.png` is the same picture in English
("Trainer Kit Excadrill", "SUN & MOON Promo McDonald's 2017"), which is what
belongs on a tile here. Taking the first folder and concluding the logos were
unusable was a mistake; the second one is the one to read.

Only gaps are filled, never a logo that already exists: ours rank last in the
app's chain anyway, so one of these only ever shows where the alternative is a
blank tile.

Run: python tools/logos_from_pokecardex.py
Then: node tools/build.mjs
"""
import io
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
LOGOS = ROOT / "images" / "logos"
AGENT = "HoloChase/1.0 (private collection tracker; github.com/miXXed234)"
CDN = "https://pokecardex.b-cdn.net/assets/images/logos/US/%s.png"
MAX_WIDTH = 480


def fetch(url, tries=3):
    last = None
    for attempt in range(tries):
        if attempt:
            time.sleep(0.4 * (1 + 2 * attempt))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(req, timeout=45) as resp:
                body = resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 404):
                return None
            last = exc
            continue
        except Exception as exc:  # noqa: BLE001
            last = exc
            continue
        else:
            return body if len(body) > 100 else None
    if last:
        print(f"      {url}: {last}")
    return None


def main():
    mapping = json.loads((ROOT / "src" / "pokecardex_sets.json").read_text("utf-8"))["international"]
    index = json.loads((ROOT / "src" / "set_logos.json").read_text("utf-8"))
    sets = json.loads(fetch("https://api.tcgdex.net/v2/en/sets").decode())

    filled, skipped = [], []
    for entry in sets:
        set_id = entry["id"]
        if index["logos"].get(set_id) or index["logosDe"].get(set_id) or entry.get("logo"):
            continue
        slug = mapping.get(set_id)
        if not slug:
            skipped.append(set_id)
            continue
        body = fetch(CDN % slug)
        if not body:
            skipped.append(set_id)
            continue
        img = Image.open(io.BytesIO(body)).convert("RGBA")
        if img.width > MAX_WIDTH:
            img = img.resize((MAX_WIDTH, round(img.height * MAX_WIDTH / img.width)), Image.LANCZOS)
        img.save(LOGOS / f"{set_id}.png", "PNG", optimize=True)
        index["logos"][set_id] = f"{set_id}.png"
        filled.append(set_id)

    index["logos"] = dict(sorted(index["logos"].items()))
    (ROOT / "src" / "set_logos.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + chr(10), "utf-8")
    print(f"logos filled {len(filled)}: {' '.join(filled)}")
    print(f"still without {len(skipped)}: {' '.join(skipped)}")


if __name__ == "__main__":
    main()
