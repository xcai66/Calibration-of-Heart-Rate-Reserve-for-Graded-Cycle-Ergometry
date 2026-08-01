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
const MAIN = path.resolve(ROOT, "../../../02_Figures");
const REPO_FIGURES = path.join(ROOT, "figures");
for (const directory of [path.join(MAIN, "SVG"), path.join(MAIN, "PNG"), path.join(MAIN, "TIFF"), path.join(REPO_FIGURES, "svg"), path.join(REPO_FIGURES, "png")]) {
  await fs.mkdir(directory, { recursive: true });
}

const parseCsv = async (name) => {
  const lines = (await fs.readFile(path.join(ANALYSIS, name), "utf8")).trim().split(/\r?\n/);
  const header = lines[0].split(",");
  return lines.slice(1).map((line) => Object.fromEntries(line.split(",").map((value, index) => [header[index], value === "" ? null : (Number.isNaN(Number(value)) ? value : Number(value))])));
};

const losses = await parseCsv("reviewer_round5_participant_losses.csv");
const performance = await parseCsv("reviewer_round5_model_performance.csv");
const byModel = Object.fromEntries(performance.map((row) => [row.model, row]));
const C = { navy: "#17365D", teal: "#007C91", orange: "#D97706", red: "#B23A48", ink: "#1F2937", gray: "#6B7280", grid: "#D1D5DB", pale: "#F4F7FA", white: "#FFFFFF" };
const width = 1800;
const height = 980;
let body = `<rect width="100%" height="100%" fill="${C.white}"/>
<style>
text { font-family: Arial, Helvetica, sans-serif; fill: ${C.ink}; }
.title { font-size: 39px; font-weight: 700; }
.subtitle { font-size: 21px; fill: ${C.gray}; }
.panel { font-size: 27px; font-weight: 700; }
.label { font-size: 19px; }
.small { font-size: 17px; fill: ${C.gray}; }
.axis { font-size: 19px; }
</style>
<text class="title" x="75" y="58">Participant-grouped evaluation of incremental HRR-distribution information</text>
<text class="subtitle" x="75" y="94">All parameter and candidate selection occurred inside the outer participant folds</text>`;

body += `<rect x="55" y="125" width="825" height="765" rx="18" fill="${C.pale}" stroke="${C.grid}"/><text class="panel" x="80" y="170">A  Participant-level absolute prediction error</text>`;
const leftX1 = 155, leftX2 = 770, leftY1 = 230, leftY2 = 805;
const yScale = (value) => leftY2 - (value / 3.5) * (leftY2 - leftY1);
for (let tick = 0; tick <= 3.5; tick += 0.5) {
  const y = yScale(tick);
  body += `<line x1="${leftX1}" y1="${y}" x2="${leftX2}" y2="${y}" stroke="${C.grid}"/><text class="small" x="${leftX1 - 18}" y="${y + 6}" text-anchor="end">${tick.toFixed(1)}</text>`;
}
const xBase = 345, xDelta = 610;
losses.forEach((row) => {
  const y1 = yScale(row.mae_base_mean), y2 = yScale(row.mae_delta_tilt_fixed_6_2);
  const favorable = row.mae_delta_tilt_fixed_6_2 < row.mae_base_mean;
  body += `<line x1="${xBase}" y1="${y1}" x2="${xDelta}" y2="${y2}" stroke="${favorable ? C.teal : C.red}" stroke-width="3" opacity="0.68"/><circle cx="${xBase}" cy="${y1}" r="6" fill="${C.navy}"/><circle cx="${xDelta}" cy="${y2}" r="6" fill="${C.teal}"/>`;
});
body += `<text class="axis" x="${xBase}" y="842" text-anchor="middle">Mean HRR</text><text class="axis" x="${xDelta}" y="842" text-anchor="middle">Mean HRR + Δtilt</text><text class="small" x="80" y="872">Fixed λ = 6.2; 10 of 15 participants had lower MAE; teal lines indicate improvement.</text>`;
body += `<text class="axis" x="88" y="535" transform="rotate(-90 88 535)" text-anchor="middle">Participant MAE (RPE units)</text>`;

body += `<rect x="920" y="125" width="825" height="765" rx="18" fill="${C.pale}" stroke="${C.grid}"/><text class="panel" x="945" y="170">B  Difference from mean-HRR baseline</text>`;
const axisL = 1130, axisR = 1670, axisY1 = 230, axisY2 = 765, minX = -0.20, maxX = 0.15;
const xScale = (value) => axisL + (value - minX) / (maxX - minX) * (axisR - axisL);
for (const tick of [-0.20, -0.15, -0.10, -0.05, 0, 0.05, 0.10, 0.15]) {
  const x = xScale(tick);
  body += `<line x1="${x}" y1="${axisY1}" x2="${x}" y2="${axisY2}" stroke="${tick === 0 ? C.ink : C.grid}" stroke-width="${tick === 0 ? 2 : 1}"/><text class="small" x="${x}" y="800" text-anchor="middle">${tick.toFixed(2)}</text>`;
}
const shown = [
  ["variance", "Mean + variance", C.gray],
  ["upper_80", "Mean + time ≥80%", C.orange],
  ["delta_tilt_fixed_6_2", "Mean + Δtilt (fixed)", C.teal],
  ["tilted_standalone_fixed_6_2", "tHRR-I fixed alone", C.navy],
  ["selected_transparent", "Selected transparent", C.red],
];
shown.forEach(([key, label, color], index) => {
  const row = byModel[key];
  const y = 290 + index * 95;
  body += `<text class="label" x="1100" y="${y + 7}" text-anchor="end">${label}</text><line x1="${xScale(row.bootstrap_ci_low)}" y1="${y}" x2="${xScale(row.bootstrap_ci_high)}" y2="${y}" stroke="${color}" stroke-width="7"/><line x1="${xScale(row.bootstrap_ci_low)}" y1="${y - 11}" x2="${xScale(row.bootstrap_ci_low)}" y2="${y + 11}" stroke="${color}" stroke-width="4"/><line x1="${xScale(row.bootstrap_ci_high)}" y1="${y - 11}" x2="${xScale(row.bootstrap_ci_high)}" y2="${y + 11}" stroke="${color}" stroke-width="4"/><circle cx="${xScale(row.mae_difference_vs_base)}" cy="${y}" r="10" fill="${color}"/><text class="small" x="${xScale(row.bootstrap_ci_high) + 10}" y="${y + 7}">${row.mae_difference_vs_base.toFixed(3)}</text>`;
});
body += `<text class="axis" x="1400" y="842" text-anchor="middle">MAE difference (candidate minus mean HRR)</text><text class="small" x="945" y="872">Negative values favor the candidate. Intervals are participant-cluster bootstrap intervals.</text>`;
body += `<text class="small" x="75" y="940">With λ fixed at 6.2, adding Δtilt changed MAE by −0.074 (95% interval −0.155 to 0.002); exact two-sided sign-flip P = 0.098.</text>`;

const svg = `<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">${body}</svg>`;
const name = "Figure_4_incremental_distribution_validation";
for (const file of [path.join(MAIN, "SVG", `${name}.svg`), path.join(REPO_FIGURES, "svg", `${name}.svg`)]) {
  await fs.writeFile(file, svg, "utf8");
}
const source = Buffer.from(svg);
for (const file of [path.join(MAIN, "PNG", `${name}.png`), path.join(REPO_FIGURES, "png", `${name}.png`)]) {
  await sharp(source, { density: 300 }).png({ compressionLevel: 9 }).withMetadata({ density: 300 }).toFile(file);
}
await sharp(source, { density: 300 }).tiff({ compression: "lzw", resolutionUnit: "inch", xres: 300, yres: 300 }).toFile(path.join(MAIN, "TIFF", `${name}.tiff`));
console.log(JSON.stringify({ figure: name, panels: 2 }, null, 2));
