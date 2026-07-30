import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const sharp = process.env.CODEX_NODE_MODULES
  ? require(path.join(process.env.CODEX_NODE_MODULES, "sharp"))
  : require("sharp");

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const ANALYSIS = path.join(ROOT, "analysis");
const BASE = path.join(ROOT, "figures_improved");
const SVG_DIR = path.join(BASE, "svg");
const PNG_DIR = path.join(BASE, "png");
const TIFF_DIR = path.join(BASE, "tiff");
await Promise.all([SVG_DIR, PNG_DIR, TIFF_DIR].map((directory) => fs.mkdir(directory, { recursive: true })));

const C = {
  navy: "#17365D",
  teal: "#007C91",
  tealLight: "#D9F0F2",
  orange: "#D97706",
  red: "#B23A48",
  ink: "#1F2937",
  gray: "#6B7280",
  grid: "#D1D5DB",
  pale: "#F4F7FA",
  white: "#FFFFFF",
};

function esc(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function frame(width, height, title, subtitle, body) {
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
  <rect width="100%" height="100%" fill="${C.white}"/>
  <style>
    text { font-family: Arial, Helvetica, sans-serif; fill: ${C.ink}; }
    .title { font-size: 42px; font-weight: 700; }
    .subtitle { font-size: 23px; fill: ${C.gray}; }
    .axis { font-size: 20px; fill: ${C.gray}; }
    .label { font-size: 23px; }
    .small { font-size: 19px; fill: ${C.gray}; }
  </style>
  <text class="title" x="90" y="72">${esc(title)}</text>
  <text class="subtitle" x="90" y="112">${esc(subtitle)}</text>
  ${body}
</svg>`;
}

async function save(name, svg) {
  await fs.writeFile(path.join(SVG_DIR, `${name}.svg`), svg, "utf8");
  const source = Buffer.from(svg);
  await sharp(source, { density: 300 }).png({ compressionLevel: 9 }).withMetadata({ density: 300 }).toFile(path.join(PNG_DIR, `${name}.png`));
  await sharp(source, { density: 300 }).tiff({ compression: "lzw", resolutionUnit: "inch", xres: 300, yres: 300 }).toFile(path.join(TIFF_DIR, `${name}.tiff`));
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let value = "";
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { value += '"'; i += 1; }
      else if (ch === '"') quoted = false;
      else value += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") { row.push(value); value = ""; }
    else if (ch === "\n") { row.push(value.replace(/\r$/, "")); rows.push(row); row = []; value = ""; }
    else value += ch;
  }
  if (value.length || row.length) { row.push(value); rows.push(row); }
  const headers = rows.shift();
  return rows.filter((r) => r.length === headers.length).map((r) => Object.fromEntries(headers.map((h, i) => [h, r[i]])));
}

// Figure 1: reproducible sample construction.
const flow = JSON.parse(await fs.readFile(path.join(ANALYSIS, "sample_flow.json"), "utf8"));
const attrition = parseCsv(await fs.readFile(path.join(ANALYSIS, "reviewer_revision_attrition_audit.csv"), "utf8"));
const attritionValue = (quantity) => Number(attrition.find((row) => row.quantity === quantity).value);
const steps = [
  [flow.rpe_records_total, "RPE records in PMData"],
  [flow.matched_sessions_broad, "RPE records matched to tracker sessions"],
  [flow.unique_match_both_directions, "Unique bidirectional matches"],
  [attritionValue("unique_pairs_passing_hr_qc"), "Unique matches passing heart-rate quality control"],
  [flow.primary_sessions, "Primary analysis sessions from 15 participants"],
];
const losses = [
  "314 records not linked to a tracker session",
  "22 matches not bidirectionally unique",
  "180 unique matches failed heart-rate quality control",
  "12 sessions failed remaining primary criteria",
];
let body = "";
steps.forEach(([count, label], index) => {
  const y = 165 + index * 164;
  body += `<rect x="250" y="${y}" width="1100" height="100" rx="18" fill="${index === 4 ? C.tealLight : C.pale}" stroke="${index === 4 ? C.teal : C.grid}" stroke-width="3"/>
  <text x="305" y="${y + 63}" font-size="38" font-weight="700" fill="${C.navy}">${count}</text>
  <text x="480" y="${y + 61}" class="label">${esc(label)}</text>`;
  if (index < 4) body += `<line x1="800" y1="${y + 100}" x2="800" y2="${y + 140}" stroke="${C.gray}" stroke-width="3"/><polygon points="790,${y + 132} 810,${y + 132} 800,${y + 148}" fill="${C.gray}"/><text x="835" y="${y + 131}" class="small">${esc(losses[index])}</text>`;
});
body += `<rect x="280" y="1010" width="480" height="100" rx="16" fill="${C.white}" stroke="${C.navy}" stroke-width="3"/>
<text x="520" y="1050" text-anchor="middle" font-size="30" font-weight="700">Nested prediction</text>
<text x="520" y="1087" text-anchor="middle" class="small">255 sessions; 15 held-out participant folds</text>
<rect x="840" y="1010" width="480" height="100" rx="16" fill="${C.white}" stroke="${C.navy}" stroke-width="3"/>
<text x="1080" y="1050" text-anchor="middle" font-size="30" font-weight="700">Within-person association</text>
<text x="1080" y="1087" text-anchor="middle" class="small">244 sessions; 9 participants with ≥5 sessions</text>`;
await save("Figure_1_sample_flow", frame(1600, 1180, "Construction of the public-data development sample", "Sequential linkage, uniqueness, heart-rate quality control, and analysis eligibility", body));

// Figure 2: normalized exponential tilting mechanism.
const plot = { left: 170, right: 1020, top: 220, bottom: 850 };
const x = (v) => plot.left + ((v - 0.05) / 0.9) * (plot.right - plot.left);
const y = (v) => plot.bottom - (v / 18) * (plot.bottom - plot.top);
body = "";
for (let tick = 0; tick <= 18; tick += 3) {
  body += `<line x1="${plot.left}" y1="${y(tick)}" x2="${plot.right}" y2="${y(tick)}" stroke="${C.grid}"/><text class="axis" x="${plot.left - 25}" y="${y(tick) + 7}" text-anchor="end">${tick}</text>`;
}
for (let i = 0; i < 10; i += 1) {
  const c = 0.05 + i * 0.1;
  body += `<line x1="${x(c)}" y1="${plot.top}" x2="${x(c)}" y2="${plot.bottom}" stroke="${C.grid}"/><text class="axis" x="${x(c)}" y="${plot.bottom + 38}" text-anchor="middle">${c.toFixed(2)}</text>`;
}
const curves = [
  { lambda: 0, color: C.gray, label: "λ = 0 (mean HRR)" },
  { lambda: 3, color: C.navy, label: "λ = 3" },
  { lambda: 6.2, color: C.teal, label: "λ = 6.2 (full-data estimate)" },
];
curves.forEach(({ lambda, color, label }, index) => {
  const points = [];
  for (let j = 0; j <= 90; j += 1) {
    const c = 0.05 + j * 0.01;
    const multiplier = Math.exp(lambda * (c - 0.5));
    points.push(`${x(c).toFixed(1)},${y(multiplier).toFixed(1)}`);
  }
  body += `<polyline points="${points.join(" ")}" fill="none" stroke="${color}" stroke-width="5"/><line x1="1090" y1="${285 + index * 55}" x2="1160" y2="${285 + index * 55}" stroke="${color}" stroke-width="6"/><text x="1180" y="${292 + index * 55}" class="small">${label}</text>`;
});
body += `<line x1="${plot.left}" y1="${plot.bottom}" x2="${plot.right}" y2="${plot.bottom}" stroke="${C.ink}" stroke-width="3"/><line x1="${plot.left}" y1="${plot.top}" x2="${plot.left}" y2="${plot.bottom}" stroke="${C.ink}" stroke-width="3"/>
<text class="label" x="${(plot.left + plot.right) / 2}" y="${plot.bottom + 90}" text-anchor="middle">HRR decile midpoint, cᵢ</text>
<text class="label" x="65" y="${(plot.top + plot.bottom) / 2}" text-anchor="middle" transform="rotate(-90 65 ${(plot.top + plot.bottom) / 2})">Relative multiplier exp[λ(cᵢ − 0.50)]</text>
<rect x="1080" y="500" width="430" height="300" rx="16" fill="${C.pale}" stroke="${C.grid}" stroke-width="2"/>
<text x="1110" y="550" font-size="25" font-weight="700">tHRR-I(λ)</text>
<text x="1110" y="598" font-size="23">Σ Pᵢ cᵢ exp(λcᵢ)</text>
<line x1="1105" y1="613" x2="1435" y2="613" stroke="${C.ink}" stroke-width="2"/>
<text x="1110" y="650" font-size="23">Σ Pᵢ exp(λcᵢ)</text>
<text x="1110" y="700" class="small">Bounded between 0 and 1</text>
<text x="1110" y="735" class="small">λ = 0 gives mean HRR</text>
<text x="1110" y="770" class="small">At λ = 6.2, each decile step multiplies weight by 1.86</text>`;
await save("Figure_2_tilted_weighting", frame(1600, 1030, "Normalized exponential tilting preserves an interpretable HRR scale", "Higher λ increases the influence of upper HRR bins while preserving the 0–1 output range", body));

// Figure 3: paired associations.
const assoc = parseCsv(await fs.readFile(path.join(ANALYSIS, "improved_formula_intensity_associations.csv"), "utf8"));
const assocPlot = { left: 430, right: 1170, top: 185, bottom: 900 };
const ay = (v) => assocPlot.bottom - ((v + 0.05) / 1.0) * (assocPlot.bottom - assocPlot.top);
const xl = 610;
const xt = 990;
body = "";
for (let tick = 0; tick <= 0.9; tick += 0.1) body += `<line x1="${assocPlot.left}" y1="${ay(tick)}" x2="${assocPlot.right}" y2="${ay(tick)}" stroke="${C.grid}"/><text class="axis" x="${assocPlot.left - 28}" y="${ay(tick) + 7}" text-anchor="end">${tick.toFixed(1)}</text>`;
assoc.forEach((row) => {
  const linear = Number(row.linear_decile);
  const tilted = Number(row.tilted_hrr);
  const color = tilted >= linear ? C.teal : C.red;
  const labelOffsets = { p07: -10, p11: 16, p14: 26 };
  const labelY = ay(tilted) + (labelOffsets[row.participant] ?? 0);
  body += `<line x1="${xl}" y1="${ay(linear)}" x2="${xt}" y2="${ay(tilted)}" stroke="${color}" stroke-width="4" opacity="0.82"/><rect x="${xl - 8}" y="${ay(linear) - 8}" width="16" height="16" fill="${C.navy}"/><circle cx="${xt}" cy="${ay(tilted)}" r="9" fill="${C.teal}"/><line x1="${xt + 11}" y1="${ay(tilted)}" x2="${xt + 25}" y2="${labelY}" stroke="${C.gray}" stroke-width="1.5"/><text x="${xt + 30}" y="${labelY + 7}" class="small">${esc(row.participant)} (n=${esc(row.sessions)})</text>`;
});
const summary = parseCsv(await fs.readFile(path.join(ANALYSIS, "improved_formula_intensity_summary.csv"), "utf8"));
const lm = Number(summary.find((r) => r.family === "linear_decile").median_participant_rho);
const tm = Number(summary.find((r) => r.family === "tilted_hrr").median_participant_rho);
body += `<line x1="${xl - 65}" y1="${ay(lm)}" x2="${xl + 65}" y2="${ay(lm)}" stroke="${C.orange}" stroke-width="9"/><line x1="${xt - 65}" y1="${ay(tm)}" x2="${xt - 18}" y2="${ay(tm)}" stroke="${C.orange}" stroke-width="9"/>
<text x="${xl}" y="955" text-anchor="middle" font-size="28" font-weight="700">Linear decile score</text><text x="${xt}" y="955" text-anchor="middle" font-size="28" font-weight="700">tHRR-I</text>
<text class="label" x="70" y="${(assocPlot.top + assocPlot.bottom) / 2}" text-anchor="middle" transform="rotate(-90 70 ${(assocPlot.top + assocPlot.bottom) / 2})">Within-person Spearman ρ with session RPE</text>
<text x="430" y="1025" class="small">Orange bars show medians: linear ${lm.toFixed(3)}, tHRR-I ${tm.toFixed(3)}.</text>`;
await save("Figure_3_participant_associations", frame(1600, 1080, "Within-person changes were heterogeneous", "Five of nine evaluable participants improved; the paired median difference remained imprecise", body));

// Figure 4: nested prediction performance.
const performance = parseCsv(await fs.readFile(path.join(ANALYSIS, "improved_formula_prediction_summary.csv"), "utf8"));
const interceptPerformance = parseCsv(await fs.readFile(path.join(ANALYSIS, "reviewer_revision_intercept_performance.csv"), "utf8"));
performance.push(...interceptPerformance);
const order = ["tilted_hrr", "entropic_hrr", "power_hrr", "linear_decile", "mean_hrr", "original_exp", "banister_trimp", "intercept_only"];
const labels = { tilted_hrr: "tHRR-I", entropic_hrr: "Entropic HRR", power_hrr: "Power-mean HRR", linear_decile: "Linear decile score", mean_hrr: "Mean HRR", original_exp: "Original exponential sum", banister_trimp: "Integrated Banister TRIMP", intercept_only: "Intercept-only baseline" };
const px = (v) => 535 + ((v - 0.7) / 1.5) * 915;
body = "";
for (let tick = 0.8; tick <= 2.2; tick += 0.2) body += `<line x1="${px(tick)}" y1="200" x2="${px(tick)}" y2="850" stroke="${C.grid}"/><text class="axis" x="${px(tick)}" y="895" text-anchor="middle">${tick.toFixed(1)}</text>`;
order.forEach((family, index) => {
  const row = performance.find((r) => r.family === family);
  const yy = 210 + index * 78;
  const estimate = Number(row.participant_balanced_mae);
  const low = Number(row.mae_ci_low);
  const high = Number(row.mae_ci_high);
  const color = family === "tilted_hrr" ? C.teal : C.navy;
  body += `<text x="500" y="${yy + 8}" text-anchor="end" class="label">${labels[family]}</text><line x1="${px(low)}" y1="${yy}" x2="${px(high)}" y2="${yy}" stroke="${color}" stroke-width="6"/><line x1="${px(low)}" y1="${yy - 13}" x2="${px(low)}" y2="${yy + 13}" stroke="${color}" stroke-width="4"/><line x1="${px(high)}" y1="${yy - 13}" x2="${px(high)}" y2="${yy + 13}" stroke="${color}" stroke-width="4"/><circle cx="${px(estimate)}" cy="${yy}" r="12" fill="${color}"/><text x="${px(high) + 15}" y="${yy + 7}" class="small">${estimate.toFixed(2)}</text>`;
});
body += `<line x1="535" y1="850" x2="1450" y2="850" stroke="${C.ink}" stroke-width="3"/><text class="label" x="990" y="955" text-anchor="middle">Participant-balanced MAE (RPE units; lower is better)</text>
<rect x="1010" y="112" width="470" height="80" rx="14" fill="${C.pale}" stroke="${C.grid}"/><text x="1035" y="146" class="small">tHRR-I − linear MAE: −0.097 RPE units</text><text x="1035" y="177" class="small">95% conditional CI −0.164 to −0.033</text>`;
await save("Figure_4_nested_cv_performance", frame(1600, 1030, "Held-out-participant prediction performance", "Conditional participant-cluster intervals; formula-family selection was not repeated", body));

// Figure 5: real session pairs with nearly equal mean HRR but different distributions.
const sessions = parseCsv(await fs.readFile(path.join(ANALYSIS, "pmdata_primary_analysis_sessions.csv"), "utf8"));
const examples = [
  { participant: "p08", a: 7, b: 14 },
  { participant: "p07", a: 40, b: 47 },
];
body = "";
examples.forEach((example, panelIndex) => {
  const first = sessions.find((row) => row.participant === example.participant && Number(row.session_number) === example.a);
  const second = sessions.find((row) => row.participant === example.participant && Number(row.session_number) === example.b);
  const top = 175 + panelIndex * 430;
  const bottom = top + 285;
  const left = 300;
  const right = 1460;
  const yValue = (value) => bottom - (value / 0.9) * (bottom - top);
  const xValue = (index) => left + (index - 1) * ((right - left) / 9);
  body += `<text x="90" y="${top + 25}" font-size="28" font-weight="700">${panelIndex === 0 ? "A" : "B"}</text>`;
  for (let tick = 0; tick <= 0.9; tick += 0.3) {
    body += `<line x1="${left}" y1="${yValue(tick)}" x2="${right}" y2="${yValue(tick)}" stroke="${C.grid}"/><text class="axis" x="${left - 25}" y="${yValue(tick) + 7}" text-anchor="end">${tick.toFixed(1)}</text>`;
  }
  for (let index = 1; index <= 10; index += 1) {
    const xx = xValue(index);
    const firstValue = Number(first[`p${index}`]);
    const secondValue = Number(second[`p${index}`]);
    body += `<rect x="${xx - 31}" y="${yValue(firstValue)}" width="28" height="${bottom - yValue(firstValue)}" fill="${C.navy}"/><rect x="${xx + 3}" y="${yValue(secondValue)}" width="28" height="${bottom - yValue(secondValue)}" fill="${C.teal}"/><text class="axis" x="${xx}" y="${bottom + 30}" text-anchor="middle">${index}</text>`;
  }
  const getExample = (row) => {
    const mean = Number(row.mean_hrr);
    const proportions = Array.from({ length: 10 }, (_, index) => Number(row[`p${index + 1}`]));
    const centers = Array.from({ length: 10 }, (_, index) => 0.05 + index * 0.1);
    const weights = centers.map((center) => Math.exp(6.2 * center));
    const tilted = proportions.reduce((sum, value, index) => sum + value * centers[index] * weights[index], 0) / proportions.reduce((sum, value, index) => sum + value * weights[index], 0);
    return { mean, tilted, rpe: Number(row.rpe) };
  };
  const firstSummary = getExample(first);
  const secondSummary = getExample(second);
  body += `<line x1="${left}" y1="${bottom}" x2="${right}" y2="${bottom}" stroke="${C.ink}" stroke-width="3"/><text class="small" x="${left}" y="${bottom + 68}">${example.participant}: session ${example.a} | mean HRR ${firstSummary.mean.toFixed(3)}, tHRR-I ${firstSummary.tilted.toFixed(3)}, RPE ${firstSummary.rpe.toFixed(0)}</text><text class="small" x="${left}" y="${bottom + 100}">${example.participant}: session ${example.b} | mean HRR ${secondSummary.mean.toFixed(3)}, tHRR-I ${secondSummary.tilted.toFixed(3)}, RPE ${secondSummary.rpe.toFixed(0)}</text>`;
});
body += `<rect x="1030" y="92" width="25" height="25" fill="${C.navy}"/><text x="1070" y="113" class="small">First session in each pair</text><rect x="1315" y="92" width="25" height="25" fill="${C.teal}"/><text x="1355" y="113" class="small">Second session</text><text class="label" x="65" y="525" text-anchor="middle" transform="rotate(-90 65 525)">Proportion of valid session time</text><text class="label" x="880" y="1030" text-anchor="middle">HRR decile</text>`;
await save("Figure_5_equal_mean_examples", frame(1600, 1070, "Similar mean HRR can conceal different intensity distributions", "Two post hoc within-participant examples; tHRR-I used the full-development λ = 6.2", body));

console.log(JSON.stringify({ figures: 5, formats: ["svg", "png", "tiff"] }));
