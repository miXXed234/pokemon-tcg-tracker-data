"""Japanese set logos for the sets that still have none.

TCGdex serves no logo at all for any of its 186 Japanese sets. PokeCardex keeps
a separate Japanese zone (`/jp/series?zone=jp`, reachable only by clicking the
flag above a list that calls itself international) with one for 236 of them.

Symbols are not this tool's job any more -- set_symbols.py takes those for both
mounts from the same source.

Logos only fill a gap here. Some entries in that zone are the Traditional
Chinese printing -- `S5I` is 一撃大師 where the Japanese booster reads
一撃マスター -- so an existing logo is left alone rather than swapped for one
that might be the wrong edition.

[HAND] covers the families where upper-casing the id does not land on
PokeCardex's slug. The paired sets are the dangerous ones: both sources number
them a/b, but PokeCardex letters them after the name, so our `XY8a` (Blue
Shock) is its `XY8B` while our `XY8b` (Red Flash) is its `XY8R`. Each pair was
read off the logo artwork, because TCGdex's Japanese set *names* are not
trustworthy here: fifteen sets share one name, and `CP5` carries `XY11b`'s.

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

    logo_index = json.loads((ROOT / "src" / "set_logos.json").read_text("utf-8"))
    got_logo = []
    for set_id, slug in sorted(slugs.items()):
        # An existing logo stays: a few entries here are the Chinese edition.
        if set_id in logo_index["logos"]:
            continue
        body = fetch(CDN % ("logos_jp", slug))
        if body:
            name = f"{set_id.replace('+', '_').replace('.', '_')}.png"
            if save(body, LOGOS / name):
                logo_index["logos"][set_id] = name
                got_logo.append(set_id)

    logo_index["logos"] = dict(sorted(logo_index["logos"].items()))
    (ROOT / "src" / "set_logos.json").write_text(
        json.dumps(logo_index, indent=2, ensure_ascii=False) + "\n", "utf-8")

    print(f"japanese sets: {len(sets)}, matched {len(slugs)}")
    print(f"  logos filled    {len(got_logo)}")
    print(f"  unmatched       {sorted(s['id'] for s in sets if s['id'] not in slugs)}")


if __name__ == "__main__":
    main()
