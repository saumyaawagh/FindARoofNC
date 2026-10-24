// Priority watchlist (sortable table) and the "Find a county" search box (spec §7.6).
// Both are keyboard-accessible ways to reach every county without using the map.
import {colorForTierName, textOn} from "./palette.js";
import {formatScore} from "./format.js";

const COLUMNS = [
  {key: "rank", label: "Rank", numeric: true, ascending: true},
  {key: "name", label: "County", ascending: true},
  {key: "score", label: "Score", numeric: true},
  {key: "tier", label: "Tier", sortBy: "score"},
  {key: "momentum", label: "Momentum", numeric: true},
  {key: "driver", label: "Top driver", ascending: true},
  {key: "coverage", label: "Data", numeric: true}
];
const TOP_N = 15;

// rows: [{fips, name, score, tier, rank, momentum, rising, driver, coverage, partial}]
export function createWatchlist({onSelect, palette = "default"}) {
  const state = {rows: [], selectedId: null, sortKey: "score", descending: true, showAll: false, palette};

  const root = document.createElement("section");
  root.className = "hs-watchlist";
  root.setAttribute("aria-labelledby", "hs-watchlist-title");
  root.innerHTML = `
    <div class="hs-watchlist-head">
      <h2 id="hs-watchlist-title">Priority watchlist</h2>
      <p class="hs-small hs-muted">Click a row (or press Enter on it) to see that county on the map.</p>
    </div>
    <div class="hs-table-wrap"><table><thead><tr></tr></thead><tbody></tbody></table></div>
    <button type="button" class="hs-button hs-showall"></button>`;
  const headRow = root.querySelector("thead tr");
  const body = root.querySelector("tbody");
  const toggle = root.querySelector(".hs-showall");
  toggle.onclick = () => {
    state.showAll = !state.showAll;
    render();
  };

  for (const col of COLUMNS) {
    const th = document.createElement("th");
    th.scope = "col";
    th.className = `hs-col-${col.key}`;
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = col.label;
    button.onclick = () => {
      if (state.sortKey === col.key) state.descending = !state.descending;
      else {
        state.sortKey = col.key;
        state.descending = !col.ascending;
      }
      render();
    };
    th.append(button);
    headRow.append(th);
  }

  function sorted() {
    const col = COLUMNS.find((c) => c.key === state.sortKey);
    const key = col.sortBy ?? col.key;
    const dir = state.descending ? -1 : 1;
    return [...state.rows].sort((a, b) => {
      const x = a[key];
      const y = b[key];
      if (x == null) return 1;
      if (y == null) return -1;
      return (typeof x === "string" ? x.localeCompare(y) : x - y) * dir || a.rank - b.rank;
    });
  }

  function render() {
    headRow.querySelectorAll("th").forEach((th, i) => {
      const active = COLUMNS[i].key === state.sortKey;
      th.setAttribute("aria-sort", active ? (state.descending ? "descending" : "ascending") : "none");
      th.querySelector("button").dataset.arrow = active ? (state.descending ? "▼" : "▲") : "";
    });

    const rows = sorted().slice(0, state.showAll ? undefined : TOP_N);
    body.replaceChildren(...rows.map(rowElement));
    toggle.textContent = state.showAll ? `Show top ${TOP_N} only` : `Show all ${state.rows.length} counties`;
    toggle.setAttribute("aria-expanded", String(state.showAll));
  }

  function rowElement(r) {
    const tr = document.createElement("tr");
    tr.tabIndex = 0;
    tr.dataset.id = r.fips;
    tr.setAttribute("aria-label", `${r.name} County, rank ${r.rank ?? "—"}, score ${formatScore(r.score)}`);
    if (r.fips === state.selectedId) tr.className = "hs-selected";
    const color = colorForTierName(r.tier, state.palette);
    tr.innerHTML = `
      <td class="num hs-col-rank">${r.rank ?? "—"}</td>
      <td class="hs-col-name">${r.name}</td>
      <td class="num hs-col-score"><span class="hs-scorecell">${formatScore(r.score)}<span class="hs-minibar"><span style="width:${r.score ?? 0}%;background:${color}"></span></span></span></td>
      <td class="hs-col-tier"><span class="hs-pill" style="background:${color};color:${textOn(color)}">${r.tier ?? "No data"}</span></td>
      <td class="num hs-col-momentum">${formatScore(r.momentum)}${r.rising ? ` <span class="hs-rising-mark" title="Rising">▲</span>` : ""}</td>
      <td class="hs-col-driver">${r.driver ?? "—"}</td>
      <td class="num hs-col-coverage">${Math.round(r.coverage * 100)}%${r.partial ? ` <span title="Partial data: under 70% of indicator weight available" aria-label="partial data">⚠</span>` : ""}</td>`;
    tr.onclick = () => onSelect(r.fips);
    tr.onkeydown = (e) => {
      if (e.key === "Enter") onSelect(r.fips);
    };
    return tr;
  }

  return {
    element: root,
    update({rows, selectedId, palette}) {
      if (rows) state.rows = rows;
      if (palette) state.palette = palette;
      state.selectedId = selectedId ?? null;
      render();
    }
  };
}

// Type-ahead combobox over county names. Arrow keys move, Enter selects, Esc clears.
export function createSearch({items, onSelect, placeholder = "Find a county…"}) {
  const root = document.createElement("div");
  root.className = "hs-search";
  root.innerHTML = `
    <input type="text" role="combobox" aria-label="Find a county" aria-autocomplete="list"
      aria-expanded="false" aria-controls="hs-search-list" autocomplete="off" placeholder="${placeholder}">
    <ul id="hs-search-list" role="listbox" aria-label="Matching counties" hidden></ul>`;
  const input = root.querySelector("input");
  const list = root.querySelector("ul");
  let matches = [];
  let active = -1;

  function open(show) {
    list.hidden = !show;
    input.setAttribute("aria-expanded", String(show));
  }

  function renderList() {
    list.replaceChildren(...matches.map((item, i) => {
      const li = document.createElement("li");
      li.id = `hs-search-option-${i}`;
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", String(i === active));
      li.textContent = item.name;
      // mousedown (not click) so it fires before the input loses focus
      li.onmousedown = (e) => {
        e.preventDefault();
        choose(item);
      };
      return li;
    }));
    if (active >= 0) input.setAttribute("aria-activedescendant", `hs-search-option-${active}`);
    else input.removeAttribute("aria-activedescendant");
    open(matches.length > 0);
  }

  function choose(item) {
    // Clear the box: the panel and map now show the choice, and a stale name would mislead.
    input.value = "";
    matches = [];
    active = -1;
    open(false);
    onSelect(item.id);
  }

  input.oninput = () => {
    const q = input.value.trim().toLowerCase();
    // Names starting with the text come first, then names containing it.
    matches = q
      ? [...items.filter((d) => d.name.toLowerCase().startsWith(q)),
         ...items.filter((d) => !d.name.toLowerCase().startsWith(q) && d.name.toLowerCase().includes(q))].slice(0, 8)
      : [];
    active = matches.length ? 0 : -1;
    renderList();
  };

  input.onkeydown = (e) => {
    if (e.key === "ArrowDown" && matches.length) {
      e.preventDefault();
      active = (active + 1) % matches.length;
      renderList();
    } else if (e.key === "ArrowUp" && matches.length) {
      e.preventDefault();
      active = (active - 1 + matches.length) % matches.length;
      renderList();
    } else if (e.key === "Enter" && active >= 0) {
      e.preventDefault();
      choose(matches[active]);
    } else if (e.key === "Escape") {
      input.value = "";
      matches = [];
      active = -1;
      renderList();
    }
  };
  input.onblur = () => open(false);

  return root;
}
