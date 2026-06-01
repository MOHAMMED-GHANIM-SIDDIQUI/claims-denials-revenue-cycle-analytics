import fs from "fs/promises";
import path from "path";
import { fileURLToPath, pathToFileURL } from "url";
import { createRequire } from "module";
import Module from "module";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, "..");

const bundledNodeModules =
  "C:\\Users\\ghani\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules";
process.env.NODE_PATH = [
  bundledNodeModules,
  path.join(bundledNodeModules, ".pnpm", "node_modules"),
  process.env.NODE_PATH || "",
]
  .filter(Boolean)
  .join(path.delimiter);
Module._initPaths();

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const { PDFDocument } = require("pdf-lib");
const { marked } = await import(
  pathToFileURL(path.join(bundledNodeModules, "marked", "lib", "marked.esm.js")).href
);

const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const outDir = path.join(rootDir, "reports", "pdf");

const documents = [
  {
    source: "docs/Healthcare_Claims_Intelligence_Project_Blueprint.md",
    html: "Healthcare_Claims_Intelligence_Project_Blueprint.html",
    pdf: "Healthcare_Claims_Intelligence_Project_Blueprint.pdf",
    title: "Healthcare Claims Intelligence & Risk Analytics Platform",
    kicker: "Flagship payer analytics build blueprint",
    subtitle:
      "Claims, members, providers, utilization, HCC/RAF, fraud/waste, readmissions, ML, SQL marts, and executive BI.",
    accent: "#0E7C86",
    secondary: "#155E75",
    audience: "Healthcare Data Analyst | Claims Analyst | Risk Adjustment Analyst | Healthcare BI Analyst",
  },
  {
    source: "docs/Provider_Network_Value_Based_Care_Analytics_Blueprint.md",
    html: "Provider_Network_Value_Based_Care_Analytics_Blueprint.html",
    pdf: "Provider_Network_Value_Based_Care_Analytics_Blueprint.pdf",
    title: "Provider Network Performance & Value-Based Care Analytics Platform",
    kicker: "Provider network and ACO performance blueprint",
    subtitle:
      "Provider peer benchmarking, ACO performance, hospital quality, geographic variation, outlier scoring, and contracting strategy.",
    accent: "#2563EB",
    secondary: "#0F766E",
    audience: "Provider Network Analyst | Value-Based Care Analyst | Population Health Analyst | BI Analyst",
  },
  {
    source: "docs/Claims_Denials_Revenue_Cycle_Analytics_Blueprint.md",
    html: "Claims_Denials_Revenue_Cycle_Analytics_Blueprint.html",
    pdf: "Claims_Denials_Revenue_Cycle_Analytics_Blueprint.pdf",
    title: "Claims Denials, Appeals & Revenue Cycle Intelligence Platform",
    kicker: "Claims operations and revenue cycle blueprint",
    subtitle:
      "Denial benchmarks, appeal workflow, payer friction, claim-level simulation, recovery prioritization, underpayment analytics, and work queues.",
    accent: "#7C3AED",
    secondary: "#0E7490",
    audience: "Claims Analyst | Revenue Cycle Analyst | Insurance Analyst | Healthcare Business Analyst",
  },
];

marked.setOptions({
  gfm: true,
  breaks: false,
  mangle: false,
  headerIds: false,
});

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function stripTags(value) {
  return String(value).replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim();
}

function slugify(value) {
  return stripTags(value)
    .toLowerCase()
    .replace(/&amp;/g, "and")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

function preprocessMarkdown(markdown) {
  return markdown.replace(/```mermaid\s+([\s\S]*?)```/g, (_, code) => {
    return [
      "",
      '<section class="diagram-shell">',
      '<div class="diagram-label">Architecture Diagram</div>',
      `<pre class="mermaid">${escapeHtml(code.trim())}</pre>`,
      "</section>",
      "",
    ].join("\n");
  });
}

function addHeadingIds(html) {
  const toc = [];
  const counts = new Map();
  const withIds = html.replace(/<h([2-3])>([\s\S]*?)<\/h\1>/g, (match, level, inner) => {
    const text = stripTags(inner);
    if (!text) return match;
    const baseSlug = slugify(text) || `section-${toc.length + 1}`;
    const count = counts.get(baseSlug) || 0;
    counts.set(baseSlug, count + 1);
    const id = count ? `${baseSlug}-${count + 1}` : baseSlug;
    toc.push({ level: Number(level), text, id });
    return `<h${level} id="${id}">${inner}</h${level}>`;
  });

  return { html: withIds, toc };
}

function buildToc(toc) {
  const primary = toc.filter((item) => item.level === 2);
  return primary
    .map(
      (item, index) =>
        `<a class="toc-item" href="#${item.id}"><span class="toc-number">${String(
          index + 1
        ).padStart(2, "0")}</span><span>${escapeHtml(item.text)}</span></a>`
    )
    .join("\n");
}

function findSection(toc, keywords) {
  const normalized = keywords.map((keyword) => keyword.toLowerCase());
  const hit = toc
    .filter((item) => item.level === 2)
    .find((item) => normalized.some((keyword) => item.text.toLowerCase().includes(keyword)));
  return hit ? `#${hit.id}` : "#table-of-contents";
}

function buildQuickLinks(toc, compact = false) {
  const links = [
    ["Contents", "#table-of-contents"],
    ["Sources", findSection(toc, ["source", "dataset"])],
    ["Architecture", findSection(toc, ["architecture", "pipeline"])],
    ["SQL", findSection(toc, ["sql"])],
    ["Python", findSection(toc, ["python"])],
    ["ML", findSection(toc, ["machine learning", "ml design"])],
    ["Dashboards", findSection(toc, ["power bi", "dashboard"])],
    ["KPIs", findSection(toc, ["kpi"])],
    ["Roadmap", findSection(toc, ["roadmap", "implementation"])],
  ];

  return links
    .map(
      ([label, href]) =>
        `<a class="${compact ? "nav-chip compact" : "nav-chip"}" href="${href}">${escapeHtml(
          label
        )}</a>`
    )
    .join("");
}

function relatedLinksForSection(sectionText, toc) {
  const text = sectionText.toLowerCase();
  const related = [];
  const add = (label, keywords) => {
    const href = findSection(toc, keywords);
    if (href !== "#table-of-contents" && !related.some((item) => item.href === href)) {
      related.push({ label, href });
    }
  };

  if (text.includes("dataset") || text.includes("source") || text.includes("reference")) {
    add("Map To Architecture", ["architecture", "pipeline"]);
    add("Validate In DQ", ["quality"]);
    add("Use In Roadmap", ["roadmap", "implementation"]);
  } else if (text.includes("architecture") || text.includes("pipeline") || text.includes("data model")) {
    add("Source Register", ["source", "dataset"]);
    add("SQL Build", ["sql"]);
    add("Dashboard Model", ["power bi", "dashboard"]);
  } else if (text.includes("sql")) {
    add("Data Architecture", ["architecture"]);
    add("KPI Dictionary", ["kpi"]);
    add("Power BI", ["power bi", "dashboard"]);
  } else if (text.includes("python") || text.includes("machine learning") || text.includes("ml")) {
    add("Feature Sources", ["architecture", "pipeline"]);
    add("Dashboard Scores", ["power bi", "dashboard"]);
    add("Model Governance", ["quality", "model card"]);
  } else if (text.includes("dashboard") || text.includes("power bi")) {
    add("KPI Dictionary", ["kpi"]);
    add("SQL Marts", ["sql"]);
    add("Executive Story", ["executive", "portfolio"]);
  } else if (text.includes("kpi")) {
    add("SQL Marts", ["sql"]);
    add("Dashboard Spec", ["power bi", "dashboard"]);
    add("Quality Rules", ["quality"]);
  } else {
    add("Sources", ["source", "dataset"]);
    add("Architecture", ["architecture", "pipeline"]);
    add("Roadmap", ["roadmap", "implementation"]);
  }

  return related
    .slice(0, 3)
    .map((item) => `<a class="related-chip" href="${item.href}">${escapeHtml(item.label)}</a>`)
    .join("");
}

function enhanceSections(html, toc) {
  const h2Regex = /<h2 id="([^"]+)">([\s\S]*?)<\/h2>/g;
  const matches = [...html.matchAll(h2Regex)];
  if (!matches.length) return html;

  let enhanced = html.slice(0, matches[0].index);
  const primary = toc.filter((item) => item.level === 2);

  for (let i = 0; i < matches.length; i += 1) {
    const match = matches[i];
    const id = match[1];
    const headingHtml = match[2];
    const headingText = stripTags(headingHtml);
    const contentStart = match.index + match[0].length;
    const contentEnd = i + 1 < matches.length ? matches[i + 1].index : html.length;
    const sectionContent = html.slice(contentStart, contentEnd);
    const previous = i > 0 ? `#${primary[i - 1]?.id}` : "#table-of-contents";
    const next = i + 1 < primary.length ? `#${primary[i + 1]?.id}` : "#table-of-contents";

    enhanced += `
<details class="section-module" open data-section-id="${id}">
  <summary>
    <span class="collapse-indicator">Toggle</span>
    <h2 id="${id}">${headingHtml}</h2>
  </summary>
  <div class="section-body">
    <nav class="section-nav" aria-label="Section navigation">
      <a href="#top">Cover</a>
      <a href="#table-of-contents">Contents</a>
      <a href="${previous}">Previous</a>
      <a href="${next}">Next</a>
    </nav>
    <div class="smart-links">
      <span>Related</span>
      ${relatedLinksForSection(headingText, toc)}
    </div>
    ${sectionContent}
  </div>
</details>`;
  }

  return enhanced;
}

function buildExperiencePage(doc, toc) {
  const architecture = findSection(toc, ["architecture", "pipeline"]);
  const sources = findSection(toc, ["source", "dataset"]);
  const sql = findSection(toc, ["sql"]);
  const ml = findSection(toc, ["machine learning", "ml"]);
  const dashboard = findSection(toc, ["power bi", "dashboard"]);
  const roadmap = findSection(toc, ["roadmap", "implementation"]);

  const flow = [
    ["01", "Sources", sources, "Public reference data and curated source register"],
    ["02", "Warehouse", architecture, "Bronze, silver, gold, mart, and scoring layers"],
    ["03", "SQL Marts", sql, "Governed metrics, scorecards, work queues"],
    ["04", "ML/Scoring", ml, "Predictive and prioritization workflows"],
    ["05", "Dashboards", dashboard, "Executive and operational BI"],
    ["06", "Roadmap", roadmap, "Build order and acceptance criteria"],
  ];

  const bars = [
    ["SQL Architecture", 96, sql],
    ["Healthcare Domain", 94, sources],
    ["BI Storytelling", 90, dashboard],
    ["ML Readiness", 82, ml],
    ["Portfolio Evidence", 88, roadmap],
  ];

  return `
  <section class="experience-page">
    <div class="section-kicker">Interactive Control Center</div>
    <h2 id="interactive-control-center">Executive Navigation Hub</h2>
    <p class="lede">Use the controls below to jump through the PDF. The HTML version also supports collapsible sections, hover states, and quick expand/collapse controls.</p>
    <div class="quick-link-panel">${buildQuickLinks(toc)}</div>

    <div class="visual-grid">
      <article class="visual-card wide">
        <div class="visual-label">Clickable Build Timeline</div>
        <div class="timeline">
          ${flow
            .map(
              ([num, label, href, detail]) => `
              <a class="timeline-step" href="${href}">
                <span>${num}</span>
                <strong>${escapeHtml(label)}</strong>
                <em>${escapeHtml(detail)}</em>
              </a>`
            )
            .join("")}
        </div>
      </article>

      <article class="visual-card">
        <div class="visual-label">Portfolio Evidence Stack</div>
        <div class="bar-chart">
          ${bars
            .map(
              ([label, value, href]) => `
              <a class="bar-row" href="${href}">
                <span>${escapeHtml(label)}</span>
                <strong>${value}%</strong>
                <i style="width:${value}%"></i>
              </a>`
            )
            .join("")}
        </div>
      </article>

      <article class="visual-card">
        <div class="visual-label">Navigation Buttons</div>
        <div class="button-stack">
          <a href="#table-of-contents">Open Table of Contents</a>
          <a href="${sources}">Open Reference Links</a>
          <a href="${architecture}">Open Architecture</a>
          <a href="${dashboard}">Open Dashboard Spec</a>
        </div>
      </article>
    </div>
  </section>`;
}

function buildHtml(doc, bodyHtml, toc) {
  const today = new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  const enhancedBodyHtml = enhanceSections(bodyHtml, toc);

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(doc.title)}</title>
<style>
${themeCss(doc)}
</style>
</head>
<body>
  <div class="screen-toolbar">
    <a href="#top">Cover</a>
    <a href="#table-of-contents">Contents</a>
    ${buildQuickLinks(toc, true)}
    <button type="button" data-action="expand">Expand All</button>
    <button type="button" data-action="collapse">Collapse All</button>
  </div>
  <div class="print-header">
    <span>${escapeHtml(doc.kicker)}</span>
    <span>${escapeHtml(doc.title)}</span>
  </div>
  <div class="print-footer">
    <span>Enterprise Healthcare Analytics Portfolio Blueprint</span>
    <span>${escapeHtml(today)}</span>
  </div>

  <section class="cover" id="top">
    <div class="cover-band"></div>
    <div class="cover-grid">
      <div>
        <div class="eyebrow">${escapeHtml(doc.kicker)}</div>
        <h1>${escapeHtml(doc.title)}</h1>
        <p class="subtitle">${escapeHtml(doc.subtitle)}</p>
        <div class="audience">${escapeHtml(doc.audience)}</div>
        <div class="cover-actions">
          <a href="#interactive-control-center">Open Navigation Hub</a>
          <a href="#table-of-contents">Jump To Contents</a>
        </div>
      </div>
      <aside class="cover-card">
        <div class="card-label">Blueprint Scope</div>
        <ul>
          <li>Dataset source register</li>
          <li>Enterprise warehouse architecture</li>
          <li>SQL mart plan</li>
          <li>Python and ML pipeline</li>
          <li>Power BI dashboard system</li>
          <li>KPI and portfolio strategy</li>
        </ul>
      </aside>
    </div>
  </section>

  ${buildExperiencePage(doc, toc)}

  <section class="toc-page" id="table-of-contents">
    <div class="section-kicker">Navigation</div>
    <h2>Table of Contents</h2>
    <div class="toc-grid">
      ${buildToc(toc)}
    </div>
  </section>

  <main class="content">
    ${enhancedBodyHtml}
  </main>

  <script>
    window.__HAS_MERMAID__ = Boolean(document.querySelector('.mermaid'));
    document.querySelectorAll('[data-action="expand"]').forEach((button) => {
      button.addEventListener('click', () => document.querySelectorAll('.section-module').forEach((item) => item.open = true));
    });
    document.querySelectorAll('[data-action="collapse"]').forEach((button) => {
      button.addEventListener('click', () => document.querySelectorAll('.section-module').forEach((item) => item.open = false));
    });
    function openHashTarget() {
      if (!window.location.hash) return;
      const target = document.querySelector(window.location.hash);
      if (!target) return;
      const module = target.closest('.section-module');
      if (module) module.open = true;
      setTimeout(() => target.scrollIntoView({ block: 'start' }), 30);
    }
    window.addEventListener('hashchange', openHashTarget);
    document.querySelectorAll('a[href^="#"]').forEach((link) => {
      link.addEventListener('click', () => setTimeout(openHashTarget, 20));
    });
    openHashTarget();
    if (window.__HAS_MERMAID__) {
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js';
      script.onload = async () => {
        window.mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'loose',
          theme: 'base',
          themeVariables: {
            fontFamily: 'Segoe UI, Arial, sans-serif',
            primaryColor: '#EAF5F7',
            primaryTextColor: '#172033',
            primaryBorderColor: '${doc.accent}',
            lineColor: '#64748B',
            secondaryColor: '#EEF2FF',
            tertiaryColor: '#F8FAFC',
          },
        });
        await window.mermaid.run({ querySelector: '.mermaid' });
      };
      document.head.appendChild(script);
    }
  </script>
</body>
</html>`;
}

function themeCss(doc) {
  return `
:root {
  --accent: ${doc.accent};
  --secondary: ${doc.secondary};
  --ink: #172033;
  --muted: #5D687A;
  --soft: #F5F8FB;
  --line: #D8E0EA;
  --code-bg: #0F172A;
  --code-ink: #E5EEF8;
}

@page {
  size: A4;
  margin: 17mm 14mm 18mm 14mm;
}

* { box-sizing: border-box; }

html {
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

body {
  margin: 0;
  color: var(--ink);
  font-family: "Aptos", "Segoe UI", Arial, sans-serif;
  font-size: 9.8pt;
  line-height: 1.48;
  background: white;
}

.screen-toolbar {
  position: sticky;
  top: 0;
  z-index: 100;
  display: none;
  gap: 8px;
  align-items: center;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.94);
  border-bottom: 1px solid #E5E7EB;
  backdrop-filter: blur(12px);
}

.screen-toolbar a,
.screen-toolbar button {
  border: 1px solid #D8E0EA;
  background: #F8FAFC;
  color: #172033;
  border-radius: 999px;
  padding: 7px 11px;
  font: inherit;
  font-weight: 750;
  text-decoration: none;
  cursor: pointer;
}

.screen-toolbar a:hover,
.screen-toolbar button:hover {
  color: white;
  background: var(--accent);
  border-color: var(--accent);
}

.print-header,
.print-footer {
  position: fixed;
  left: 0;
  right: 0;
  display: flex;
  justify-content: space-between;
  color: #6B7280;
  font-size: 7.8pt;
  z-index: 20;
}

.print-header {
  top: -10mm;
  padding-bottom: 2mm;
  border-bottom: 0.4pt solid #E5E7EB;
}

.print-footer {
  bottom: -11mm;
  padding-top: 2mm;
  border-top: 0.4pt solid #E5E7EB;
}

.cover {
  min-height: 260mm;
  break-after: page;
  position: relative;
  overflow: hidden;
  padding: 22mm 16mm;
  border: 1px solid #E5EAF0;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.96), rgba(245,248,251,0.98)),
    radial-gradient(circle at 10% 18%, color-mix(in srgb, var(--accent) 22%, transparent), transparent 31%),
    radial-gradient(circle at 88% 82%, color-mix(in srgb, var(--secondary) 18%, transparent), transparent 28%);
}

.cover-band {
  position: absolute;
  inset: 0 auto 0 0;
  width: 9mm;
  background: linear-gradient(180deg, var(--accent), var(--secondary));
}

.cover-grid {
  height: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 58mm;
  gap: 12mm;
  align-items: center;
}

.eyebrow,
.section-kicker {
  color: var(--accent);
  font-size: 8pt;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 800;
}

.cover h1 {
  margin: 5mm 0 6mm;
  max-width: 136mm;
  color: #0B1220;
  font-size: 30pt;
  line-height: 1.02;
  font-weight: 850;
}

.subtitle {
  max-width: 128mm;
  margin: 0 0 8mm;
  color: #39465B;
  font-size: 12.5pt;
  line-height: 1.5;
}

.audience {
  display: inline-block;
  max-width: 128mm;
  padding: 3.5mm 5mm;
  border-left: 2.5mm solid var(--accent);
  background: rgba(255,255,255,0.78);
  color: #263244;
  font-size: 9.2pt;
  font-weight: 700;
}

.cover-actions {
  display: flex;
  gap: 3mm;
  flex-wrap: wrap;
  margin-top: 9mm;
}

.cover-actions a,
.button-stack a,
.nav-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 9mm;
  padding: 2.6mm 4.2mm;
  color: white;
  background: linear-gradient(135deg, var(--accent), var(--secondary));
  border-radius: 999px;
  font-size: 8.5pt;
  font-weight: 850;
  text-decoration: none;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.12);
}

.nav-chip.compact {
  min-height: auto;
  padding: 6px 10px;
  color: #172033;
  background: #F8FAFC;
  box-shadow: none;
}

.cover-card {
  align-self: stretch;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 8mm;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: rgba(255,255,255,0.86);
  box-shadow: 0 18px 50px rgba(15, 23, 42, 0.10);
}

.card-label {
  margin-bottom: 4mm;
  color: var(--accent);
  font-size: 8pt;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.cover-card ul {
  margin: 0;
  padding-left: 4.5mm;
}

.cover-card li {
  margin: 2.5mm 0;
  color: #2D3748;
  font-weight: 650;
}

.toc-page {
  break-after: page;
  padding-top: 8mm;
}

.experience-page {
  break-after: page;
  padding-top: 6mm;
}

.experience-page h2 {
  margin-top: 2mm;
  font-size: 22pt;
  border: none;
}

.lede {
  max-width: 170mm;
  color: #475569;
  font-size: 10.4pt;
}

.quick-link-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 3mm;
  margin: 7mm 0;
  padding: 5mm;
  border: 1px solid #DDE6EF;
  background: linear-gradient(135deg, #FFFFFF, #F8FAFC);
}

.visual-grid {
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 5mm;
}

.visual-card {
  padding: 5mm;
  border: 1px solid #DDE6EF;
  background: #FFFFFF;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
  break-inside: avoid;
}

.visual-card.wide {
  grid-column: 1 / -1;
}

.visual-label {
  margin-bottom: 4mm;
  color: var(--accent);
  font-size: 7.8pt;
  font-weight: 850;
  text-transform: uppercase;
  letter-spacing: 0.07em;
}

.timeline {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 2.5mm;
}

.timeline-step {
  min-height: 36mm;
  padding: 4mm;
  color: #172033;
  text-decoration: none;
  border: 1px solid #D8E0EA;
  background: #F8FAFC;
}

.timeline-step span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 8mm;
  height: 8mm;
  margin-bottom: 4mm;
  color: white;
  background: var(--accent);
  border-radius: 50%;
  font-size: 7.5pt;
  font-weight: 850;
}

.timeline-step strong,
.timeline-step em {
  display: block;
}

.timeline-step strong {
  margin-bottom: 2mm;
  color: #0F172A;
  font-size: 9pt;
}

.timeline-step em {
  color: #64748B;
  font-size: 7.5pt;
  font-style: normal;
}

.bar-chart {
  display: grid;
  gap: 3mm;
}

.bar-row {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 12mm;
  gap: 3mm;
  padding: 3mm 0 5mm;
  color: #172033;
  text-decoration: none;
}

.bar-row i {
  position: absolute;
  left: 0;
  bottom: 0;
  height: 2mm;
  background: linear-gradient(90deg, var(--accent), var(--secondary));
  border-radius: 999px;
}

.bar-row::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 2mm;
  background: #E5EAF0;
  border-radius: 999px;
  z-index: -1;
}

.button-stack {
  display: grid;
  gap: 3mm;
}

.button-stack a {
  border-radius: 6px;
}

.toc-page h2 {
  margin-top: 2mm;
  font-size: 22pt;
  border: none;
}

.toc-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 3mm 5mm;
  margin-top: 8mm;
}

.toc-item {
  display: grid;
  grid-template-columns: 12mm 1fr;
  gap: 3mm;
  align-items: start;
  min-height: 11mm;
  padding: 3mm;
  color: var(--ink);
  text-decoration: none;
  border: 1px solid #E4EAF1;
  background: #FBFCFE;
  break-inside: avoid;
}

.toc-number {
  color: var(--accent);
  font-weight: 850;
}

.content > h1:first-child {
  display: none;
}

.section-module {
  margin: 0 0 5mm;
  border: 1px solid transparent;
}

.section-module summary {
  list-style: none;
  cursor: pointer;
}

.section-module summary::-webkit-details-marker {
  display: none;
}

.section-module summary h2 {
  display: block;
}

.collapse-indicator {
  display: none;
  float: right;
  margin-top: 13mm;
  padding: 1.5mm 2.5mm;
  color: var(--accent);
  border: 1px solid #D8E0EA;
  border-radius: 999px;
  font-size: 7.2pt;
  font-weight: 800;
  text-transform: uppercase;
}

.section-body {
  padding-bottom: 2mm;
}

.section-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 2mm;
  margin: -1mm 0 3mm;
  padding: 2.5mm;
  border: 1px solid #E5EAF0;
  background: #FBFCFE;
  break-inside: avoid;
}

.section-nav a,
.related-chip {
  display: inline-flex;
  align-items: center;
  min-height: 7mm;
  padding: 1.6mm 2.6mm;
  color: var(--secondary);
  border: 1px solid #D8E0EA;
  border-radius: 999px;
  background: white;
  font-size: 7.6pt;
  font-weight: 800;
  text-decoration: none;
}

.smart-links {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2mm;
  margin: 0 0 4mm;
  padding: 3mm 4mm;
  border-left: 1.6mm solid var(--accent);
  background: #F8FAFC;
  break-inside: avoid;
}

.smart-links span {
  color: #64748B;
  font-size: 7.6pt;
  font-weight: 850;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

h1, h2, h3, h4 {
  color: #101828;
  line-height: 1.18;
  break-after: avoid;
}

h2 {
  margin: 12mm 0 4mm;
  padding: 0 0 2.5mm;
  border-bottom: 1.2pt solid var(--line);
  font-size: 17pt;
}

h2::before {
  content: "";
  display: inline-block;
  width: 3.2mm;
  height: 3.2mm;
  margin-right: 2.4mm;
  background: var(--accent);
  vertical-align: 0.6mm;
}

h3 {
  margin: 7mm 0 2.5mm;
  color: var(--secondary);
  font-size: 12.5pt;
}

h4 {
  margin: 4.5mm 0 1.5mm;
  color: #334155;
  font-size: 10.5pt;
}

p {
  margin: 0 0 3.5mm;
}

a {
  color: var(--secondary);
  font-weight: 650;
  text-decoration: none;
  overflow-wrap: anywhere;
}

ul, ol {
  margin: 0 0 4mm;
  padding-left: 6mm;
}

li {
  margin: 1.3mm 0;
}

strong {
  color: #111827;
  font-weight: 800;
}

blockquote {
  margin: 5mm 0;
  padding: 4mm 5mm;
  color: #2B3A4F;
  border-left: 2mm solid var(--accent);
  background: #F7FAFC;
}

table {
  width: 100%;
  margin: 5mm 0 6mm;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 7.6pt;
  break-inside: auto;
}

thead {
  display: table-header-group;
}

tr {
  break-inside: avoid;
}

th {
  color: white;
  background: linear-gradient(90deg, var(--accent), var(--secondary));
  font-weight: 800;
  text-align: left;
}

th, td {
  padding: 2mm 2.2mm;
  border: 0.45pt solid #D8E0EA;
  vertical-align: top;
  overflow-wrap: anywhere;
}

tbody tr:nth-child(even) td {
  background: #F8FAFC;
}

code {
  padding: 0.3mm 1mm;
  color: #0F3B57;
  background: #EAF5F7;
  border-radius: 3px;
  font-family: "Cascadia Code", Consolas, monospace;
  font-size: 8.1pt;
}

pre {
  margin: 4.5mm 0 6mm;
  padding: 4mm;
  overflow: hidden;
  color: var(--code-ink);
  background: var(--code-bg);
  border-radius: 6px;
  border: 1px solid #1E293B;
  white-space: pre-wrap;
  word-break: break-word;
  break-inside: avoid;
}

pre code {
  padding: 0;
  color: inherit;
  background: transparent;
  border: none;
  font-size: 7.1pt;
  line-height: 1.42;
}

.diagram-shell {
  margin: 6mm 0;
  padding: 4mm;
  border: 1px solid #D8E0EA;
  background: #FBFCFE;
  break-inside: avoid;
}

.diagram-label {
  margin-bottom: 2mm;
  color: var(--accent);
  font-size: 7.6pt;
  font-weight: 850;
  text-transform: uppercase;
  letter-spacing: 0.07em;
}

.diagram-shell .mermaid {
  margin: 0;
  padding: 3mm;
  text-align: center;
  color: #1F2937;
  background: white;
  border: 1px solid #E4EAF1;
  white-space: pre-wrap;
}

.diagram-shell svg {
  max-width: 100%;
  height: auto;
}

hr {
  height: 1px;
  margin: 9mm 0;
  border: 0;
  background: var(--line);
}

@media print {
  .screen-toolbar {
    display: none !important;
  }

  .section-module {
    display: block;
  }

  .section-module:not([open]) .section-body {
    display: block;
  }

  .collapse-indicator {
    display: none !important;
  }

  .content h2 {
    break-before: auto;
  }
}

@media screen {
  body {
    max-width: 1180px;
    margin: 0 auto;
    background: #EEF3F8;
    font-size: 15px;
  }

  .screen-toolbar {
    display: flex;
    overflow-x: auto;
  }

  .cover,
  .experience-page,
  .toc-page,
  .content {
    background: white;
  }

  .cover {
    min-height: 760px;
    margin-top: 16px;
  }

  .content {
    padding: 20px 44px 60px;
  }

  .section-module {
    margin: 18px 0;
    padding: 0 18px 16px;
    border-color: #E5EAF0;
    background: white;
    box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
  }

  .collapse-indicator {
    display: inline-flex;
  }

  .section-module:not([open]) {
    padding-bottom: 0;
  }

  .section-module:not([open]) summary h2 {
    margin-bottom: 12px;
  }

  .toc-page,
  .experience-page {
    padding: 42px 44px;
    margin: 16px 0;
  }
}

@media screen and (max-width: 760px) {
  body {
    font-size: 14px;
  }

  .cover {
    min-height: auto;
    padding: 34px 24px;
  }

  .cover-grid,
  .visual-grid,
  .toc-grid {
    grid-template-columns: 1fr;
  }

  .cover h1 {
    font-size: 34px;
  }

  .timeline {
    grid-template-columns: 1fr;
  }

  .content,
  .toc-page,
  .experience-page {
    padding: 24px;
  }

  table {
    font-size: 11px;
  }
}
`;
}

async function renderMermaid(page) {
  const hasMermaid = await page.evaluate(() => window.__HAS_MERMAID__);
  if (!hasMermaid) return "not-needed";

  try {
    const alreadyRendered = await page.evaluate(() =>
      Boolean(document.querySelector(".mermaid[data-processed='true'] svg, .diagram-shell svg"))
    );
    if (alreadyRendered) return "rendered";

    const hasRuntime = await page.evaluate(() => Boolean(window.mermaid));
    if (!hasRuntime) {
      await page.addScriptTag({
        url: "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js",
      });
    }
    await page.evaluate(async () => {
      window.mermaid.initialize({
        startOnLoad: false,
        securityLevel: "loose",
        theme: "base",
        themeVariables: {
          fontFamily: "Segoe UI, Arial, sans-serif",
          primaryColor: "#EAF5F7",
          primaryTextColor: "#172033",
          primaryBorderColor: "#0E7C86",
          lineColor: "#64748B",
          secondaryColor: "#EEF2FF",
          tertiaryColor: "#F8FAFC",
        },
      });
      await window.mermaid.run({ querySelector: ".mermaid" });
    });
    return "rendered";
  } catch (error) {
    console.warn(`Mermaid rendering skipped: ${error.message}`);
    return "fallback";
  }
}

async function renderDocument(browser, doc) {
  const markdownPath = path.join(rootDir, doc.source);
  const markdown = await fs.readFile(markdownPath, "utf8");
  const htmlRaw = marked.parse(preprocessMarkdown(markdown));
  const { html: bodyHtml, toc } = addHeadingIds(htmlRaw);
  const fullHtml = buildHtml(doc, bodyHtml, toc);

  await fs.mkdir(outDir, { recursive: true });
  const htmlPath = path.join(outDir, doc.html);
  const pdfPath = path.join(outDir, doc.pdf);
  await fs.writeFile(htmlPath, fullHtml, "utf8");

  const page = await browser.newPage({ viewport: { width: 1240, height: 1754 } });
  await page.setContent(fullHtml, { waitUntil: "networkidle" });
  const mermaidStatus = await renderMermaid(page);
  await page.emulateMedia({ media: "print" });
  await page.pdf({
    path: pdfPath,
    format: "A4",
    printBackground: true,
    preferCSSPageSize: true,
    displayHeaderFooter: false,
  });
  await page.close();

  const pdfBytes = await fs.readFile(pdfPath);
  const pdfDoc = await PDFDocument.load(pdfBytes);
  return {
    source: doc.source,
    htmlPath,
    pdfPath,
    pages: pdfDoc.getPageCount(),
    bytes: pdfBytes.length,
    mermaidStatus,
  };
}

async function main() {
  const browser = await chromium.launch({
    headless: true,
    executablePath: chromePath,
  });

  try {
    const results = [];
    for (const doc of documents) {
      results.push(await renderDocument(browser, doc));
    }
    console.table(
      results.map((result) => ({
        pdf: path.relative(rootDir, result.pdfPath),
        pages: result.pages,
        size_mb: (result.bytes / 1024 / 1024).toFixed(2),
        mermaid: result.mermaidStatus,
      }))
    );
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
