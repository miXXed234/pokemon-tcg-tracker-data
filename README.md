# Pokémon TCG Tracker data

Curated catalogue data for the private [Pokémon TCG Tracker](https://github.com/miXXed234/pokemon-tcg-tracker)
Android app: the cards, artwork and set logos that [TCGdex](https://tcgdex.dev)
does not serve.

The app downloads a generated file, `data.json`, and streams the images straight
from this repository. Publishing a correction or a new promo card is a
`git push`, not a new app build.

## Layout

```
data.json              generated, fetched on every app start
sealed.json            generated, ~450 KB, fetched only by the sealed-products screen
src/
  set_logos.json       set id -> logo filename, for both languages
  manual_cards/*.json  curated cards for sets TCGdex only half covers
  promo_seed/*.json    whole sets TCGdex lists but has no cards for
  fallback/            card id -> external image url, for cards with no artwork here
images/
  cards/<cardId>.jpg   artwork, named exactly like the card id
  logos/<file>.png     set logos
  logos/de/<file>.png  german set logos, for sets TCGdex has no german logo for
tools/build.mjs        regenerates data.json
tools/sealed-from-cardmarket.mjs   regenerates sealed.json
```

`sealed.json` is kept out of `data.json` on purpose: it is eight times the size,
and only someone tracking sealed products ever needs it. Like the curated card
prices it comes from Cardmarket's daily download, which needs a login, so both
are refreshed by hand rather than by a worker.

## Making a change

1. Edit or add files under `src/` or `images/`.
2. `node tools/build.mjs`
3. Commit and push.

The app picks it up on its next daily sync, or immediately via
Settings > "Zusatzdaten" > refresh.

Card artwork is indexed from `images/cards/` itself, so adding a picture means
dropping in `<cardId>.jpg` and rebuilding. Nothing to register by hand. The build
fails if `set_logos.json` points at a logo file that isn't there.

## Attribution

Non-commercial fan project, not affiliated with Nintendo, Creatures Inc., GAME
FREAK or The Pokémon Company.

Card images and set logos were collected from [Bulbapedia](https://bulbapedia.bulbagarden.net)
and [PokéWiki](https://www.pokewiki.de), both CC BY-NC-SA, plus a few newer promos
from Limitless and UnownArchives. Pokémon and all card artwork are © Nintendo /
Creatures Inc. / GAME FREAK inc. / The Pokémon Company.
