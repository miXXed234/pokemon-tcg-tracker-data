"""Pulls card images and set logos off pokemontcg.io for sets TCGdex leaves bare.

TCGdex is the better catalogue for us -- it is the only source with German card
and set names -- but it is a volunteer project and a fresh set sometimes arrives
with no artwork at all. The 30th Classic Collection sat there for six weeks with
30 cards and not one picture, and no logo for either 30th set.

pokemontcg.io still publishes card data and artwork (its *prices* are frozen,
which is why it is no use as a catalogue), and its images are the same scans.
This grabs what TCGdex is missing and re-hosts it next to our other artwork, so
nothing in the app has to change: `images/cards/<ourCardId>.jpg` is indexed by
build.mjs exactly like the Bulbapedia scans.

Matching the two catalogues is the whole problem. They number differently:
`30th-c` runs 001-030 while pokemontcg.io keeps each card's *original* print
number, so Charizard is our 001 and their 4. So:

  1. If a card with the same number exists on both sides and the names agree,
     take it. That is the normal case for an ordinary set.
  2. Otherwise match on the name, stripped to letters and digits, because the
     two spell the same card differently ("Genesect EX" vs "Genesect-EX").
     Only a single remaining candidate counts; a name that hits twice (the two
     halves of a LEGEND card) is taken in printing order.
  3. Anything still unmatched needs a line in OVERRIDES naming the counterpart,
     or it is skipped and printed. Never guessed: a wrong picture under a right
     name is worse than a placeholder, and that is exactly the mistake the
     Bulbapedia run made twice.

Spot-check a few pictures after a run. Rule 2 is a heuristic.

Usage:  python tools/images_from_pokemontcgio.py [setId ...]

Idempotent: files already on disk are skipped. Run `node tools/build.mjs`
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
API = "https://api.pokemontcg.io/v2"
TCGDEX = "https://api.tcgdex.net/v2/en/sets"
AGENT = "HoloChase/1.0 (private collection tracker; github.com/miXXed234)"

# Our set id -> theirs.
SETS = {
    "30th": "me55",
    "30th-c": "me55c",
}

# Sets whose logo we want, even when their cards are already pictured. The 30th
# logo is shared by both sets; TCGdex serves none for either.
LOGOS = {"30th", "30th-c"}

# Cards the name rule cannot pair, with the name they carry on the other side.
OVERRIDES = {
    "30th-c-022": "Palkia LV.X",  # TCGdex just calls it "Palkia"
}

CARD_WIDTH = 500   # what the existing card images use
LOGO_WIDTH = 480   # what the newer logos use
PAUSE = 0.4
RETRIES = 5        # the free endpoint throws the odd 500/502


def slug(set_id):
    """The logo filename for a set id, as the existing entries spell it."""
    return re.sub(r"[^a-z0-9]", "_", set_id.lower()) + ".png"


def norm(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def api(url):
    last = None
    for attempt in range(RETRIES):
        time.sleep(PAUSE)
        try:
            return json.loads(fetch(url))
        except Exception as error:  # 500/502 come and go on the free endpoint
            last = error
    raise last


def their_cards(their_id):
    query = urllib.parse.urlencode(
        {"q": f"set.id:{their_id}", "pageSize": 250, "orderBy": "number"}
    )
    return api(f"{API}/cards?{query}")["data"]


def their_set(their_id):
    found = api(f"{API}/sets?{urllib.parse.urlencode({'q': f'id:{their_id}'})}")["data"]
    return found[0] if found else None


def our_cards(set_id):
    return api(f"{TCGDEX}/{urllib.parse.quote(set_id)}").get("cards", [])


def pair_up(ours, theirs):
    """Our card id -> their card, by the three rules in the module docstring."""
    by_number, by_name = {}, {}
    for card in theirs:
        by_number.setdefault(card["number"], []).append(card)
        by_name.setdefault(norm(card["name"]), []).append(card)

    taken, pairs, open_ones = set(), {}, []
    for card in ours:
        local, name = card["localId"], norm(card["name"])

        same_number = [c for c in by_number.get(local.lstrip("0") or "0", [])
                       if c["id"] not in taken and norm(c["name"]) == name]
        if same_number:
            chosen = same_number[0]
        else:
            wanted = OVERRIDES.get(card["id"])
            key = norm(wanted) if wanted else name
            free = [c for c in by_name.get(key, []) if c["id"] not in taken]
            if not free:
                open_ones.append(card)
                continue
            chosen = free[0]  # printing order, which is how LEGEND halves line up

        taken.add(chosen["id"])
        pairs[card["id"]] = chosen
    return pairs, open_ones, [c for c in theirs if c["id"] not in taken]


def save_card(raw, path):
    image = Image.open(BytesIO(raw)).convert("RGB")
    height = round(image.height * CARD_WIDTH / image.width)
    image.resize((CARD_WIDTH, height), Image.LANCZOS).save(path, "JPEG", quality=82, optimize=True)


def save_logo(raw, path):
    image = Image.open(BytesIO(raw)).convert("RGBA")
    width = min(LOGO_WIDTH, image.width)
    height = round(image.height * width / image.width)
    image.resize((width, height), Image.LANCZOS).save(path, "PNG", optimize=True)


def run(set_id, their_id, logos):
    got_logo = 0
    if set_id in LOGOS:
        path = ROOT / "images" / "logos" / slug(set_id)
        if not path.exists():
            remote = (their_set(their_id) or {}).get("images", {}).get("logo")
            if remote:
                save_logo(fetch(remote), path)
                got_logo = 1
        if path.exists():
            logos.setdefault(set_id, slug(set_id))

    # Only the cards TCGdex leaves without a picture. Ours wins over TCGdex in
    # the app, so fetching a card that already has one would swap a working
    # image for an identical one and carry the weight in the repository for
    # nothing -- the first run did exactly that for all 161 cards of `30th`.
    ours = [c for c in our_cards(set_id) if not c.get("image")]
    if not ours:
        print(f"{set_id:8s} logo {'new' if got_logo else 'kept'}, "
              f"no cards to fetch (TCGdex pictures them all)")
        return got_logo, 0

    theirs = their_cards(their_id)
    pairs, open_ours, open_theirs = pair_up(ours, theirs)

    done = 0
    for our_id, card in sorted(pairs.items()):
        path = ROOT / "images" / "cards" / f"{our_id}.jpg"
        if path.exists():
            continue
        url = card.get("images", {}).get("large") or card.get("images", {}).get("small")
        if not url:
            continue
        time.sleep(PAUSE)
        try:
            save_card(fetch(url), path)
        except Exception as error:  # one bad image must not stop the run
            print(f"     ! {our_id}: {error}")
            continue
        done += 1
        if done % 20 == 0:
            print(f"     {set_id} {done}")

    for card in open_ours:
        print(f"     {set_id}: no match for {card['id']} \"{card['name']}\" -- add an OVERRIDE")
    if open_theirs and open_ours:
        print(f"     {set_id}: unused on their side: "
              + ", ".join(f"{c['number']} {c['name']}" for c in open_theirs[:6]))

    state = "new" if got_logo else ("kept" if set_id in logos else "none")
    print(f"{set_id:8s} logo {state}, {done} fetched ({len(pairs)} of {len(ours)} paired)")
    return got_logo, done


def main():
    chosen = sys.argv[1:] or list(SETS)
    unknown = [s for s in chosen if s not in SETS]
    if unknown:
        raise SystemExit(f"unknown set(s): {', '.join(unknown)}")

    logo_file = ROOT / "src" / "set_logos.json"
    catalogue = json.loads(logo_file.read_text(encoding="utf-8"))

    logos = cards = 0
    for set_id in chosen:
        got_logo, got_cards = run(set_id, SETS[set_id], catalogue["logos"])
        logos += got_logo
        cards += got_cards

    # Written back in the order it was read, new sets appended: the file is
    # grouped by hand and re-sorting would bury a two-line change.
    logo_file.write_text(json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n{logos} logos, {cards} card images. Now run: node tools/build.mjs")


if __name__ == "__main__":
    main()
