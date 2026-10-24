// CSV download of the scores as currently shown (under the current weights).

function cell(value) {
  if (value == null) return "";
  const text = String(value);
  // Quote anything with a comma, quote or line break, doubling inner quotes (RFC 4180).
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function toCSV(rows, columns) {
  const header = columns.map((c) => cell(c.label)).join(",");
  const lines = rows.map((row) => columns.map((c) => cell(c.value(row))).join(","));
  return [header, ...lines].join("\n");
}

export function downloadCSV(filename, rows, columns) {
  const blob = new Blob([toCSV(rows, columns)], {type: "text/csv;charset=utf-8"});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
