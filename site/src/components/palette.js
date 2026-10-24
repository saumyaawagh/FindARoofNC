// Tier colors (spec §4.4 step 7). Index 0 = Low ... 4 = Priority.
export const PALETTES = {
  default: ["#1A9850", "#91CF60", "#FEE08B", "#FC8D59", "#D73027"],
  cb: ["#FDE725", "#5EC962", "#21918C", "#3B528B", "#440154"] // viridis: colorblind-safe
};

export const NO_DATA_COLOR = "#CBD5E1";
export const TIER_NAMES = ["Low", "Guarded", "Elevated", "High", "Priority"];
export const TIER_BREAKS = [20, 40, 60, 80];

export function tierIndex(score) {
  if (score == null || Number.isNaN(score)) return null;
  return TIER_BREAKS.filter((b) => score >= b).length;
}

export function tierName(score) {
  const i = tierIndex(score);
  return i == null ? null : TIER_NAMES[i];
}

export function tierColor(score, palette = "default") {
  const i = tierIndex(score);
  return i == null ? NO_DATA_COLOR : PALETTES[palette][i];
}

export function colorForTierName(name, palette = "default") {
  const i = TIER_NAMES.indexOf(name);
  return i < 0 ? NO_DATA_COLOR : PALETTES[palette][i];
}

// MapLibre expression: color by a numeric feature property, grey when it's missing.
export function fillExpression(property, palette = "default") {
  const c = PALETTES[palette];
  return [
    "case",
    ["!", ["has", property]], NO_DATA_COLOR,
    ["step", ["get", property], c[0], 20, c[1], 40, c[2], 60, c[3], 80, c[4]]
  ];
}

// Pick dark or white text, whichever is easier to read on this background (WCAG contrast).
export function textOn(hex) {
  const lum = luminance(hex);
  const dark = luminance("#0F172A");
  const contrastDark = (lum + 0.05) / (dark + 0.05);
  const contrastWhite = 1.05 / (lum + 0.05);
  return contrastDark >= contrastWhite ? "#0F172A" : "#FFFFFF";
}

function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const v = parseInt(hex.slice(i, i + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
