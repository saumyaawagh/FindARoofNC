---
title: About
---

```js
const sources = FileAttachment("data/sources.json").json();
```

# About HomeSignal NC

<div class="hs-prose">

## Purpose

HomeSignal NC is an early-warning map of **housing-loss pressure** across North Carolina's 100 counties, with a neighborhood-level view of Durham County. It is built for county **social services departments and local governments** deciding where to focus eviction prevention, rental assistance and outreach, ideally *before* a lost home turns into homelessness.

## What it is, and what it isn't

**HomeSignal shows where housing-loss pressure is building. It does not identify individuals and does not predict whether any specific household will become homeless.**

- It **is** a relative ranking of places, built from public, aggregated data and updated when new data is published.
- It **isn't** a list of people, a risk score for households, or a forecast of homelessness counts.

## Ethics

- **Aggregated public data only.** Every number describes a whole county or census tract. No individual or household data is used.
- **Race is not an input.** CDC's racial and ethnic minority theme is deliberately excluded (see [Methods](./methods)).
- **Careful wording.** The highest tier is called "Priority", meaning a place to look first, not "dangerous" or "bad".
- **Honest about limits.** Missing data is shown as missing, small counties carry a "Low reliability" badge, and the [Validation](./validation) page reports how well the index lines up with independent data, whatever the result.

## AI disclosure

- **Code:** written with Claude Code under the student's direction. The student reviewed and tested it.
- **Briefs:** each county and tract brief is meant to be written with the Claude API from computed numbers only. The prevention actions come from a fixed list chosen by the code, and every number in a brief is checked automatically against the facts. When the API isn't used, the brief is a template built only from the numbers, labelled "Template brief (no AI)" on the map page.
- **Prompt:** the exact prompt is in the repository at `pipeline/prompts/brief_prompt.txt`.

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

## Data credits

</div>

```js
html`<div class="hs-prose"><ul class="hs-credits">${sources.filter((s) => s.status === "used").map((s) => html`<li>${s.url ? html`<a href="${s.url}" target="_blank" rel="noopener">${s.name}</a>` : s.name}, ${s.publisher} <span class="hs-muted">(${s.vintage})</span></li>`)}</ul>
<p class="hs-small hs-muted">Basemap © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions" target="_blank" rel="noopener">CARTO</a>.</p></div>`
```
