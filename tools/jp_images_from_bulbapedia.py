"""Pulls Japanese set logos and card scans off Bulbapedia.

TCGdex serves no logo at all for its Japanese mount -- not for one of the 170
sets -- and no card images for the current M series. Bulbapedia has both, under
CC BY-NC-SA, which the app already credits in its settings.

Getting the right picture takes three checks, each of which caught a real
mistake while this was written:

  1. A card file is named "<Card><SetName><Number>.jpg", so the card number is
     read out of the filename instead of guessed from a name, and then checked
     against TCGdex's own card list for the set. A stray upload cannot invent a
     card the set does not have.

  2. Only files carrying the *Japanese* set's name are taken. The same category
     also holds the English counterpart's scans -- Ninja Spinner's category is
     full of "...ChaosRising22.jpg" -- and those are English cards with English
     numbering. A file is dropped when it belongs to more than one expansion.
     Which categories are expansions is read off Bulbapedia (their parent is
     "TCG Expansions") rather than listed here, so a new set pairing needs no
     edit.

  3. The current version of a file may not be the Japanese one. Once a set gets
     its English release, editors overwrite the Japanese scan in place: every
     one of Inferno X's 65 files now holds a Phantasmal Flames card in English,
     uploaded with the comment "English release (source: Pokemon TCG Live)".
     The Japanese original is still there as an older revision, so what gets
     fetched is the newest revision *not* announced as a foreign release.
     Storm Emeralda, whose English release is still months out, has no such
     revision on any of its 104 files -- which is why checks 1 and 2 on their
     own looked like they were working.

Check 3 leans on a comment an editor typed, so spot-check a few pictures after
running this for a set whose English version already exists.

Usage:  python tools/jp_images_from_bulbapedia.py [setId ...]

Idempotent: anything already on disk is skipped, so a re-run fetches only what
is new -- and a set already collected keeps its Japanese scans even after
Bulbapedia has moved on to the English ones. Run `node tools/build.mjs`
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
ARCHIVES = "https://archives.bulbagarden.net/w/api.php"
TCGDEX = "https://api.tcgdex.net/v2/ja/sets"
AGENT = "HoloChase/1.0 (private collection tracker; github.com/miXXed234)"

# Our set id -> the name Bulbapedia files it under. The category name doubles as
# the token in card filenames, minus the spaces.
SETS = {
    "M1S": "Mega Symphonia",
    "M1L": "Mega Brave",
    "M2": "Inferno X",
    "M2a": "MEGA Dream ex",
    "M3": "Nihil Zero",
    "M4": "Ninja Spinner",
    "M5": "Abyss Eye",
    "M6": "Storm Emeralda",
}

CARD_WIDTH = 500                      # what the existing card images use
LOGO_WIDTH = 480                      # what the newer logos use
PAUSE = 0.4                           # nobody is waiting on this, so ask politely
EXPANSION_PARENT = "TCG Expansions"   # what marks a category as a set
FOREIGN_UPLOAD = re.compile(r"\b(english|german|french|italian|spanish|korean|chinese)\b", re.I)


def slug(set_id):
    """The logo filename for a set id, as the existing entries spell it."""
    return re.sub(r"[^a-z0-9]", "_", set_id.lower()) + ".png"


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def api(url):
    time.sleep(PAUSE)
    return json.loads(fetch(url))


def category_files(category):
    """Every file in a category, following continuation."""
    files, cursor = [], None
    while True:
        url = (
            f"{ARCHIVES}?action=query&list=categorymembers"
            f"&cmtitle=Category:{urllib.parse.quote(category)}"
            "&cmnamespace=6&cmlimit=500&format=json"
        )
        if cursor:
            url += "&cmcontinue=" + urllib.parse.quote(cursor)
        data = api(url)
        files += [m["title"][len("File:"):] for m in data.get("query", {}).get("categorymembers", [])]
        cursor = data.get("continue", {}).get("cmcontinue")
        if not cursor:
            return files


def file_categories(titles):
    """The categories each file sits in."""
    out = {}
    for start in range(0, len(titles), 50):
        joined = urllib.parse.quote("|".join("File:" + t for t in titles[start:start + 50]))
        data = api(f"{ARCHIVES}?action=query&titles={joined}&prop=categories&cllimit=500&format=json")
        for page in data["query"]["pages"].values():
            out[page["title"][len("File:"):]] = [
                c["title"][len("Category:"):] for c in page.get("categories", [])
            ]
    return out


def mark_expansions(names, known):
    """Fills `known` with which of these categories are TCG expansions."""
    missing = sorted({n for n in names if n not in known})
    for start in range(0, len(missing), 50):
        joined = urllib.parse.quote("|".join("Category:" + n for n in missing[start:start + 50]))
        data = api(f"{ARCHIVES}?action=query&titles={joined}&prop=categories&cllimit=100&format=json")
        for page in data["query"]["pages"].values():
            name = page["title"][len("Category:"):]
            known[name] = any(
                c["title"][len("Category:"):] == EXPANSION_PARENT for c in page.get("categories", [])
            )
    for name in missing:
        known.setdefault(name, False)
    return known


def japanese_revision_url(title):
    """The newest upload of a file that isn't announced as a foreign release.

    None when every revision is one, which means the Japanese original is gone
    and there is nothing here worth taking.
    """
    data = api(
        f"{ARCHIVES}?action=query&titles={urllib.parse.quote('File:' + title)}"
        "&prop=imageinfo&iiprop=url|comment&iilimit=30&format=json"
    )
    page = list(data["query"]["pages"].values())[0]
    for revision in page.get("imageinfo", []):  # newest first
        if not FOREIGN_UPLOAD.search(revision.get("comment", "")):
            return revision["url"]
    return None


def known_local_ids(set_id):
    """The card numbers TCGdex lists for the set, so we only fetch real ones."""
    data = api(f"{TCGDEX}/{urllib.parse.quote(set_id)}")
    return {int(c["localId"]): c["localId"] for c in data.get("cards", []) if c["localId"].isdigit()}


def save_card(raw, path):
    image = Image.open(BytesIO(raw)).convert("RGB")
    height = round(image.height * CARD_WIDTH / image.width)
    image.resize((CARD_WIDTH, height), Image.LANCZOS).save(path, "JPEG", quality=82, optimize=True)


def save_logo(raw, path):
    image = Image.open(BytesIO(raw)).convert("RGBA")
    width = min(LOGO_WIDTH, image.width)
    height = round(image.height * width / image.width)
    image.resize((width, height), Image.LANCZOS).save(path, "PNG", optimize=True)


def run(set_id, category, logos, expansions):
    files = category_files(category)
    token = category.replace(" ", "")
    pattern = re.compile(rf"^.+{re.escape(token)}(\d{{1,3}})\.(jpg|png)$", re.IGNORECASE)

    # --- the logo -------------------------------------------------------
    logo_path = ROOT / "images" / "logos" / slug(set_id)
    logo_title = f"{set_id} Logo JP.png"
    got_logo = 0
    if logo_title in files and not logo_path.exists():
        url = japanese_revision_url(logo_title)
        if url:
            time.sleep(PAUSE)
            save_logo(fetch(url), logo_path)
            got_logo = 1
    if logo_path.exists():
        logos.setdefault(set_id, slug(set_id))

    # --- which files are this set's own cards ---------------------------
    local_ids = known_local_ids(set_id)
    numbered = {
        name: int(match.group(1))
        for name in files
        if (match := pattern.match(name)) and int(match.group(1)) in local_ids
    }
    categories = file_categories(sorted(numbered)) if numbered else {}
    mark_expansions({c for cats in categories.values() for c in cats}, expansions)

    mine, shared = {}, 0
    for name, number in numbered.items():
        if len([c for c in categories.get(name, []) if expansions.get(c)]) > 1:
            shared += 1
            continue
        mine[name] = number
    if shared:
        print(f"     {set_id}: {shared} file(s) skipped, they belong to another expansion too")

    # --- fetch what we don't have yet -----------------------------------
    todo = {}
    for name, number in sorted(mine.items()):
        path = ROOT / "images" / "cards" / f"{set_id}-{local_ids[number]}.jpg"
        if not path.exists():
            todo[name] = path

    done, foreign = 0, 0
    for name, path in todo.items():
        url = japanese_revision_url(name)
        if not url:
            foreign += 1
            continue
        time.sleep(PAUSE)
        try:
            save_card(fetch(url), path)
        except Exception as error:  # one bad upload must not stop the run
            print(f"     ! {name}: {error}")
            continue
        done += 1
        if done % 20 == 0:
            print(f"     {set_id} {done}/{len(todo)}")

    if foreign:
        print(f"     {set_id}: {foreign} file(s) skipped, only a foreign scan is left of them")
    state = "new" if got_logo else ("kept" if logo_path.exists() else "none")
    print(f"{set_id:4s} logo {state}, {done} fetched ({len(mine)} japanese of {len(local_ids)} in set)")
    return got_logo, done


def main():
    chosen = sys.argv[1:] or list(SETS)
    unknown = [s for s in chosen if s not in SETS]
    if unknown:
        raise SystemExit(f"unknown set(s): {', '.join(unknown)}")

    logo_file = ROOT / "src" / "set_logos.json"
    catalogue = json.loads(logo_file.read_text(encoding="utf-8"))

    expansions, logos, cards = {}, 0, 0
    for set_id in chosen:
        got_logo, got_cards = run(set_id, SETS[set_id], catalogue["logos"], expansions)
        logos += got_logo
        cards += got_cards

    # Written back in the order it was read, new sets appended. The file is
    # grouped by hand rather than sorted, and re-sorting would bury a two-line
    # change in a rewrite of the whole thing.
    logo_file.write_text(json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n{logos} logos, {cards} card images. Now run: node tools/build.mjs")


if __name__ == "__main__":
    main()
