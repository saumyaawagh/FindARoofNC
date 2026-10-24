// Number and date formatting used across the site, so every page shows numbers the same way.

export function formatScore(score) {
  return score == null ? "—" : Math.round(score).toString();
}

export function formatNumber(value, decimals = 0) {
  if (value == null) return "—";
  return value.toLocaleString("en-US", {minimumFractionDigits: decimals, maximumFractionDigits: decimals});
}

// "2026-08" -> "Aug 2026"
export function formatMonth(month) {
  const [y, m] = month.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleString("en-US", {month: "short", year: "numeric", timeZone: "UTC"});
}

export function ordinal(n) {
  const v = Math.round(n);
  const suffix = v % 100 >= 11 && v % 100 <= 13 ? "th" : {1: "st", 2: "nd", 3: "rd"}[v % 10] ?? "th";
  return `${v}${suffix}`;
}

// An indicator value as a short string, e.g. "9.8", "+0.4", "4.1%", "85th".
// info = meta.indicator_info[key] from counties.json: {decimals, signed, unit}
export function formatIndicator(value, info) {
  if (value == null) return "—";
  if (info.unit === "percentile") return ordinal(value);
  const text = value.toLocaleString("en-US", {
    minimumFractionDigits: info.decimals,
    maximumFractionDigits: info.decimals,
    signDisplay: info.signed ? "exceptZero" : "auto"
  });
  return info.unit === "%" ? `${text}%` : text;
}
