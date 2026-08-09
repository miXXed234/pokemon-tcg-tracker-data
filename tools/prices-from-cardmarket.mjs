// Fills in prices for the cards we curate ourselves, from Cardmarket's own
// price guide download.
//
//   1. Log in at cardmarket.com and download from .../Pokemon/Data/Download:
//        price_guide_6.json, products_singles_6.json   (6 = Pokémon)
//   2. Drop both in this directory (they are gitignored: Cardmarket hands them
//      to logged-in users, republishing the whole database is another matter)
//   3. node tools/prices-from-cardmarket.mjs
//   4. node tools/build.mjs && git commit
//
// Why this exists: TCGdex carries Cardmarket prices for the cards it knows, and
// the app takes them from there daily. The cards in src/manual_cards are exactly
// the ones TCGdex has no entry for, so they have no price at all and had to be
// typed in by hand.
//
// Matching is by card name within one expansion, because Cardmarket names cards
// after their attacks ("Meganium [Wild Growth | Solar Beam]") and carries no card
// number to join on. That is only trustworthy when it lands on exactly one
// product AND we know of exactly one print: in MEP, two products sharing a name
// differ by 0.32 € against 15.98 €, so a guess is worse than no price at all.
// Everything ambiguous is left alone and stays hand-priced in the app.
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const readJson = (p) => JSON.parse(readFileSync(join(ROOT, p), 'utf8'));

const GUIDE = 'price_guide_6.json';
const CATALOGUE = 'products_singles_6.json';

for (const f of [GUIDE, CATALOGUE]) {
  if (!existsSync(join(ROOT, f))) {
    console.error(`${f} not found. Download it while logged in at cardmarket.com (see header).`);
    process.exit(1);
  }
}

const guideFile = readJson(GUIDE);
const prices = new Map(guideFile.priceGuides.map((g) => [g.idProduct, g]));
const products = readJson(CATALOGUE).products;
const expansions = readJson('src/cardmarket_expansions.json');

/** "Meganium [Wild Growth | Solar Beam]" -> "Meganium" */
const plainName = (name) => name.replace(/\s*\[.*$/, '').trim();

/**
 * Cardmarket splits a card's figures over a plain and a "-holo" set of columns,
 * and which one is filled depends on how the card was printed. Trend is the
 * figure the app already shows for every other card, so prefer it and fall back
 * the same way TCGdex's data source does.
 */
function priceCentsOf(guide) {
  const euros = guide.trend ?? guide.avg ?? guide['trend-holo'] ?? guide['avg-holo'];
  return euros == null ? null : Math.round(euros * 100);
}

let set_ = 0, cleared = 0, ambiguous = 0, unknown = 0, unpriced = 0;

for (const [setId, idExpansion] of Object.entries(expansions)) {
  if (setId.startsWith('_')) continue; // the comment key
  const path = `src/manual_cards/${setId}.json`;
  if (!existsSync(join(ROOT, path))) {
    console.warn(`${setId}: no curated file, skipping`);
    continue;
  }

  const byName = new Map();
  for (const p of products.filter((p) => p.idExpansion === idExpansion)) {
    const key = plainName(p.name);
    byName.set(key, [...(byName.get(key) ?? []), p]);
  }
  if (byName.size === 0) {
    console.warn(`${setId}: expansion ${idExpansion} has no products, check the mapping`);
    continue;
  }

  const cards = readJson(path);
  for (const card of cards) {
    const matches = byName.get(card.name) ?? [];
    // A price we set on an earlier run has to disappear again once the match
    // stops being unambiguous, or a stale figure would outlive its reason.
    const clear = () => card.variants.forEach((v) => {
      if (v.priceCents != null) { delete v.priceCents; cleared++; }
    });

    if (matches.length === 0) { unknown++; clear(); continue; }
    if (matches.length > 1 || card.variants.length !== 1) { ambiguous++; clear(); continue; }

    const cents = priceCentsOf(prices.get(matches[0].idProduct) ?? {});
    if (cents == null) { unpriced++; clear(); continue; } // known card, never sold
    card.variants[0].priceCents = cents;
    set_++;
  }
  writeFileSync(join(ROOT, path), JSON.stringify(cards, null, 2) + '\n');
}

// One date for the whole batch: they all come out of the same daily download,
// and the app shows it as the price's age rather than pretending it is current.
writeFileSync(
  join(ROOT, 'src/prices_meta.json'),
  JSON.stringify({ pricesUpdatedAt: Date.parse(guideFile.createdAt) }, null, 2) + '\n',
);

console.log(`price guide from ${guideFile.createdAt}`);
console.log(`  priced        ${set_}`);
console.log(`  cleared       ${cleared}`);
console.log(`  ambiguous     ${ambiguous}  (several products, or several prints of ours)`);
console.log(`  not on cardmarket ${unknown}`);
console.log(`  no figure yet ${unpriced}`);
console.log('\nrun `node tools/build.mjs` next');
