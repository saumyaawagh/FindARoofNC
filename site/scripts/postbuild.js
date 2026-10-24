// Runs automatically after `npm run build` (including in CI).
// Framework hard-codes two things in every page that fail accessibility checks, and has no
// setting for either, so we patch the built HTML:
//   1. <html> has no language, which screen readers need -> add lang="en"
//   2. the viewport tag sets maximum-scale=1, which blocks pinch-zoom on phones -> remove it
import {readdirSync, readFileSync, writeFileSync} from "node:fs";
import {join} from "node:path";

const dist = new URL("../dist/", import.meta.url).pathname;
let patched = 0;
for (const file of readdirSync(dist, {recursive: true})) {
  if (!file.endsWith(".html")) continue;
  const path = join(dist, file);
  const before = readFileSync(path, "utf-8");
  const after = before
    .replace("<html>", '<html lang="en">')
    .replace(", maximum-scale=1", "");
  if (after !== before) {
    writeFileSync(path, after);
    patched++;
  }
}
console.log(`postbuild: patched ${patched} HTML pages (lang="en", pinch-zoom allowed)`);
