// Builds sealed.json, the catalogue of sealed products the app searches.
//
//   1. Log in at cardmarket.com and download from .../Pokemon/Data/Download:
//        price_guide_6.json, products_nonsingles_6.json   (6 = Pokémon)
//   2. Drop both in this directory (gitignored, same reasoning as the singles)
//   3. node tools/sealed-from-cardmarket.mjs
//   4. git commit
//
// Why this is its own file and not part of data.json: it is ~450 KB against
// data.json's 56, and the app fetches data.json on every start and in the daily
// set-sync worker. Sealed products are wanted by whoever tracks sealed products,
// so they pay for it once when they open that screen, and everyone else never
// downloads it at all.
//
// Unlike the card prices next door there is no matching problem here: a sealed
// product IS a Cardmarket product, so its idProduct is the key and its own name
// is the name. Nothing is guessed.
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const readJson = (p) => JSON.parse(readFileSync(join(ROOT, p), 'utf8'));

const GUIDE = 'price_guide_6.json';
const CATALOGUE = 'products_nonsingles_6.json';

for (const f of [GUIDE, CATALOGUE]) {
  if (!existsSync(join(ROOT, f))) {
    console.error(`${f} not found. Download it while logged in at cardmarket.com (see header).`);
    process.exit(1);
  }
}

// Cardmarket files both of these under "non-singles", but neither is a sealed
// product: 1654 is "buy the whole set as singles" ("Pitch Black: Main Set") and
// 1064 is a seller's random lot. Listing them would offer the user something
// they cannot own as an object.
const NOT_A_PRODUCT = new Set([1064, 1654]);

const guideFile = readJson(GUIDE);
const prices = new Map(guideFile.priceGuides.map((g) => [g.idProduct, g]));

const cents = (v) => (v == null ? null : Math.round(v * 100));

const products = [];
let unpriced = 0;
for (const p of readJson(CATALOGUE).products) {
  if (NOT_A_PRODUCT.has(p.idCategory)) continue;
  const g = prices.get(p.idProduct);
  // Cardmarket reports avg1/avg7/avg30 for singles only; for sealed they are
  // null across the whole file, so they are not carried and the app falls back
  // to trend when one of those bases is selected.
  const trend = cents(g?.trend);
  const avg = cents(g?.avg);
  const low = cents(g?.low);
  if (trend == null && avg == null && low == null) unpriced++;
  products.push({ i: p.idProduct, n: p.name, c: p.idCategory, t: trend, a: avg, l: low });
}
products.sort((a, b) => a.i - b.i);

// The date on Cardmarket's guide, not now: these figures only move when someone
// downloads the file again, so "updated today" would be a lie the moment this
// runs against a guide from last week.
const pricesUpdatedAt = Date.parse(guideFile.createdAt);

const out = { version: 1, pricesUpdatedAt, products };
writeFileSync(join(ROOT, 'sealed.json'), JSON.stringify(out) + '\n');

const byCategory = {};
for (const p of products) byCategory[p.c] = (byCategory[p.c] ?? 0) + 1;
console.log(`sealed.json: ${Math.round(JSON.stringify(out).length / 1024)} KB`);
console.log(`  products   ${products.length} (${unpriced} without any price)`);
console.log(`  guide date ${new Date(pricesUpdatedAt).toISOString().slice(0, 10)}`);
console.log(`  categories ${Object.entries(byCategory).map(([k, v]) => `${k}:${v}`).join(' ')}`);
