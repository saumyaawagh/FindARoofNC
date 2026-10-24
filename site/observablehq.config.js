// Observable Framework config. Docs: https://observablehq.com/framework/config
import {readFileSync} from "node:fs";

// "Data as of" in the header = the newest month in the data (read at build time).
const meta = JSON.parse(readFileSync(new URL("./src/data/counties.json", import.meta.url), "utf-8")).meta;
const dataAsOf = meta.data_as_of.unemployment;

export default {
  title: "FindARoofNC",
  root: "src",

  // Light theme only, so the demo looks the same on every machine (no dark mode switching).
  theme: "air",
  style: "style.css",

  // We draw our own header nav, so hide Framework's sidebar, table of contents, and footer.
  sidebar: false,
  toc: false,
  pager: false,
  footer: `<div class="hs-footer">
  <p><strong>Aggregated public data only. No individuals are identified.</strong></p>
  <p><a href="./about">About</a> · <a href="./about#methods">Methods</a> · <a href="./about#sources">Sources</a></p>
</div>`,

  head: `<meta name="description" content="FindARoofNC: an early-warning map of housing-loss pressure across North Carolina's 100 counties, with a Durham County neighborhood view. Built from public, aggregated data.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%231A9850'/%3E%3Cstop offset='.5' stop-color='%23FEE08B'/%3E%3Cstop offset='1' stop-color='%23D73027'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='16' height='16' rx='4' fill='url(%23g)'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script type="module">
  // Mark the current page in the header nav (for styling and screen readers).
  addEventListener("DOMContentLoaded", () => {
    // Plain string methods (no regex), since this text lives inside a JS template string.
    let here = location.pathname.split("/").pop();
    if (here.endsWith(".html")) here = here.slice(0, -5);
    if (here === "index") here = "";
    for (const a of document.querySelectorAll(".hs-nav a")) {
      const target = a.getAttribute("href").replace("./", "");
      if (target === here) a.setAttribute("aria-current", "page");
    }
  });
</script>`,

  header: `<div class="hs-header">
  <a class="hs-brand" href="./">
    <span class="hs-logo" aria-hidden="true"></span>
    <span class="hs-title">FindARoofNC</span>
    <span class="hs-tagline">Early-warning map of housing-loss pressure</span>
  </a>
  <div class="hs-header-right">
    <nav class="hs-nav" aria-label="Main">
      <a href="./">Map</a>
      <a href="./about">About</a>
    </nav>
    <span class="hs-asof-badge">Data as of ${dataAsOf}</span>
  </div>
</div>`
};
