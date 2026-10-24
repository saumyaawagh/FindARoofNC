---
title: Map
---

```js
import {createMap} from "./components/map.js";
import {renderPanel} from "./components/panel.js";
import {createWatchlist, createSearch} from "./components/watchlist.js";
import {computeScores, checkParity} from "./components/scoring.js";
import {TIER_NAMES, colorForTierName, textOn} from "./components/palette.js";
import {formatScore} from "./components/format.js";
import {createWeights, createModeToggle} from "./components/controls.js";
import {downloadCSV} from "./components/csv.js";
```

```js
const countyData = FileAttachment("data/counties.json").json();
const tractData = FileAttachment("data/durham_tracts.json").json();
const countyShapes = FileAttachment("data/nc_counties.geojson").json();
const tractShapes = FileAttachment("data/durham_tracts.geojson").json();
const sourceList = FileAttachment("data/sources.json").json();
const briefs = FileAttachment("data/briefs.json").json();
```

```js
const DURHAM = "37063";
const meta = countyData.meta;
const sources = new Map(sourceList.map((s) => [s.id, s]));
const countyByFips = new Map(countyData.units.map((u) => [u.fips, u]));
const tractByGeoid = new Map(tractData.units.map((u) => [u.geoid, u]));

// In development, make sure the browser's scoring matches Python's exactly.
if (["localhost", "127.0.0.1"].includes(location.hostname)) {
  checkParity(countyData.units, meta);
  checkParity(tractData.units, tractData.meta);
}
```

```js
// What's selected (a county FIPS or a Durham tract GEOID) and which map view is showing.
// The map, KPI card, watchlist, search box and panel all read and set these.
const selectedId = Mutable(null);
// (Named mapView, not view: `view` is a Framework built-in.)
const mapView = Mutable("state");
const select = (id) => (selectedId.value = id);
const currentSelection = () => selectedId.value;
const setView = (v) => (mapView.value = v);
```

```js
// Controls, built once. Their current values are read reactively in the next cell.
const weightsControl = createWeights(meta.pillars);
const modeToggle = createModeToggle();
```

```js
const weights = Generators.input(weightsControl.input); // {A: 30, B: 25, ...}
const mode = Generators.input(modeToggle); // "overall" | "momentum"
const palette = "default"; // the colorblind palette option was removed from the page
```

```js
// The only math in the browser: re-weight the pillar scores (scoring.js).
const countyScores = computeScores(countyData.units, weights);
const tractScores = computeScores(tractData.units, weights);
const ranked = countyData.units
  .map((u) => ({...u, ...countyScores.get(u.fips)}))
  .sort((a, b) => a.rank - b.rank);
const scoredTractCount = [...tractScores.values()].filter((s) => s.score != null).length;
```

```js
const mapEl = html`<div class="hs-map" role="region" aria-label="Map of North Carolina counties colored by Risk Score"></div>`;
```

```js
// Built once. It only depends on static files, so it never re-runs when scores change.
const hsMap = createMap(mapEl, {countyShapes, tractShapes, invalidation});
```

```js
// Move the map to a county chosen from the watchlist, search box, KPI card or chips.
function focusCounty(id) {
  if (id === DURHAM) {
    hsMap.flyToDurham();
  } else {
    if (hsMap.view === "durham") hsMap.resetView();
    hsMap.select(id, {zoom: true});
  }
  select(id);
}

hsMap.onSelect((id) => {
  // Clicking Durham County opens the tract drill-down.
  if (id === DURHAM && hsMap.view !== "durham") hsMap.flyToDurham();
  // Clicking another county while in Durham view goes back to the state view.
  else if (id.length === 5 && id !== DURHAM && hsMap.view === "durham") hsMap.resetView();
  select(id);
});

hsMap.onViewChange((v) => {
  setView(v);
  // Durham County's own detail shows until a tract is clicked; leaving drops the tract.
  const current = currentSelection();
  if (v === "durham" && (!current || current.length === 5)) select(DURHAM);
  if (v === "state" && current?.length === 11) select(DURHAM);
});
```

```js
hsMap.setCountyScores(new Map(ranked.map((u) => [u.fips, {
  name: u.name,
  score: u.score,
  tier: u.tier,
  rising: u.rising,
  momentum: u.momentum,
  momentum_tier: u.momentum_tier,
  low_reliability: u.low_reliability,
  driver: u.top_drivers[0]?.sentence
}])));

hsMap.setTractScores(new Map(tractData.units.map((u) => {
  const s = tractScores.get(u.geoid);
  return [u.geoid, {
    name: u.name,
    score: s.score,
    tier: s.tier,
    driver: u.top_drivers[0]?.sentence,
    note: s.score == null ? "Not scored: no households live here" : null
  }];
})));
```

```js
hsMap.select(selectedId);
```

```js
hsMap.setMode(mode);
hsMap.setPalette(palette);
modeToggle.setDisabled(mapView === "durham");
```

```js
function kpiCard(label, value, sub = "") {
  return html`<div class="hs-kpi"><div class="hs-kpi-label">${label}</div><div class="hs-kpi-value num">${value}</div><div class="hs-kpi-sub">${sub}</div></div>`;
}

const scored = ranked.filter((u) => u.score != null);
const top = scored[0]; // undefined when every weight is 0
const sortedScores = scored.map((u) => u.score).sort((a, b) => a - b);
const mid = Math.floor(sortedScores.length / 2);
const median = !sortedScores.length ? null
  : sortedScores.length % 2 ? sortedScores[mid] : (sortedScores[mid - 1] + sortedScores[mid]) / 2;

const highestCard = top
  ? html`<button class="hs-kpi hs-kpi-button" aria-label="Select ${top.name} County, the highest score">
      <div class="hs-kpi-label">Highest score</div>
      <div class="hs-kpi-value num">${top.name} ${formatScore(top.score)}</div>
      <div class="hs-kpi-sub">Click to select</div>
    </button>`
  : kpiCard("Highest score", "—");
if (top) highestCard.onclick = () => focusCounty(top.fips);

const kpis = html`<div class="hs-kpis">
  ${kpiCard("Priority counties", scored.filter((u) => u.tier === "Priority").length, "Score 80 or higher")}
  ${kpiCard("Rising", scored.filter((u) => u.rising).length, "Momentum ≥ 75 and score ≥ 40")}
  ${highestCard}
  ${kpiCard("Median score", formatScore(median), "Across all 100 counties")}
</div>`;
```

```js
const search = createSearch({
  items: [...countyByFips.values()].map((u) => ({id: u.fips, name: u.name})).sort((a, b) => a.name.localeCompare(b.name)),
  onSelect: focusCounty
});

const resetButton = html`<button class="hs-button" aria-label="Reset map view to all of North Carolina">Reset view</button>`;
resetButton.onclick = () => {
  hsMap.resetView();
  select(null);
};
```

```js
const watchlist = createWatchlist({onSelect: focusCounty});
```

```js
watchlist.update({
  rows: ranked.map((u) => ({
    fips: u.fips,
    name: u.name,
    score: u.score,
    tier: u.tier,
    rank: u.rank,
    momentum: u.momentum,
    rising: u.rising,
    driver: meta.indicator_info[u.top_drivers[0]?.indicator]?.short,
    coverage: u.coverage,
    partial: u.partial_data
  })),
  selectedId: selectedId?.length === 5 ? selectedId : null,
  palette
});
```

```js
// Empty state of the detail panel (nothing selected).
const DATA_AS_OF_LABELS = {
  unemployment: "Unemployment (BLS)",
  evictions: "Eviction filings (NC courts)",
  foreclosures: "Foreclosure filings (NC courts)",
  acs: "Census ACS 5-year",
  fair_market_rent: "HUD Fair Market Rent",
  svi: "CDC Social Vulnerability Index",
  durham_evictions: "Durham neighborhood evictions"
};

const tierCounts = TIER_NAMES.map((name) => ({name, count: scored.filter((u) => u.tier === name).length}));

const topChips = scored.slice(0, 5).map((u) => {
  const color = colorForTierName(u.tier, palette);
  const chip = html`<button class="hs-chip" aria-label="Select ${u.name} County, score ${formatScore(u.score)}">
    <span class="hs-chip-dot" style="background:${color}"></span>${u.name} <span class="num">${formatScore(u.score)}</span>
  </button>`;
  chip.onclick = () => focusCounty(u.fips);
  return chip;
});

const emptyPanel = html`<div class="hs-panel-inner hs-fade">
  <h2>How to read this map</h2>
  <p class="hs-lede">Each county's color shows its <strong>Risk Score</strong> (0–100), compared with the other NC counties.</p>
  <p class="hs-lede">A higher score means more signs of housing-loss pressure: eviction and foreclosure filings, rent burden, job loss and structural vulnerability.</p>
  <p class="hs-lede">Hover a county for a summary. Click it for details.</p>

  <h3>Counties by tier</h3>
  <div class="hs-tierbar" role="img" aria-label="${tierCounts.map((t) => `${t.name}: ${t.count}`).join(", ")}">
    ${tierCounts.filter((t) => t.count > 0).map((t) => {
      const color = colorForTierName(t.name, palette);
      return html`<div class="hs-tierbar-seg" style="flex:${t.count};background:${color};color:${textOn(color)}" title="${t.name}: ${t.count}">${t.count}</div>`;
    })}
  </div>
  <div class="hs-tierbar-legend">${tierCounts.map((t) => html`<span><span class="hs-chip-dot" style="background:${colorForTierName(t.name, palette)}"></span>${t.name} ${t.count}</span>`)}</div>

  <h3>Highest scores</h3>
  <div class="hs-chips">${topChips}</div>

  <h3>Data as of</h3>
  <dl class="hs-asof">${Object.entries(meta.data_as_of).flatMap(([k, v]) => [html`<dt>${DATA_AS_OF_LABELS[k] ?? k}</dt>`, html`<dd class="num">${v}</dd>`])}</dl>
</div>`;
```

```js
const panel = (() => {
  if (!selectedId) return emptyPanel;
  if (selectedId.length === 11) {
    return renderPanel({
      unit: tractByGeoid.get(selectedId),
      kind: "tract",
      live: tractScores.get(selectedId),
      total: scoredTractCount,
      meta: tractData.meta,
      sources,
      palette,
      brief: briefs[selectedId],
      onBack: () => select(DURHAM)
    });
  }
  return renderPanel({
    unit: countyByFips.get(selectedId),
    kind: "county",
    live: countyScores.get(selectedId),
    total: countyData.units.length,
    meta,
    sources,
    palette,
    brief: briefs[selectedId]
  });
})();
```

```js
// CSV downloads of the scores as currently shown (current weights).
const lensName = Object.values(weights).join("-");
const weightColumns = Object.keys(meta.pillars).map((k) => ({label: `weight_${k}`, value: () => weights[k]}));
const pillarColumns = Object.entries(meta.pillars).map(([k, p]) => ({
  label: `pillar_${k}_${p.label.toLowerCase().replace(/[^a-z]+/g, "_")}`,
  value: (u) => u.pillars[k]?.score
}));
const commonColumns = [
  {label: "score", value: (u) => u.live.score?.toFixed(2)},
  {label: "tier", value: (u) => u.live.tier},
  {label: "rank", value: (u) => u.live.rank},
  ...pillarColumns,
  {label: "coverage", value: (u) => u.coverage},
  {label: "partial_data", value: (u) => u.partial_data},
  {label: "top_driver", value: (u) => u.top_drivers[0]?.sentence}
];

const countyCsv = html`<button class="hs-button" aria-label="Download county scores as CSV">⬇ Counties CSV</button>`;
countyCsv.onclick = () => downloadCSV(`findaroofnc_counties_weights_${lensName}.csv`,
  countyData.units.map((u) => ({...u, live: countyScores.get(u.fips)})).sort((a, b) => (a.live.rank ?? 999) - (b.live.rank ?? 999)),
  [{label: "fips", value: (u) => u.fips}, {label: "county", value: (u) => u.name}, {label: "population", value: (u) => u.population},
   ...commonColumns,
   {label: "momentum", value: (u) => u.momentum}, {label: "momentum_tier", value: (u) => u.momentum_tier},
   {label: "rising", value: (u) => u.live.rising}, {label: "low_reliability", value: (u) => u.low_reliability},
   ...weightColumns]);

const tractCsv = html`<button class="hs-button" aria-label="Download Durham tract scores as CSV">⬇ Durham tracts CSV</button>`;
tractCsv.onclick = () => downloadCSV(`findaroofnc_durham_tracts_weights_${lensName}.csv`,
  tractData.units.map((u) => ({...u, live: tractScores.get(u.geoid)})).sort((a, b) => (a.live.rank ?? 999) - (b.live.rank ?? 999)),
  [{label: "geoid", value: (u) => u.geoid}, {label: "tract", value: (u) => u.name}, {label: "population", value: (u) => u.population},
   ...commonColumns, ...weightColumns]);

const noScores = scored.length === 0;
const zeroNotice = noScores
  ? html`<p class="hs-banner" role="alert">Set at least one weight above 0. The map has no colors until then.</p>`
  : html`<span></span>`;
```

<p class="hs-positioning">FindARoofNC shows where housing-loss pressure is building. It does not identify individuals and does not predict whether any specific household will become homeless.</p>

<div>${kpis}</div>

<div class="hs-controls">
  <div class="hs-controls-group">${modeToggle}${weightsControl.lensSelect}${weightsControl.toggle}</div>
</div>
<div class="hs-controls">
  <div class="hs-controls-left">${search}</div>
  <div class="hs-controls-right">${resetButton}</div>
</div>

<div>${weightsControl.drawer}</div>
<div>${zeroNotice}</div>

<div class="hs-main">
  <div class="hs-map-wrap">${mapEl}</div>
  <aside class="hs-panel" aria-label="Details" aria-live="polite">${panel}</aside>
</div>

<div>${watchlist.element}</div>

<div class="hs-downloads">
  <span class="hs-small hs-muted">Download the scores as shown (current weights):</span>
  ${countyCsv}${tractCsv}
</div>

