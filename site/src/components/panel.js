// Detail panel for one county or one Durham tract (spec §7.5).
// Everything shown comes from the pipeline's JSON; the only live numbers are the
// re-weighted score, tier, rank and Rising flag passed in as `live`.
import * as Plot from "npm:@observablehq/plot";
import {html} from "npm:htl";
import {tierColor, colorForTierName, textOn} from "./palette.js";
import {formatScore, formatIndicator, formatMonth} from "./format.js";

const MUTED = "#5B677A"; // matches --muted in style.css

// unit: one entry of counties.json / durham_tracts.json "units"
// kind: "county" | "tract"; live: {score, tier, rank, rising}; total: how many units are ranked
// sources: Map id -> sources.json entry; brief: briefs.json entry or undefined
export function renderPanel({unit, kind, live, total, meta, sources, palette, brief, onBack}) {
  const county = kind === "county";
  const scored = live.score != null;

  return html`<div class="hs-panel-inner hs-fade">
    <div class="hs-panel-header">
      ${onBack ? backButton(onBack) : ""}
      <h2 class="hs-panel-title">${county ? `${unit.name} County` : unit.name}</h2>
      <div class="hs-badges">
        ${pill(live.tier, palette)}
        ${scored ? html`<span class="hs-rank num">Rank ${live.rank} of ${total}</span>` : ""}
        ${live.rising ? html`<span class="hs-chip-rising">▲ Rising</span>` : ""}
        ${unit.low_reliability ? html`<span class="hs-badge" title="Population under 10,000: rates can swing a lot from year to year.">Low reliability</span>` : ""}
        ${unit.partial_data && scored ? html`<span class="hs-badge" title="Less than 70% of the indicator weight has data for this ${county ? "county" : "tract"}.">Partial data</span>` : ""}
      </div>
      ${county ? "" : html`<p class="hs-muted hs-small">Compared with other Durham tracts.</p>`}
    </div>
    ${scored ? scoredBody({unit, county, live, meta, sources, palette, brief}) : unscoredBody(unit)}
  </div>`;
}

function scoredBody({unit, county, live, meta, sources, palette, brief}) {
  const color = tierColor(live.score, palette);
  return html`
    <div class="hs-scoreblock">
      <div>
        <div class="hs-bigscore num">${formatScore(live.score)}</div>
        <div class="hs-small hs-muted">HomeSignal Risk Score (0–100)</div>
      </div>
      ${county ? html`<div class="hs-momentum">
        <div class="hs-small hs-muted">Momentum</div>
        <div class="hs-momentum-value num">${formatScore(unit.momentum)} <span class="hs-small">${unit.momentum_tier}</span></div>
      </div>` : ""}
    </div>
    <div class="hs-scorebar" role="img" aria-label="Score ${formatScore(live.score)} out of 100">
      <div style="width:${live.score}%;background:${color}"></div>
    </div>

    <h3>What makes up the score</h3>
    ${pillarChart(unit, meta, palette)}

    <h3>Top drivers</h3>
    <ul class="hs-drivers">
      ${unit.top_drivers.map((d) => html`<li>${d.sentence} <span class="hs-year">${unit.indicators[d.indicator].vintage}</span></li>`)}
    </ul>

    ${county ? html`<h3>Unemployment rate, last 24 months</h3>${sparkline(unit.unemployment_series)}
      ${unit.unemployment_series.some((p) => p.rate == null) ? html`<p class="hs-small hs-muted">Gap: BLS published no county data for October 2025 (federal shutdown).</p>` : ""}` : ""}

    ${brief ? briefCard(brief) : ""}

    ${indicatorTable(unit, meta, sources)}`;
}

function unscoredBody(unit) {
  const why = unit.population === 0
    ? "No one lives in this tract."
    : "This tract has residents but no households: everyone lives in group quarters such as college dorms.";
  return html`<p class="hs-lede">${why} A housing-loss score for households doesn't apply, so it isn't scored.</p>`;
}

function backButton(onBack) {
  const button = html`<button type="button" class="hs-back">← Durham County</button>`;
  button.onclick = onBack;
  return button;
}

function pill(tier, palette) {
  const color = colorForTierName(tier, palette);
  return html`<span class="hs-pill" style="background:${color};color:${textOn(color)}">${tier ?? "No data"}</span>`;
}

// Five horizontal bars, one per pillar, each colored by its own tier.
function pillarChart(unit, meta, palette) {
  const rows = Object.entries(meta.pillars).map(([key, p]) => ({
    label: p.label,
    score: unit.pillars[key]?.score ?? null
  }));
  const withData = rows.filter((r) => r.score != null);
  const without = rows.filter((r) => r.score == null);
  return Plot.plot({
    width: 360,
    height: 32 * rows.length + 8,
    marginLeft: 160,
    marginRight: 36,
    x: {domain: [0, 100], axis: null},
    y: {domain: rows.map((r) => r.label), label: null, tickSize: 0},
    color: {type: "identity"},
    style: {fontSize: "12px", fontFamily: "Inter, system-ui, sans-serif"},
    ariaLabel: "Pillar scores",
    marks: [
      Plot.barX(rows, {x: 100, y: "label", fill: "#F1F5F9", insetTop: 6, insetBottom: 6}),
      Plot.barX(without, {x: 100, y: "label", fill: "none", stroke: "#94A3B8", strokeDasharray: "4,3", insetTop: 6, insetBottom: 6}),
      Plot.barX(withData, {x: "score", y: "label", fill: (r) => tierColor(r.score, palette), insetTop: 6, insetBottom: 6}),
      Plot.text(withData, {x: "score", y: "label", text: (r) => formatScore(r.score), dx: 4, textAnchor: "start", fill: "#0F172A"}),
      Plot.text(without, {x: 50, y: "label", text: () => "No data", fill: MUTED})
    ]
  });
}

// 24-month line with only the first and last month labeled; the last point is marked.
function sparkline(series) {
  const points = series.map((p) => ({date: new Date(`${p.month}-01T00:00:00Z`), month: p.month, rate: p.rate}));
  const last = [...points].reverse().find((p) => p.rate != null);
  return Plot.plot({
    width: 360,
    height: 90,
    marginLeft: 28, // room for the centered first-month label
    marginRight: 40,
    marginTop: 12,
    x: {ticks: [points[0].date, points.at(-1).date], tickFormat: (d) => formatMonth(d.toISOString().slice(0, 7)), label: null},
    y: {axis: null, zero: false},
    style: {fontSize: "11px", fontFamily: "Inter, system-ui, sans-serif", color: MUTED},
    ariaLabel: `Unemployment rate, latest ${last.rate}% in ${formatMonth(last.month)}`,
    marks: [
      Plot.lineY(points, {x: "date", y: "rate", stroke: "#2563EB", strokeWidth: 1.75}),
      Plot.dot([last], {x: "date", y: "rate", fill: "#2563EB", r: 3}),
      Plot.text([last], {x: "date", y: "rate", text: (p) => `${p.rate}%`, dx: 6, textAnchor: "start", fill: "#0F172A"})
    ]
  });
}

function briefCard(brief) {
  return html`<div class="hs-brief">
    <div class="hs-brief-label">${brief.fallback
      ? "Template brief (no AI) · built only from the numbers above"
      : "AI-generated brief · verify before acting"}</div>
    <p class="hs-brief-headline">${brief.headline}</p>
    <p>${brief.situation}</p>
    ${brief.whats_changed ? html`<p>${brief.whats_changed}</p>` : ""}
    ${brief.actions?.length ? html`<h4>Recommended actions</h4>
      <ul>${brief.actions.map((a) => html`<li><strong>${a.label}.</strong> ${a.why}</li>`)}</ul>` : ""}
    ${brief.caveat ? html`<p class="hs-small hs-muted">${brief.caveat}</p>` : ""}
  </div>`;
}

function indicatorTable(unit, meta, sources) {
  const info = meta.indicator_info;
  const keys = Object.keys(unit.indicators);
  const missing = Object.keys(meta.indicator_weights).filter((k) => !(k in unit.indicators));
  return html`<details class="hs-indicators">
    <summary>All indicators</summary>
    <table>
      <thead><tr><th>Indicator</th><th>Value</th><th title="Share of peers this one is higher than; higher = more pressure">Pctile</th><th>Data year</th></tr></thead>
      <tbody>${keys.map((key) => {
        const ind = unit.indicators[key];
        const src = sources.get(ind.source);
        return html`<tr>
          <td>${info[key].label}<div class="hs-small hs-muted">${src ? html`<a href="${src.url}" target="_blank" rel="noopener">${src.publisher}</a>` : ind.source}</div></td>
          <td class="num">${formatIndicator(ind.value, info[key])}<div class="hs-small hs-muted">${info[key].unit === "%" ? "" : info[key].unit}</div></td>
          <td class="num">${ind.pct == null ? "—" : Math.round(ind.pct)}</td>
          <td class="hs-small">${ind.vintage}</td>
        </tr>`;
      })}</tbody>
    </table>
    ${missing.length ? html`<p class="hs-small hs-muted">Not available ${unit.fips ? "in this build" : "at tract level"}: ${missing.map((k) => info[k].label).join(", ")}. Their weight is shared among the other indicators.</p>` : ""}
  </details>`;
}
