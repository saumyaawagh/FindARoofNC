// Map controls (spec §7.7 and P1 features): Overall/Momentum toggle and the pillar-weight
// sliders with preset lenses.
// Each control is a DOM element with a `.value` that fires an "input" event when it changes,
// so the page can read it with Framework's Generators.input(element).

// Pillar weights in the order A–D (Displacement, Cost, Economic, Structural). The Help-seeking
// pillar was removed (no 211 data); each lens is its old setting without that pillar's slider.
export const LENSES = {
  default: {label: "Default", weights: [30, 25, 20, 10]},
  eviction: {label: "Eviction lens", weights: [50, 20, 10, 10]},
  cost: {label: "Cost-burden lens", weights: [20, 45, 15, 10]},
  economic: {label: "Economic-shock lens", weights: [20, 15, 45, 10]},
  balanced: {label: "Balanced", weights: [25, 25, 25, 25]}
};

function emit(target) {
  target.dispatchEvent(new Event("input", {bubbles: false}));
}

// Two-button switch: "Overall" | "Momentum".
export function createModeToggle() {
  const root = document.createElement("div");
  root.className = "hs-segmented-wrap";
  root.innerHTML = `
    <div class="hs-segmented" role="group" aria-label="Map colors show">
      <button type="button" data-value="overall" aria-pressed="true">Overall</button>
      <button type="button" data-value="momentum" aria-pressed="false">Momentum</button>
    </div>
    <span class="hs-hint" hidden>Momentum is available at county level.</span>`;
  const buttons = [...root.querySelectorAll("button")];
  const hint = root.querySelector(".hs-hint");
  root.value = "overall";

  for (const button of buttons) {
    button.onclick = () => {
      if (button.getAttribute("aria-disabled") === "true" || root.value === button.dataset.value) return;
      root.value = button.dataset.value;
      buttons.forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
      emit(root);
    };
  }

  // In Durham view the tracts have no Momentum score, so the switch is turned off.
  root.setDisabled = (disabled) => {
    hint.hidden = !disabled;
    root.title = disabled ? "Momentum is available at county level." : "";
    buttons.forEach((b) => b.setAttribute("aria-disabled", String(disabled)));
  };
  return root;
}

// Shares that always add up to exactly 100% (largest-remainder rounding).
export function normalizedShares(weights) {
  const total = weights.reduce((a, b) => a + b, 0);
  if (total === 0) return weights.map(() => 0);
  const raw = weights.map((w) => (w / total) * 100);
  const shares = raw.map(Math.floor);
  const order = raw.map((r, i) => [r - Math.floor(r), i]).sort((a, b) => b[0] - a[0]);
  const missing = 100 - shares.reduce((a, b) => a + b, 0);
  for (let k = 0; k < missing; k++) shares[order[k][1]] += 1;
  return shares;
}

// Lens dropdown + "Adjust weights" button + slider drawer, all sharing one value:
// {A: 30, B: 25, ...} raw slider values (the scoring normalizes them).
export function createWeights(pillars) {
  const keys = Object.keys(pillars);
  const value = Object.fromEntries(keys.map((k) => [k, pillars[k].weight]));
  const input = document.createElement("div"); // invisible holder for .value + "input" events
  input.value = {...value};

  // Lens dropdown
  const lensWrap = document.createElement("label");
  lensWrap.className = "hs-lens";
  lensWrap.innerHTML = `<span>Lens</span><select aria-label="Weighting lens">
    ${Object.entries(LENSES).map(([id, l]) => `<option value="${id}">${l.label}</option>`).join("")}
    <option value="custom" disabled>Custom</option>
  </select>`;
  const select = lensWrap.querySelector("select");

  // Drawer toggle button
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "hs-button";
  toggle.textContent = "⚙ Adjust weights";
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-controls", "hs-weights-drawer");

  // Drawer with one slider per pillar
  const drawer = document.createElement("section");
  drawer.id = "hs-weights-drawer";
  drawer.className = "hs-drawer";
  drawer.hidden = true;
  drawer.setAttribute("aria-label", "Pillar weights");
  drawer.innerHTML = `
    <div class="hs-drawer-head">
      <h2>Pillar weights</h2>
      <p class="hs-small hs-muted">Each slider sets how much a pillar counts. Percentages show its share of the total.</p>
    </div>
    <div class="hs-sliders">${keys.map((k) => `
      <div class="hs-slider-row">
        <label for="hs-w-${k}">${pillars[k].label}</label>
        <input id="hs-w-${k}" type="range" min="0" max="50" step="5" value="${value[k]}" aria-label="${pillars[k].label} weight">
        <span class="hs-share num" aria-live="polite"></span>
      </div>`).join("")}
    </div>
    <div class="hs-drawer-foot">
      <p class="hs-notice" role="status"></p>
      <button type="button" class="hs-button hs-reset">Reset to default</button>
    </div>`;
  const sliders = Object.fromEntries(keys.map((k) => [k, drawer.querySelector(`#hs-w-${k}`)]));
  const notice = drawer.querySelector(".hs-notice");

  toggle.onclick = () => {
    drawer.hidden = !drawer.hidden;
    toggle.setAttribute("aria-expanded", String(!drawer.hidden));
  };

  function lensFor(weights) {
    const list = keys.map((k) => weights[k]);
    return Object.keys(LENSES).find((id) => LENSES[id].weights.every((w, i) => w === list[i])) ?? "custom";
  }

  function render() {
    const list = keys.map((k) => input.value[k]);
    const shares = normalizedShares(list);
    keys.forEach((k, i) => {
      sliders[k].value = input.value[k];
      drawer.querySelectorAll(".hs-share")[i].textContent = `${input.value[k]} → ${shares[i]}%`;
    });
    const lens = lensFor(input.value);
    select.value = lens;
    const allZero = list.every((w) => w === 0);
    notice.textContent = allZero
      ? "Set at least one weight above 0."
      : lens === "default" ? "" : "Custom weights — scores and ranks recomputed.";
    notice.classList.toggle("hs-notice-warn", allZero);
  }

  function set(weights) {
    input.value = {...weights};
    render();
    emit(input);
  }

  for (const k of keys) {
    sliders[k].oninput = () => set({...input.value, [k]: Number(sliders[k].value)});
  }
  select.onchange = () => {
    const lens = LENSES[select.value];
    if (lens) set(Object.fromEntries(keys.map((k, i) => [k, lens.weights[i]])));
  };
  drawer.querySelector(".hs-reset").onclick = () =>
    set(Object.fromEntries(keys.map((k, i) => [k, LENSES.default.weights[i]])));

  render();
  return {input, lensSelect: lensWrap, toggle, drawer};
}
