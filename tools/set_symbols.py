"""Downloads the symbol printed on a card into images/symbols/<setId>.png.

The set browser can swap its logos for these, because the symbol is what is
actually printed in a card's bottom-left corner -- on the older sets it is the
*only* thing printed there, with no three-letter code next to it.

Two sources, in this order:

  TCGdex, for the 149 sets it has one for. Its own `symbol` field in the set
  list is served under a `/univ/` path that answers 400 InvalidBucketName, so
  the path is rebuilt with a language segment; and the field is missing for
  sets whose image does exist, so the logo folder is probed as well. Both
  extensions are tried: a good number of sets have only one of them.

  PokeCardex's CDN for the gaps, keyed by the code printed on the card. Only
  where that code is unambiguous -- its own slugs for the older sets are
  inventions (Shining Fates is "SWSH45" there, which no card carries), and the
  trainer kits and the pre-2023 McDonald's sets are left alone rather than
  guessed at: a wrong symbol on a tile is worse than none.

Sub-sets inherit their parent's file, which is correct -- a Trainer Gallery
card carries the parent set's symbol. Their code says so: "LOR:TG".

Run: python tools/set_symbols.py
Then: node tools/build.mjs
"""
import io
import json
import time
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "images" / "symbols"
AGENT = "HoloChase/1.0 (private collection tracker; github.com/miXXed234)"
PCX = "https://pokecardex.b-cdn.net/assets/images/symboles/%s.png"

# Sets whose printed code does not match PokeCardex's filename, checked one by
# one. Everything else resolves through src/set_codes.json.
OVERRIDES = {
    "sm3.5": "SLE",   # Shining Legends
    "sm7.5": "SM75",  # Dragon Majesty
    "mfb": "MFB23",   # My First Battle
}


# Sets PokeCardex draws a badge for that no card actually carries. Base Set
# famously prints no expansion symbol at all (checked against base1-4), and the
# McDonald's cards do not print the "M23"/"M24" PokeCardex shows. Skipped, the
# same way the trainer kits are: a tile must not claim something the card
# doesn't have.
NO_SYMBOL = {"base1", "2023sv", "2024sv"}


def fetch(url, tries=3):
    last = None
    for attempt in range(tries):
        if attempt:
            time.sleep(0.4 * (1 + 2 * attempt))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(req, timeout=45) as resp:
                body = resp.read()
            # An error page is still bytes; anything this small is not an image.
            return body if len(body) > 100 else None
        except Exception as exc:  # noqa: BLE001 - any failure means "try the next candidate"
            last = exc
    if last and getattr(last, "code", None) not in (400, 404):
        print(f"      {url}: {last}")
    return None


def api(path):
    return json.loads(fetch(f"https://api.tcgdex.net/v2/{path}").decode())


def tcgdex_candidates(entry, lang):
    bases = []
    if entry.get("symbol"):
        bases.append(entry["symbol"].replace("/univ/", f"/{lang}/"))
    if entry.get("logo"):
        bases.append(entry["logo"].rsplit("/", 1)[0] + "/symbol")
    return [b + ext for b in dict.fromkeys(bases) for ext in (".webp", ".png")]


def save(data, set_id):
    """Normalised to PNG so the app can index the folder by set id alone."""
    img = Image.open(io.BytesIO(data))
    img = img.convert("RGBA")
    img.save(OUT / f"{set_id}.png", "PNG", optimize=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    codes = json.loads((ROOT / "src" / "set_codes.json").read_text("utf-8"))
    by_code = {}
    for set_id, code in codes.items():
        by_code.setdefault(code, []).append(set_id)

    sets = {"en": api("en/sets"), "ja": api("ja/sets")}
    done, pcx_used, missing = {}, [], []

    for lang, entries in sets.items():
        for entry in entries:
            set_id = entry["id"]
            if (OUT / f"{set_id}.png").exists():
                done[set_id] = "kept"
                continue
            for url in tcgdex_candidates(entry, lang):
                body = fetch(url)
                if body:
                    save(body, set_id)
                    done[set_id] = "tcgdex"
                    break
            if set_id in done:
                continue

            slug = None if set_id in NO_SYMBOL else (OVERRIDES.get(set_id) or codes.get(set_id))
            if slug and ":" not in (slug or ""):
                body = fetch(PCX % slug)
                if body:
                    save(body, set_id)
                    done[set_id] = "pokecardex"
                    pcx_used.append(f"{set_id}={slug}")
                    continue
            missing.append(set_id)

    # A sub-set prints its parent's symbol; its code spells the parent out.
    inherited = []
    for set_id in list(missing):
        code = codes.get(set_id) or ""
        if ":" not in code:
            continue
        for parent in by_code.get(code.split(":")[0], []):
            src = OUT / f"{parent}.png"
            if src.exists():
                (OUT / f"{set_id}.png").write_bytes(src.read_bytes())
                inherited.append(f"{set_id}<-{parent}")
                missing.remove(set_id)
                break

    kinds = {}
    for kind in done.values():
        kinds[kind] = kinds.get(kind, 0) + 1
    print(f"symbols in images/symbols: {len(list(OUT.glob('*.png')))}")
    print(f"  this run: {kinds}")
    print(f"  pokecardex: {' '.join(pcx_used) or '-'}")
    print(f"  inherited:  {' '.join(inherited) or '-'}")
    print(f"  no symbol:  {len(missing)}")


if __name__ == "__main__":
    main()
