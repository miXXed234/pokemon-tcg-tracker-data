"""Downloads the symbol printed on a card into images/symbols/.

The set browser can swap its logos for these, because the symbol is what is
actually printed in a card's bottom-left corner -- on the older sets it is the
*only* thing printed there, with no three-letter code next to it.

Two sources, in this order:

  TCGdex, for the sets it has one for. Its own `symbol` field in the set list
  is served under a `/univ/` path that answers 400 InvalidBucketName, so the
  path is rebuilt with a language segment; and the field is missing for sets
  whose image does exist, so the logo folder is probed as well. Both extensions
  are tried: a good number of sets have only one of them.

  PokeCardex's CDN for the gaps, keyed by the code printed on the card. Only
  where that code is unambiguous -- its own slugs for the older sets are
  inventions (Shining Fates is "SWSH45" there, which no card carries), and the
  trainer kits and the pre-2023 McDonald's sets are left alone rather than
  guessed at: a wrong symbol on a tile is worse than none.

Sub-sets inherit their parent's file, which is correct -- a Trainer Gallery
card carries the parent set's symbol. Their code says so: "LOR:TG".

Japanese sets are handled by jp_from_pokecardex.py and live under
images/symbols/ja/. They must: `SM12` and `sm12` are two different sets, and
on a case-insensitive filesystem one file would quietly overwrite the other.

Run: python tools/set_symbols.py
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
OUT = ROOT / "images" / "symbols"
INDEX = ROOT / "src" / "set_symbols.json"
AGENT = "HoloChase/1.0 (private collection tracker; github.com/miXXed234)"
PCX = "https://pokecardex.b-cdn.net/assets/images/symboles/%s.png"

# Sets whose printed code does not match PokeCardex's filename, checked one by
# one. Everything else resolves through src/set_codes.json.
OVERRIDES = {
    "sm3.5": "SLE",   # Shining Legends
    "sm7.5": "SM75",  # Dragon Majesty
    "mfb": "MFB23",   # My First Battle
}

# Base Set famously prints no expansion symbol at all (checked against
# base1-4), and PokeCardex still draws a pokeball placeholder for it. A tile
# must not claim something the card does not have.
#
# The McDonald's sets were on this list too, on the reasoning that no card
# prints the "M23"/"M24" badge PokeCardex shows. That was wrong: our own logo
# folder carried the identical images from an unrelated earlier source, filed
# as logos, and two independent sources agreeing is what settles it. The
# McDonald's year symbols are real; the evidence against them turned out to be
# a mismatched card scan of our own.
NO_SYMBOL = {"base1"}


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
            # 404 is an answer, not a hiccup: this url is also how a slug guess
            # is tested, and retrying every miss three times with backoff turns
            # a two minute run into ten.
            if exc.code in (400, 404):
                return None
            last = exc
            continue
        except Exception as exc:  # noqa: BLE001 - any other failure is worth a retry
            last = exc
            continue
        else:
            # An error page is still bytes; anything this small is not an image.
            return body if len(body) > 100 else None
    if last:
        print(f"      {url}: {last}")
    return None


def save(data, path):
    """Returns False for a blank placeholder, which is not a symbol.

    A set that prints none still has a file on some sources: PokeCardex's
    Japanese Base Set is a fully transparent 40x40, and drawing it leaves an
    empty tile with nothing to fall back to.
    """
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    if not any(v > 10 for v in img.getchannel("A").get_flattened_data()):
        return False
    img.save(path, "PNG", optimize=True)
    return True


def candidates(entry):
    bases = []
    if entry.get("symbol"):
        bases.append(entry["symbol"].replace("/univ/", "/en/"))
    if entry.get("logo"):
        bases.append(entry["logo"].rsplit("/", 1)[0] + "/symbol")
    return [b + ext for b in dict.fromkeys(bases) for ext in (".webp", ".png")]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    codes = json.loads((ROOT / "src" / "set_codes.json").read_text("utf-8"))
    by_code = {}
    for set_id, code in codes.items():
        by_code.setdefault(code, []).append(set_id)

    index = json.loads(INDEX.read_text("utf-8")) if INDEX.exists() else {}
    sets = json.loads(fetch("https://api.tcgdex.net/v2/en/sets").decode())

    from_tcgdex, from_pcx, missing = [], [], []
    for entry in sets:
        set_id = entry["id"]
        for url in candidates(entry):
            body = fetch(url)
            if body and save(body, OUT / f"{set_id}.png"):
                index[set_id] = f"{set_id}.png"
                from_tcgdex.append(set_id)
                break
        if set_id in from_tcgdex:
            continue

        slug = None if set_id in NO_SYMBOL else (OVERRIDES.get(set_id) or codes.get(set_id))
        if slug and ":" not in slug:
            body = fetch(PCX % slug)
            if body and save(body, OUT / f"{set_id}.png"):
                index[set_id] = f"{set_id}.png"
                from_pcx.append(f"{set_id}={slug}")
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
                index[set_id] = f"{set_id}.png"
                inherited.append(f"{set_id}<-{parent}")
                missing.remove(set_id)
                break

    INDEX.write_text(json.dumps(dict(sorted(index.items())), indent=2) + "\n", "utf-8")
    print(f"international sets: {len(sets)}")
    print(f"  from tcgdex    {len(from_tcgdex)}")
    print(f"  from pokecardex {len(from_pcx)}: {' '.join(from_pcx)}")
    print(f"  inherited      {len(inherited)}: {' '.join(inherited)}")
    print(f"  no symbol      {len(missing)}")


if __name__ == "__main__":
    main()
