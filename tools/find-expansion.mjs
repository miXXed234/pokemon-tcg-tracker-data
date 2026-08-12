// Suggests the Cardmarket idExpansion for one of our sets, for the mapping in
// src/cardmarket_expansions.json.
//
//   node tools/find-expansion.mjs swshp
//
// Why this exists: Cardmarket's downloads carry no set code and not even an
// expansion name -- only an idExpansion number on each product. Finding the
// right one by hand means grepping the 13 MB catalogue for a card you happen to
// know is in the set and hoping it is not also in three others. There are 770
// expansions in the Pokemon catalogue, so that does not scale.
//
// Instead this compares card *names*: it pulls the set's card list from TCGdex
// and scores every Cardmarket expansion by how much its product names overlap.
// A real match sits near 100% and leaves the runner-up far behind; anything
// close together means the sets genuinely resemble each other and the number
// needs checking by eye before it goes in the mapping.
import { readFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const CATALOGUE = 'products_singles_6.json';

const setId = process.argv[2];
if (!setId) {
  console.error('usage: node tools/find-expansion.mjs <setId>   (e.g. swshp)');
  process.exit(1);
}
if (!existsSync(join(ROOT, CATALOGUE))) {
  console.error(`${CATALOGUE} not found. Download it while logged in at cardmarket.com.`);
  process.exit(1);
}

/**
 * Cardmarket names cards after their attacks ("Meganium [Wild Growth | Solar
 * Beam]"), so the bracket has to go before anything can be compared. Case,
 * punctuation and accents differ between the two sources often enough to be
 * worth flattening too.
 */
const norm = (s) =>
  s
    .replace(/\s*\[[^\]]*\]\s*$/, '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '');

const res = await fetch(`https://api.tcgdex.net/v2/en/sets/${encodeURIComponent(setId)}`);
if (!res.ok) {
  console.error(`TCGdex has no set "${setId}" (HTTP ${res.status})`);
  process.exit(1);
}
const set = await res.json();
const ours = new Set((set.cards ?? []).map((c) => norm(c.name)));
if (ours.size === 0) {
  console.error(`TCGdex lists no cards for "${setId}", so there is nothing to compare.`);
  process.exit(1);
}

const byExpansion = new Map();
for (const p of JSON.parse(readFileSync(join(ROOT, CATALOGUE), 'utf8')).products) {
  if (!byExpansion.has(p.idExpansion)) byExpansion.set(p.idExpansion, new Set());
  byExpansion.get(p.idExpansion).add(norm(p.name));
}

// Two measures, because neither alone is enough. Jaccard keeps a huge expansion
// from winning just by containing everything, but it also punishes the right
// answer: Cardmarket lists 101 products for MEP's 57 card names, since jumbo and
// reprint entries sit alongside the normal ones, which drags a perfect match
// down to 56%. Containment ("how many of ours does it have at all") stays at
// 100% there, so the verdict below asks for both.
const scored = [];
for (const [id, names] of byExpansion) {
  let shared = 0;
  for (const n of ours) if (names.has(n)) shared++;
  if (shared === 0) continue;
  scored.push({
    id,
    size: names.size,
    shared,
    contained: shared / ours.size,
    score: shared / (ours.size + names.size - shared),
  });
}
scored.sort((a, b) => b.score - a.score);

console.log(`${setId}: "${set.name}", ${ours.size} distinct card names at TCGdex\n`);
if (scored.length === 0) {
  console.log('No Cardmarket expansion shares a single name. Wrong set, or Cardmarket');
  console.log('does not carry it.');
  process.exit(0);
}
for (const c of scored.slice(0, 5)) {
  console.log(
    `  idExpansion ${String(c.id).padStart(5)}  overlap ${(c.score * 100).toFixed(0).padStart(3)}%  ` +
      `has ${(c.contained * 100).toFixed(0).padStart(3)}% of our names  ` +
      `(${c.shared} of ${ours.size}, ${c.size} products)`
  );
}
const [best, second] = scored;
console.log();
const clearlyAhead = !second || best.score >= second.score * 1.4;
if (best.contained >= 0.8 && clearlyAhead) {
  console.log(`Looks unambiguous. Add to src/cardmarket_expansions.json:  "${setId}": ${best.id}`);
} else {
  console.log('Too close to call. Open the top candidates in products_singles_6.json and');
  console.log('compare the names by eye before trusting either.');
}
