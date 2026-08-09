// Bundles everything under src/ plus an index of images/ into a single data.json,
// the one file the app downloads.
//
// Run after changing anything: `node tools/build.mjs`
//
// The image indexes are read from the directories themselves rather than kept by
// hand, so dropping in a correctly named file is all it takes to publish it --
// the index cannot drift out of sync with the files that actually ship.
import { readFileSync, writeFileSync, readdirSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const readJson = (p) => JSON.parse(readFileSync(join(ROOT, p), 'utf8'));

/** Every `<setId>.json` in a directory, keyed by set id. */
function readSetFiles(dir) {
  const out = {};
  for (const file of readdirSync(join(ROOT, dir)).sort()) {
    if (!file.endsWith('.json')) continue;
    out[file.slice(0, -'.json'.length)] = readJson(join(dir, file));
  }
  return out;
}

const { logos, logosDe } = readJson('src/set_logos.json');

// A logo entry pointing at a missing file would render as a blank tile in the
// app with no hint why, so fail the build instead.
for (const [dir, map] of [['images/logos', logos], ['images/logos/de', logosDe]]) {
  for (const [setId, file] of Object.entries(map)) {
    if (!existsSync(join(ROOT, dir, file))) throw new Error(`${dir}/${file} missing (set ${setId})`);
  }
}

const cardImages = readdirSync(join(ROOT, 'images/cards'))
  .filter((f) => f.endsWith('.jpg'))
  .map((f) => f.slice(0, -'.jpg'.length))
  .sort();

const data = {
  // Bumped only on a breaking shape change; the app refuses a version it
  // doesn't know rather than reading it wrong.
  version: 1,
  // Deliberately no build timestamp: it would rewrite data.json on every run
  // and bury real changes in noise. Git records when, and the app dates the
  // catalogue by when it fetched it, which is what "last updated" means there.
  cardImages,
  setLogos: logos,
  setLogosDe: logosDe,
  fallbackImages: readJson('src/fallback/card_images.json'),
  supplements: readSetFiles('src/manual_cards'),
  seeds: readSetFiles('src/promo_seed'),
};

writeFileSync(join(ROOT, 'data.json'), JSON.stringify(data) + '\n');

const kb = (n) => `${Math.round(n / 1024)} KB`;
console.log(`data.json: ${kb(JSON.stringify(data).length)}`);
console.log(`  card images   ${cardImages.length}`);
console.log(`  set logos     ${Object.keys(logos).length} (+ ${Object.keys(logosDe).length} german)`);
console.log(`  fallback urls ${Object.keys(data.fallbackImages).length}`);
console.log(`  supplements   ${Object.entries(data.supplements).map(([k, v]) => `${k}:${v.length}`).join(' ')}`);
console.log(`  seeds         ${Object.entries(data.seeds).map(([k, v]) => `${k}:${v.length}`).join(' ')}`);
