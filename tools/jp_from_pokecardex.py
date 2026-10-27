"""Japanese set symbols, and logos for the sets that still have none.

TCGdex barely illustrates its Japanese mount: no logo for any of the 186 sets
and a symbol for four. PokeCardex keeps a separate Japanese zone
(`/jp/series?zone=jp`, reachable only by clicking the flag) with both, for 236
sets, under `symboles_jp/` and `logos_jp/`.

Its slugs are TCGdex's ids in upper case, give or take: `M6a` is `M6A`, `SV-P`
is `SVP`, and `SM1+` is `SM1P`. [HAND] covers the families where that rule
breaks, and every one of those was checked against the logo artwork rather than
against TCGdex's Japanese set *names*, which are not trustworthy here -- fifteen
sets share the name "トリプレットビート", and `CP5` carries the name of `XY11b`.

Two deliberate limits:

  Symbols are taken for every matched set. The expansion symbol is the same
  glyph whatever language the card was printed in, so there is nothing to get
  wrong.

  Logos are only written where we have none. Some entries in PokeCardex's
  Japanese zone are the Traditional Chinese edition -- `S5I` is 一撃大師 where
  the Japanese booster reads 一撃マスター -- so an existing logo is left alone
  rather than swapped for one that might be the wrong edition.

Japanese symbols live in their own folder. They must: `SM12` and `sm12` are two
different sets in two different mounts, and on a case-insensitive filesystem one
file quietly overwrites the other -- which is exactly what happened, handing
fourteen international sets the symbol of their Japanese namesake.

Run: python tools/jp_from_pokecardex.py
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
SYMBOLS = ROOT / "images" / "symbols" / "ja"
INDEX = ROOT / "src" / "set_symbols.json"
LOGOS = ROOT / "images" / "logos"
AGENT = "HoloChase/1.0 (private collection tracker; github.com/miXXed234)"
CDN = "https://pokecardex.b-cdn.net/assets/images/%s/%s.png"

# Where upper-casing the id does not land on PokeCardex's slug. The paired sets
# are the dangerous ones: both sources number them a/b, but PokeCardex letters
# them after the name, so a blind match crosses them over. Each pair below was
# read off the logo artwork.
HAND = {
    "PMCG1": "OR1", "PMCG2": "OR2", "PMCG3": "OR3",
    "PMCG4": "OR4", "PMCG5": "OR5", "PMCG6": "OR6",
    "VS1": "VS", "web1": "PW", "PCG10": "WCP",
    "E1": "ES1", "E2": "ES2", "E3": "ES3", "E4": "ES4", "E5": "ES5",
    "L1a": "L1HG", "L1b": "L1SS",       # HeartGold / SoulSilver Collection
    "XY1a": "XY1B", "XY1b": "XY1R",     # Collection X / Collection Y
    "XY5a": "XY5Y", "XY5b": "XY5G",     # Gaia Volcano / Tidal Storm
    "XY8a": "XY8B", "XY8b": "XY8R",     # Blue Shock / Red Flash
    "XY11a": "XY11P", "XY11b": "XY11B",  # Fever-Burst Fighter / Cruel Traitor
}


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
            return body if len(body) > 100 else None
    if last and getattr(last, "code", None) != 404:
        print(f"      {url}: {last}")
    return None


def save(data, path):
    """Returns False for a blank placeholder, which is not a symbol.

    A set that prints none still has a file here: the Japanese Base Set
    (PMCG1) is a fully transparent 40x40, and drawing it leaves an empty
    tile with nothing to fall back to.
    """
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    if not any(v > 10 for v in img.getchannel("A").get_flattened_data()):
        return False
    img.save(path, "PNG", optimize=True)
    return True


def main():
    sets = json.loads(fetch("https://api.tcgdex.net/v2/ja/sets").decode())
    slugs = {s["id"]: HAND[s["id"]] for s in sets if s["id"] in HAND}
    for s in sets:
        set_id = s["id"]
        if set_id in slugs:
            continue
        # PokeCardex drops the separator and writes "+" as "P": SM1+ -> SM1P.
        upper = set_id.upper()
        for guess in (upper, upper.replace("-", ""), upper.replace("+", "P").replace("-", "")):
            if fetch(CDN % ("symboles_jp", guess)):
                slugs[set_id] = guess
                break

    SYMBOLS.mkdir(parents=True, exist_ok=True)
    symbol_index = json.loads(INDEX.read_text("utf-8")) if INDEX.exists() else {}
    logo_index = json.loads((ROOT / "src" / "set_logos.json").read_text("utf-8"))
    got_symbol, got_logo = [], []
    for set_id, slug in sorted(slugs.items()):
        body = fetch(CDN % ("symboles_jp", slug))
        if body and save(body, SYMBOLS / f"{set_id}.png"):
            symbol_index[set_id] = f"ja/{set_id}.png"
            got_symbol.append(set_id)
        # An existing logo stays: a few entries here are the Chinese edition.
        if set_id in logo_index["logos"]:
            continue
        body = fetch(CDN % ("logos_jp", slug))
        if body:
            name = f"{set_id.replace('+', '_').replace('.', '_')}.png"
            if save(body, LOGOS / name):
                logo_index["logos"][set_id] = name
                got_logo.append(set_id)

    INDEX.write_text(json.dumps(dict(sorted(symbol_index.items())), indent=2) + chr(10), "utf-8")
    logo_index["logos"] = dict(sorted(logo_index["logos"].items()))
    (ROOT / "src" / "set_logos.json").write_text(
        json.dumps(logo_index, indent=2, ensure_ascii=False) + "\n", "utf-8")

    print(f"japanese sets: {len(sets)}, matched {len(slugs)}")
    print(f"  symbols written {len(got_symbol)}")
    print(f"  logos filled    {len(got_logo)}")
    print(f"  unmatched       {sorted(s['id'] for s in sets if s['id'] not in slugs)}")


if __name__ == "__main__":
    main()
