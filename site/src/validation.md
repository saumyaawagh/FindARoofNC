---
title: Validation
---

```js
import {colorForTierName} from "./components/palette.js";
const validation = FileAttachment("data/validation.json").json();
```

# Validation

<div class="hs-prose">

<p class="hs-lede">These checks compare the HomeSignal score with homelessness counts gathered by other agencies, which the index never uses as inputs. If the index points at the right places, counties with higher scores should tend to have more people experiencing homelessness. A relationship here is a sanity check, not proof: correlation does not show that the index predicts homelessness.</p>

</div>

```js
// Draws one comparison card. If the optional data isn't in this build, says so instead.
function comparisonCard({title, part, xLabel, yLabel, note, labelPoints = false}) {
  if (part.status === "missing-optional" || !part.points.length) {
    return html`<section class="hs-card">
      <h2>${title}</h2>
      <p class="hs-unavailable">Data not available in this build.</p>
      <p class="hs-small hs-muted">${note}</p>
    </section>`;
  }
  const chart = Plot.plot({
    width: 520,
    height: 320,
    marginLeft: 48,
    x: {label: xLabel, domain: [0, 100]},
    y: {label: yLabel, grid: true},
    color: {type: "identity"},
    marks: [
      Plot.linearRegressionY(part.points, {x: "x", y: "y", stroke: "#94A3B8", ci: 0}),
      Plot.dot(part.points, {x: "x", y: "y", r: 4, fill: (d) => colorForTierName(d.tier), stroke: "#FFFFFF", tip: true, title: (d) => `${d.name}\n${xLabel}: ${d.x.toFixed(0)}\n${yLabel}: ${d.y.toFixed(1)}`}),
      labelPoints ? Plot.text(part.points, {x: "x", y: "y", text: "name", dy: -10, fontSize: 10}) : null
    ]
  });
  return html`<section class="hs-card">
    <h2>${title}</h2>
    <p class="hs-rho num">Spearman ρ = ${part.rho.toFixed(2)} <span class="hs-muted">(n = ${part.n})</span></p>
    <p>${part.interpretation}.</p>
    ${chart}
    <p class="hs-small hs-muted">${note}</p>
  </section>`;
}
```

```js
const stability = validation.stability;
```

<div class="hs-cards">

${comparisonCard({
  title: "Students experiencing homelessness",
  part: validation.student,
  xLabel: "County HomeSignal score",
  yLabel: "Students experiencing homelessness per 1,000 children",
  note: "Source when included: U.S. Department of Education, ED Data Express (EDFacts file 118), school districts mapped to counties."
})}

${comparisonCard({
  title: "Point-in-Time homelessness counts",
  part: validation.pit,
  xLabel: "Population-weighted mean county score in the CoC",
  yLabel: "People counted per 10,000 residents",
  note: "Source when included: HUD Point-in-Time counts by Continuum of Care (CoC). Only 12 data points; treat as a rough check.",
  labelPoints: true
})}

<section class="hs-card">
  <h2>Weight stability</h2>
  <p class="hs-rho num">${stability.median_top10_overlap} of 10</p>
  <p>${stability.sentence}</p>
  <p class="hs-small hs-muted">Each of the five pillar weights was multiplied by a random factor between ${1 - stability.weight_shift} and ${1 + stability.weight_shift}, ${stability.runs} times, with a fixed random seed (${stability.seed}) so the result is the same every time. A high number means the top of the list doesn't depend on the exact weights chosen.</p>
</section>

<section class="hs-card">
  <h2>What this does and doesn't show</h2>
  <ul>
    <li>It <strong>does</strong> show whether the index lines up with independent counts of homelessness, and whether its top counties hold up when the weights shift a little.</li>
    <li>It <strong>doesn't</strong> show that the index predicts homelessness for any place or any household.</li>
    <li>Homelessness counts measure the end point. HomeSignal measures pressure earlier on, so the two shouldn't match perfectly.</li>
    <li>School districts and Continuums of Care don't follow county borders exactly, so these comparisons are approximate.</li>
    <li>Correlations are described only as weak, modest, moderate or strong, using fixed cut-offs (see Methods).</li>
  </ul>
</section>

</div>
