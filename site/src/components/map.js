// MapLibre wrapper. The map is built ONCE; the page changes it through the methods returned
// by createMap() (new scores, mode, palette, selection, Durham view), so it never flickers.
import maplibregl from "npm:maplibre-gl@5.24.0";
import {PALETTES, NO_DATA_COLOR, TIER_NAMES, fillExpression, colorForTierName, textOn} from "./palette.js";
import {formatScore} from "./format.js";

const CARTO_POSITRON = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";
const OPENFREEMAP_POSITRON = "https://tiles.openfreemap.org/styles/positron";
const NC_BOUNDS = [[-84.33, 33.84], [-75.46, 36.59]];
const DURHAM = "37063";
const INK = "#0F172A";

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const duration = (ms) => (reducedMotion() ? 0 : ms);
const easeInOutCubic = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

export function createMap(container, {countyShapes, tractShapes, invalidation}) {
  const state = {
    view: "state", // "state" (all NC) | "durham" (tract drill-down)
    mode: "overall", // "overall" | "momentum" (counties only)
    palette: "default", // "default" | "cb"
    props: {counties: new Map(), tracts: new Map()},
    selected: {counties: null, tracts: null},
    hovered: {counties: null, tracts: null},
    loaded: false,
    selectHandlers: [],
    viewHandlers: []
  };
  // "points" = one point per county (its center), used for the Rising markers.
  const shapes = {counties: countyShapes, tracts: tractShapes, points: countyPoints(countyShapes)};
  const idField = {counties: "fips", tracts: "geoid", points: "fips"};

  // Plain-HTML overlays drawn on top of the map canvas.
  const tooltip = el("div", "hs-tooltip");
  tooltip.setAttribute("role", "tooltip");
  tooltip.hidden = true;
  const legend = el("div", "hs-legend");
  const breadcrumb = el("nav", "hs-breadcrumb");
  breadcrumb.setAttribute("aria-label", "Map level");
  breadcrumb.hidden = true;
  breadcrumb.innerHTML = `<button type="button" class="hs-crumb-link">North Carolina</button><span aria-hidden="true">›</span><span aria-current="page">Durham County</span>`;
  breadcrumb.querySelector("button").onclick = () => api.resetView();
  container.append(tooltip, legend, breadcrumb);

  const map = new maplibregl.Map({
    container,
    style: CARTO_POSITRON,
    bounds: NC_BOUNDS,
    fitBoundsOptions: {padding: 24},
    maxZoom: 13,
    dragRotate: false,
    pitchWithRotate: false,
    attributionControl: {compact: true}
  });
  map.touchZoomRotate.disableRotation();
  map.keyboard.disableRotation();
  map.addControl(new maplibregl.NavigationControl({showCompass: false}), "top-right");
  invalidation?.then(() => map.remove());

  // Keep all of NC visible and stop users panning far away. Both limits depend on the
  // map's size (a tall phone screen shows much more latitude), so recompute on resize.
  function updateLimits() {
    const camera = {center: map.getCenter(), zoom: map.getZoom()};
    map.setMaxBounds(null);
    const fit = map.cameraForBounds(NC_BOUNDS, {padding: 24});
    const minZoom = Math.min(5.5, fit.zoom);
    map.setMinZoom(minZoom);
    // Max bounds = what's visible with NC fitted at the minimum zoom, plus 10% slack.
    map.jumpTo({center: fit.center, zoom: minZoom});
    const b = map.getBounds();
    const padX = (b.getEast() - b.getWest()) * 0.1;
    const padY = (b.getNorth() - b.getSouth()) * 0.1;
    map.setMaxBounds([[b.getWest() - padX, b.getSouth() - padY], [b.getEast() + padX, b.getNorth() + padY]]);
    map.jumpTo({center: camera.center, zoom: Math.max(camera.zoom, minZoom)});
  }

  const bboxes = new Map(countyShapes.features.map((f) => [f.properties.fips, bbox(f.geometry)]));

  // If Carto's basemap can't be loaded, switch once to OpenFreeMap (both need no API key).
  let usedFallback = false;
  map.on("error", (e) => {
    if (!state.loaded && !usedFallback) {
      usedFallback = true;
      console.warn("Carto basemap failed to load; using OpenFreeMap instead.", e.error?.message);
      map.setStyle(OPENFREEMAP_POSITRON);
    }
  });

  map.once("style.load", () => {
    // Put our layers under the basemap's labels, so place names stay readable on top.
    const firstLabel = map.getStyle().layers.find((l) => l.type === "symbol")?.id;
    const hover = ["boolean", ["feature-state", "hover"], false];
    const selected = ["boolean", ["feature-state", "selected"], false];

    map.addSource("counties", {type: "geojson", data: merged("counties"), promoteId: "fips"});
    map.addLayer({
      id: "county-fill",
      type: "fill",
      source: "counties",
      paint: {
        "fill-color": fillExpression("score", state.palette),
        "fill-opacity": countyOpacity(),
        "fill-opacity-transition": {duration: duration(400)}
      }
    }, firstLabel);
    map.addLayer({
      id: "county-borders",
      type: "line",
      source: "counties",
      paint: {"line-color": "#FFFFFF", "line-width": 0.6}
    }, firstLabel);
    // Dashed outline = low reliability (population under 10,000); the legend explains it.
    map.addLayer({
      id: "county-low-reliability",
      type: "line",
      source: "counties",
      filter: ["==", ["get", "low_reliability"], true],
      paint: {"line-color": INK, "line-width": 1, "line-opacity": 0.55, "line-dasharray": [2, 1.5]}
    }, firstLabel);

    // Durham tracts sit above the counties but start fully transparent.
    map.addSource("tracts", {type: "geojson", data: merged("tracts"), promoteId: "geoid"});
    map.addLayer({
      id: "tract-fill",
      type: "fill",
      source: "tracts",
      paint: {
        "fill-color": fillExpression("score", state.palette),
        "fill-opacity": 0,
        "fill-opacity-transition": {duration: duration(400)}
      }
    }, firstLabel);
    map.addLayer({
      id: "tract-borders",
      type: "line",
      source: "tracts",
      paint: {"line-color": "#FFFFFF", "line-width": 0.4, "line-opacity": 0, "line-opacity-transition": {duration: duration(400)}}
    }, firstLabel);
    map.addLayer({
      id: "tract-highlight",
      type: "line",
      source: "tracts",
      paint: {"line-color": INK, "line-width": ["case", selected, 2.5, hover, 1.5, 0]}
    });

    // Drawn last so the selected county's outline (and Durham's in Durham view) is on top.
    map.addLayer({
      id: "county-highlight",
      type: "line",
      source: "counties",
      paint: {
        "line-color": INK,
        "line-width": ["case", selected, 2.5, ["boolean", ["feature-state", "durham"], false], 2.5, hover, 1.5, 0]
      }
    });

    // ▲ markers on counties flagged Rising; shown only in Momentum view.
    map.addImage("rising", triangleImage(), {pixelRatio: 2});
    map.addSource("county-points", {type: "geojson", data: merged("points", "counties")});
    map.addLayer({
      id: "rising-markers",
      type: "symbol",
      source: "county-points",
      filter: ["==", ["get", "rising"], true],
      layout: {"icon-image": "rising", "icon-allow-overlap": true, "icon-ignore-placement": true, "visibility": "none"}
    });

    state.loaded = true;
    // The page may create the map before its box has a size; fit NC again now that it does.
    map.resize();
    updateLimits();
    map.fitBounds(NC_BOUNDS, {padding: 24, duration: 0});
    applyMode();
    for (const layer of ["counties", "tracts"]) {
      if (state.selected[layer]) setFeatureState(layer, state.selected[layer], {selected: true});
    }
  });
  map.on("resize", updateLimits);
  // Lets us measure "map visible within 3 seconds" (spec §9) from the browser's dev tools.
  map.once("idle", () => performance.mark("hs-map-ready"));

  function countyOpacity() {
    // In Durham view every county fades back so the tracts stand out.
    if (state.view === "durham") return 0.25;
    return ["case", ["boolean", ["feature-state", "hover"], false], 0.95, 0.82];
  }

  // ---- Hover and click -----------------------------------------------------------------
  function setHover(layer, id) {
    if (state.hovered[layer] === id) return;
    if (state.hovered[layer]) setFeatureState(layer, state.hovered[layer], {hover: false});
    state.hovered[layer] = id;
    if (id) setFeatureState(layer, id, {hover: true});
  }

  function clearHover() {
    setHover("counties", null);
    setHover("tracts", null);
    map.getCanvas().style.cursor = "";
    tooltip.hidden = true;
  }

  // One handler for both layers: tracts win inside Durham in Durham view, counties elsewhere.
  map.on("mousemove", (e) => {
    if (!state.loaded) return;
    const layers = state.view === "durham" ? ["tract-fill", "county-fill"] : ["county-fill"];
    const feature = map.queryRenderedFeatures(e.point, {layers})[0];
    if (!feature) return clearHover();
    const layer = feature.layer.id === "tract-fill" ? "tracts" : "counties";
    setHover(layer, feature.properties[idField[layer]]);
    setHover(layer === "tracts" ? "counties" : "tracts", null);
    map.getCanvas().style.cursor = "pointer";
    showTooltip(e.point, feature.properties, layer);
  });
  map.getCanvas().addEventListener("mouseleave", clearHover);

  map.on("click", (e) => {
    if (!state.loaded) return;
    const layers = state.view === "durham" ? ["tract-fill", "county-fill"] : ["county-fill"];
    const feature = map.queryRenderedFeatures(e.point, {layers})[0];
    if (!feature) return;
    const layer = feature.layer.id === "tract-fill" ? "tracts" : "counties";
    const id = feature.properties[idField[layer]];
    state.selectHandlers.forEach((handler) => handler(id, layer === "tracts" ? "tract" : "county"));
  });

  function setFeatureState(layer, id, value) {
    if (state.loaded) map.setFeatureState({source: layer, id}, value);
  }

  function merged(layer, propsFrom = layer) {
    return {
      type: "FeatureCollection",
      features: shapes[layer].features.map((f) => {
        const props = {...f.properties};
        // Leave out missing values entirely, so the map's ["has", ...] check shows "No data".
        for (const [k, v] of Object.entries(state.props[propsFrom].get(f.properties[idField[layer]]) ?? {})) {
          if (v != null) props[k] = v;
        }
        return {...f, properties: props};
      })
    };
  }

  // ---- Tooltip -------------------------------------------------------------------------
  function showTooltip(point, p, layer) {
    const momentum = state.mode === "momentum" && layer === "counties";
    const value = momentum ? p.momentum : p.score;
    const tier = momentum ? p.momentum_tier : p.tier;
    const color = colorForTierName(tier, state.palette);
    tooltip.innerHTML = `
      <div class="hs-tooltip-name">${escape(p.name)}</div>
      <div class="hs-tooltip-row">
        <span class="hs-tooltip-score num">${formatScore(value)}</span>
        <span class="hs-pill" style="background:${color};color:${textOn(color)}">${tier ?? "No data"}</span>
        ${p.rising ? `<span class="hs-chip-rising">▲ Rising</span>` : ""}
      </div>
      <div class="hs-tooltip-label">${momentum ? "Momentum score" : "HomeSignal Risk Score"}</div>
      ${p.driver ? `<div class="hs-tooltip-driver">${escape(p.driver)}</div>` : ""}
      ${p.note ? `<div class="hs-tooltip-note">${escape(p.note)}</div>` : ""}
      ${p.low_reliability ? `<div class="hs-tooltip-note">Low reliability: population under 10,000</div>` : ""}
      <div class="hs-tooltip-hint">Click for details</div>`;
    tooltip.hidden = false;

    // Follow the cursor 12px away, flipping to the other side near the map's edges.
    const pad = 12;
    const {clientWidth: W, clientHeight: H} = container;
    const {offsetWidth: w, offsetHeight: h} = tooltip;
    let x = point.x + pad;
    let y = point.y + pad;
    if (x + w > W - 4) x = point.x - w - pad;
    if (y + h > H - 4) y = point.y - h - pad;
    tooltip.style.transform = `translate(${Math.max(4, x)}px, ${Math.max(4, y)}px)`;
  }

  // ---- Legend --------------------------------------------------------------------------
  function renderLegend() {
    const colors = PALETTES[state.palette];
    const ranges = ["0–20", "20–40", "40–60", "60–80", "80–100"];
    const durham = state.view === "durham";
    const title = state.mode === "momentum" && !durham ? "Momentum (rising pressure)" : "HomeSignal Risk Score";
    legend.innerHTML = `
      <div class="hs-legend-title">${title}</div>
      ${TIER_NAMES.map((name, i) => `
        <div class="hs-legend-row">
          <span class="hs-swatch" style="background:${colors[i]}"></span>
          <span class="hs-legend-name">${name}</span>
          <span class="hs-legend-range num">${ranges[i]}</span>
        </div>`).reverse().join("")}
      ${durham ? `
        <div class="hs-legend-row">
          <span class="hs-swatch" style="background:${NO_DATA_COLOR}"></span>
          <span class="hs-legend-name">No data</span>
          <span class="hs-legend-range"></span>
        </div>` : ""}
      <div class="hs-legend-caption">${durham ? "Relative to Durham County tracts" : "Relative to all 100 NC counties"}</div>
      ${durham ? "" : `<div class="hs-legend-note"><span class="hs-dash"></span>Low reliability (population under 10,000)</div>`}
      ${showRising() ? `<div class="hs-legend-note"><span class="hs-rising-mark">▲</span>Rising: Momentum ≥ 75 and score ≥ 40</div>` : ""}`;
  }

  const showRising = () => state.mode === "momentum" && state.view === "state";

  function applyMode() {
    renderLegend();
    if (!state.loaded) return;
    const property = state.mode === "momentum" ? "momentum" : "score";
    map.setPaintProperty("county-fill", "fill-color", fillExpression(property, state.palette));
    map.setPaintProperty("tract-fill", "fill-color", fillExpression("score", state.palette));
    map.setLayoutProperty("rising-markers", "visibility", showRising() ? "visible" : "none");
  }

  // ---- View changes (statewide <-> Durham) ----------------------------------------------
  function applyView() {
    const durham = state.view === "durham";
    breadcrumb.hidden = !durham;
    renderLegend();
    if (state.loaded) {
      map.setPaintProperty("county-fill", "fill-opacity", countyOpacity());
      map.setPaintProperty("tract-fill", "fill-opacity", durham ? 0.85 : 0);
      map.setPaintProperty("tract-borders", "line-opacity", durham ? 1 : 0);
      setFeatureState("counties", DURHAM, {durham});
      map.setLayoutProperty("rising-markers", "visibility", showRising() ? "visible" : "none");
    }
    state.viewHandlers.forEach((handler) => handler(state.view));
  }

  renderLegend();

  const api = {
    // Map id -> {name, score, tier, momentum, momentum_tier, rising, low_reliability, driver, note}
    setCountyScores(scoresByFips) {
      state.props.counties = scoresByFips;
      if (state.loaded) {
        map.getSource("counties").setData(merged("counties"));
        map.getSource("county-points").setData(merged("points", "counties"));
      }
    },
    setTractScores(scoresByGeoid) {
      state.props.tracts = scoresByGeoid;
      if (state.loaded) map.getSource("tracts").setData(merged("tracts"));
    },
    setMode(mode) {
      state.mode = mode;
      applyMode();
    },
    setPalette(palette) {
      state.palette = palette;
      applyMode();
    },
    // Selects a county (5-digit FIPS) or a Durham tract (11-digit GEOID); null clears both.
    select(id, {zoom = false} = {}) {
      const layer = id && id.length === 11 ? "tracts" : "counties";
      // Only one thing is selected at a time. (Durham's outline in Durham view is separate.)
      for (const l of ["counties", "tracts"]) {
        if (state.selected[l]) setFeatureState(l, state.selected[l], {selected: false});
        state.selected[l] = null;
      }
      if (!id) return;
      state.selected[layer] = id;
      setFeatureState(layer, id, {selected: true});
      if (zoom && layer === "counties" && bboxes.has(id)) {
        map.fitBounds(bboxes.get(id), {padding: 80, maxZoom: 8, duration: duration(800)});
      }
    },
    flyToDurham() {
      if (state.view !== "durham") {
        state.view = "durham";
        applyView();
      }
      map.fitBounds(bboxes.get(DURHAM), {padding: 40, duration: duration(1600), easing: easeInOutCubic});
    },
    resetView() {
      if (state.view !== "state") {
        state.view = "state";
        applyView();
      }
      map.fitBounds(NC_BOUNDS, {padding: 24, duration: duration(800)});
    },
    get view() {
      return state.view;
    },
    onSelect(handler) {
      state.selectHandlers.push(handler);
    },
    onViewChange(handler) {
      state.viewHandlers.push(handler);
    },
    map // exposed for debugging in the browser console only
  };
  return api;
}

function el(tag, className) {
  const node = document.createElement(tag);
  node.className = className;
  return node;
}

function escape(text) {
  return String(text ?? "").replace(/[&<>"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
}

function bbox(geometry) {
  const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
  let [minX, minY, maxX, maxY] = [Infinity, Infinity, -Infinity, -Infinity];
  for (const polygon of polygons) {
    for (const [x, y] of polygon[0]) {
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
    }
  }
  return [[minX, minY], [maxX, maxY]];
}

// One point per county for markers: the area-weighted center of its largest polygon.
function countyPoints(shapes) {
  return {
    type: "FeatureCollection",
    features: shapes.features.map((f) => {
      const polygons = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
      const ring = polygons.map((p) => p[0]).sort((a, b) => Math.abs(ringArea(b)) - Math.abs(ringArea(a)))[0];
      return {type: "Feature", properties: {fips: f.properties.fips}, geometry: {type: "Point", coordinates: ringCentroid(ring)}};
    })
  };
}

function ringArea(ring) {
  let a = 0;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) a += ring[j][0] * ring[i][1] - ring[i][0] * ring[j][1];
  return a / 2;
}

function ringCentroid(ring) {
  let x = 0;
  let y = 0;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const cross = ring[j][0] * ring[i][1] - ring[i][0] * ring[j][1];
    x += (ring[j][0] + ring[i][0]) * cross;
    y += (ring[j][1] + ring[i][1]) * cross;
  }
  const a = ringArea(ring) * 6;
  return [x / a, y / a];
}

// A small dark triangle with a white edge, drawn on a canvas (no font needed).
function triangleImage(size = 28) {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d");
  ctx.beginPath();
  ctx.moveTo(size / 2, 3);
  ctx.lineTo(size - 3, size - 4);
  ctx.lineTo(3, size - 4);
  ctx.closePath();
  ctx.fillStyle = INK;
  ctx.fill();
  ctx.lineWidth = 3;
  ctx.strokeStyle = "#FFFFFF";
  ctx.stroke();
  return ctx.getImageData(0, 0, size, size);
}
