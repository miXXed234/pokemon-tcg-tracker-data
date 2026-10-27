"""Downloads the symbol printed on a card, from PokeCardex, for every set.

The set browser can swap its logos for these, because the symbol is what is
actually printed in a card's bottom-left corner -- on the older sets it is the
*only* thing printed there, with no three-letter code next to it.

One source on purpose. An earlier version pulled most of them from TCGdex and
patched the gaps from PokeCardex, which meant three fallbacks, a rewritten url
(TCGdex serves its symbols under a `/univ/` path that answers 400) and two
extensions to try, each of which was somewhere for a bug to sit. Checked before
switching: of the 169 sets that had a symbol from TCGdex, 146 are pixel-wise
the same drawing here and the other 23 are the same symbol drawn at a different
weight. Nothing is lost, 21 gaps are filled, and this file is now a loop.

[SETS] is the mapping, because PokeCardex has its own set keys. It was built
from its set *names* (its overview shows only pictures, but each set page
carries the name in its <title>), never guessed from the file letters -- those
follow the French Pokemon names, so B&W Trainer Kit (Excadrill) is "TK5-M" for
Minotaupe.

Two findings worth keeping:
  Base Set prints no expansion symbol at all. PokeCardex still has a file for
  it, a pokeball placeholder, so it is left out.
  McDonald's ran separate French and international sets some years, with
  different symbols -- 2018 is "MC8" against "MC8US". Ours are the
  international ones.

Sub-sets inherit their parent's file, which is correct: a Trainer Gallery card
carries the parent set's symbol, and its code says so ("LOR:TG").

Japanese symbols live in images/symbols/ja/. They must: `SM12` and `sm12` are
two different sets in two different mounts, and on a case-insensitive
filesystem one file silently overwrites the other -- which is exactly what
happened, handing fourteen international sets the symbol of their Japanese
namesake.

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
SETS = ROOT / "src" / "pokecardex_sets.json"
AGENT = "HoloChase/1.0 (private collection tracker; github.com/miXXed234)"
CDN = "https://pokecardex.b-cdn.net/assets/images/%s/%s.png"


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
            # A miss is an answer, not a hiccup, and retrying it three times
            # with backoff turns a two minute run into ten.
            if exc.code in (400, 404):
                return None
            last = exc
            continue
        except Exception as exc:  # noqa: BLE001 - anything else is worth a retry
            last = exc
            continue
        else:
            return body if len(body) > 100 else None
    if last:
        print(f"      {url}: {last}")
    return None


def save(data, path):
    """Returns False for a blank placeholder, which is not a symbol.

    Drawing one leaves an empty tile with nothing to fall back to, which is
    what PokeCardex's fully transparent Japanese Base Set file used to do.
    """
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    if not any(v > 10 for v in img.getchannel("A").get_flattened_data()):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)
    return True


def main():
    sets = json.loads(SETS.read_text("utf-8"))
    index, missing = {}, []
    for zone, folder, prefix in (("international", "symboles", ""),
                                 ("japanese", "symboles_jp", "ja/")):
        for set_id, slug in sorted(sets[zone].items()):
            body = fetch(CDN % (folder, slug))
            name = f"{prefix}{set_id}.png"
            if body and save(body, OUT / name):
                index[set_id] = name
            else:
                missing.append(set_id)

    # A sub-set prints its parent's symbol -- a Trainer Gallery card carries the
    # parent set's, and its code says so ("LOR:TG"). PokeCardex does not list
    # them separately, so the parent is named outright rather than derived.
    inherited = []
    for set_id, parent in sorted(sets.get("inherit", {}).items()):
        src = OUT / index.get(parent, "")
        if parent in index and src.exists():
            (OUT / f"{set_id}.png").write_bytes(src.read_bytes())
            index[set_id] = f"{set_id}.png"
            inherited.append(f"{set_id}<-{parent}")
        elif set_id not in index:
            missing.append(set_id)

    # Files that are already here but that PokeCardex has no set for stay:
    # Yellow A Alternate's mark came from elsewhere and is still correct.
    kept = []
    for path in sorted(OUT.rglob("*.png")):
        rel = path.relative_to(OUT).as_posix()
        set_id = rel[3:-4] if rel.startswith("ja/") else rel[:-4]
        if set_id not in index:
            index[set_id] = rel
            kept.append(set_id)

    INDEX.write_text(json.dumps(dict(sorted(index.items())), indent=2) + chr(10), "utf-8")
    print(f"  kept      {len(kept)}: {' '.join(kept)}")
    print(f"symbols: {len(index)}")
    print(f"  inherited {len(inherited)}: {' '.join(inherited)}")
    print(f"  no symbol {len(missing)}: {' '.join(sorted(missing))}")


if __name__ == "__main__":
    main()
