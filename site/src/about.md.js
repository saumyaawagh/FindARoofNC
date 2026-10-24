// Page loader: builds the About page. It has two parts:
//   1. the About text below (purpose, ethics, AI disclosure, roadmap), and
//   2. the Methods section, taken from the repo's METHODS.md (the source of truth) with its
//      tables and numbers filled in from the pipeline's JSON, so they always match the data.
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
  const rows = ["| Score | Tier | Color |", "|---|---|---|"];
  meta.tiers.forEach((tier, i) => {
    const range = i === meta.tiers.length - 1 ? `${tier.min}–${tier.max}` : `${tier.min} to under ${tier.max}`;
    rows.push(`| ${range} | **${TIER_NAMES[i]}** | ${swatch(PALETTES.default[i])} \`${PALETTES.default[i]}\` |`);
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

// METHODS.md becomes one section of this page, so each of its headings moves down a level.
const methodsSection = methods
  .replace(/^# Methods\n/, "")
  .replace(/^> This file is the source[^\n]*\n/m, "")
  .replace(/^## /gm, "### ")
  .replace(/<!-- table:(\w+) -->/g, (_, name) => {
    if (!(name in tables)) throw new Error(`METHODS.md asks for unknown table "${name}"`);
    return tables[name];
  })
  .replace(/\{\{([\w.]+)\}\}/g, (_, name) => {
    if (!(name in values)) throw new Error(`METHODS.md uses unknown value {{${name}}}`);
    return values[name];
  });

process.stdout.write(`---
title: About
---

# About FindARoofNC

<div class="hs-prose">

## Purpose

FindARoofNC is an early-warning map of **housing-loss pressure** across North Carolina's 100 counties, with a neighborhood-level view of Durham County. It is built for county **social services departments and local governments** deciding where to focus eviction prevention, rental assistance and outreach, ideally *before* a lost home turns into homelessness.

## What it is, and what it isn't

**FindARoofNC shows where housing-loss pressure is building. It does not identify individuals and does not predict whether any specific household will become homeless.**

- It **is** a relative ranking of places, built from public, aggregated data and updated when new data is published.
- It **isn't** a list of people, a risk score for households, or a forecast of homelessness counts.

## Ethics

- **Aggregated public data only.** Every number describes a whole county or census tract. No individual or household data is used.
- **Race is not an input.** CDC's racial and ethnic minority theme is deliberately excluded (see [What's left out, and why](#whats-left-out-and-why)).
- **Careful wording.** The highest tier is called "Priority", meaning a place to look first, not "dangerous" or "bad".
- **Honest about limits.** Missing data is shown as missing, small counties carry a "Low reliability" badge, and the [Validation](#validation) notes below report how stable the ranking is when the weights change.

## AI disclosure

- **Code:** written with Claude Code under the student's direction. The student reviewed and tested it.
- **Briefs:** each county and tract brief is meant to be written with the Claude API from computed numbers only. The prevention actions come from a fixed list chosen by the code, and every number in a brief is checked automatically against the facts. When the API isn't used, the brief is a template built only from the numbers.
- **Prompt:** the exact prompt is in the repository at \`pipeline/prompts/brief_prompt.txt\`.

## Methods

${methodsSection}

## Roadmap

Ideas for later versions, not part of this build:

- Comparing two counties side by side
- Congressional district overlay
- Print to PDF
- Backtesting the index against past years
- 60-day outlook
- Shelter capacity gap
- Hurricane Helene recovery overlay
- Spanish-language version
- Directory of local resources
- Live chat
- Automatic data refresh

## Credits

Data sources are listed under [Sources](#sources) above. Basemap © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors © [CARTO](https://carto.com/attributions).

</div>
`);
