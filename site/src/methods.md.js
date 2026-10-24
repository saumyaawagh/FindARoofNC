// Page loader: builds the Methods page from the repo's METHODS.md (the source of truth)
// plus the pipeline's JSON, so every number on the page comes from the data.
// Framework runs this with Node at build time and uses whatever it prints as the page.
import {readFileSync} from "node:fs";
import {PALETTES, TIER_NAMES} from "./components/palette.js";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf-8");
const methods = read("../../METHODS.md");
const counties = JSON.parse(read("./data/counties.json"));
const sources = JSON.parse(read("./data/sources.json"));
const validation = JSON.parse(read("./data/validation.json"));
const meta = counties.meta;
const sourceName = Object.fromEntries(sources.map((s) => [s.id, s.name]));

// Indicators that exist in this build (optional sources may be missing).
const present = new Set(Object.keys(counties.units[0].indicators));

function weightsTable() {
  const rows = ["| Pillar | Pillar weight | Indicator | Weight inside pillar |", "|---|---|---|---|"];
  for (const [key, pillar] of Object.entries(meta.pillars)) {
    const indicators = Object.entries(meta.indicator_weights).filter(([, w]) => w.pillar === key);
    indicators.forEach(([ind, w], i) => {
      const label = meta.indicator_info[ind].label + (present.has(ind) ? "" : " *(not in this build)*");
      rows.push(`| ${i === 0 ? `**${key}. ${pillar.label}**` : ""} | ${i === 0 ? pillar.weight : ""} | ${label} | ${w.weight} |`);
    });
  }
  return rows.join("\n");
}

function tiersTable() {
  const swatch = (color) => `<span class="hs-swatch-inline" style="background:${color}"></span>`;
  const rows = ["| Score | Tier | Default color | Colorblind-safe color |", "|---|---|---|---|"];
  meta.tiers.forEach((tier, i) => {
    const range = i === meta.tiers.length - 1 ? `${tier.min}–${tier.max}` : `${tier.min} to under ${tier.max}`;
    rows.push(`| ${range} | **${TIER_NAMES[i]}** | ${swatch(PALETTES.default[i])} \`${PALETTES.default[i]}\` | ${swatch(PALETTES.cb[i])} \`${PALETTES.cb[i]}\` |`);
  });
  return rows.join("\n");
}

function sourcesTable() {
  const rows = ["| Source | Publisher | Geography | Data year | Used for | In this build |", "|---|---|---|---|---|---|"];
  for (const s of sources) {
    const name = s.url ? `[${s.name}](${s.url})` : s.name;
    const status = s.status === "used" ? `Yes (retrieved ${s.retrieved})` : "Not included (optional)";
    rows.push(`| ${name} | ${s.publisher} | ${s.geography} | ${s.vintage ?? "—"} | ${s.used_for} | ${status} |`);
  }
  return rows.join("\n");
}

const lowReliability = counties.units.filter((u) => u.low_reliability).map((u) => u.name).sort();
const values = {
  acs_year: meta.acs_year,
  missing_optional: meta.missing_optional_sources.map((id) => sourceName[id] ?? id).join("; ") || "nothing",
  low_reliability_counties: lowReliability.length ? lowReliability.join(", ") : "none",
  stability_sentence: validation.stability.sentence,
  ...Object.fromEntries(Object.entries(meta.data_as_of).map(([k, v]) => [`data_as_of.${k}`, v]))
};
const tables = {weights: weightsTable(), tiers: tiersTable(), sources: sourcesTable()};

let body = methods
  .replace(/^# Methods\n/, "")
  .replace(/^> This file is the source[^\n]*\n/m, "")
  .replace(/<!-- table:(\w+) -->/g, (_, name) => {
    if (!(name in tables)) throw new Error(`METHODS.md asks for unknown table "${name}"`);
    return tables[name];
  })
  .replace(/\{\{([\w.]+)\}\}/g, (_, name) => {
    if (!(name in values)) throw new Error(`METHODS.md uses unknown value {{${name}}}`);
    return values[name];
  });

process.stdout.write(`---
title: Methods
---

# Methods

<div class="hs-prose">

${body}

</div>
`);
