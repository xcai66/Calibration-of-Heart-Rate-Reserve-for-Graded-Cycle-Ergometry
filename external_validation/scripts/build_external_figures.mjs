import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const sharp = require(path.join(process.env.CODEX_NODE_MODULES, "sharp"));
const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const PACKAGE = path.resolve(ROOT, "../..");
const RESULTS = path.join(ROOT, "results");
const OUT = path.join(ROOT, "figures");
const MAIN = path.join(PACKAGE, "02_Figures");
for (const directory of [OUT, path.join(MAIN, "SVG"), path.join(MAIN, "PNG"), path.join(MAIN, "TIFF")]) {
  await fs.mkdir(directory, { recursive: true });
}

const parseJson = async (name) => JSON.parse((await fs.readFile(path.join(RESULTS, name), "utf8")).replaceAll("NaN", "null"));
const weee = await parseJson("weee_external_summary.json");
const malaga = await parseJson("malaga_external_summary.json");
const malagaSensitivity = await parseJson("malaga_sensitivity_summary.json");
const C = { navy: "#17365D", teal: "#007C91", orange: "#D97706", red: "#B23A48", ink: "#1F2937", gray: "#6B7280", grid: "#D1D5DB", pale: "#F4F7FA", white: "#FFFFFF" };
const repeated = Object.fromEntries(weee.repeated_measures_association.map((row) => [`${row.scale}_${row.association}`, row]));
const agreement = Object.fromEntries(weee.device_agreement.filter((row) => row.device === "zephyr").map((row) => [row.score, row]));
const agreementCI = Object.fromEntries(weee.device_agreement_intervals.filter((row) => row.device === "zephyr").map((row) => [row.score, row]));
const wPerf = Object.fromEntries(weee.construct_performance.map((row) => [`${row.model}_${row.metric}`, row.estimate]));
const wComp = Object.fromEntries(weee.construct_comparison.map((row) => [row.metric, row]));
const mPerf = Object.fromEntries(malaga.performance.map((row) => [`${row.model}_${row.metric}`, row.estimate]));
const recoverySensitivity = malagaSensitivity.endpoint_sensitivity.filter((row) => row.baseline_method === "recovery_min" && row.smoothing_seconds === 15);
const primaryRecovery = recoverySensitivity.find((row) => row.window_seconds === 180);

const width = 1800;
const height = 1140;
let body = `<rect width="100%" height="100%" fill="${C.white}"/>
<style>
text { font-family: Arial, Helvetica, sans-serif; fill: ${C.ink}; }
.title { font-size: 40px; font-weight: 700; }
.subtitle { font-size: 22px; fill: ${C.gray}; }
.panel { font-size: 27px; font-weight: 700; }
.label { font-size: 21px; }
.small { font-size: 18px; fill: ${C.gray}; }
.number { font-size: 25px; font-weight: 700; }
</style>
<text class="title" x="80" y="62">Locked external evaluation of tHRR-I (λ = 6.2)</text>
<text class="subtitle" x="80" y="100">Participant-level dependence was retained; no external parameter retuning was performed</text>`;

const rows = [["mean_hrr", "Mean HRR", C.navy], ["thrr_i", "tHRR-I", C.teal], ["delta_tilt", "Δtilt", C.orange]];
body += `<rect x="65" y="135" width="820" height="445" rx="18" fill="${C.pale}" stroke="${C.grid}"/><text class="panel" x="90" y="178">A  WEEE association with stage VO₂</text>`;
const axL = 330, axR = 820, axY = 505;
for (let tick = 0; tick <= 1.0001; tick += 0.2) {
  const x = axL + tick * (axR - axL);
  body += `<line x1="${x}" y1="225" x2="${x}" y2="${axY}" stroke="${C.grid}"/><text class="small" x="${x}" y="${axY + 30}" text-anchor="middle">${tick.toFixed(1)}</text>`;
}
rows.forEach(([key, label, color], index) => {
  const row = repeated[`within_participant_pearson_${key}`];
  const y = 275 + index * 82;
  const x = (value) => axL + value * (axR - axL);
  body += `<text class="label" x="300" y="${y + 7}" text-anchor="end">${label}</text><line x1="${x(row.ci_low)}" y1="${y}" x2="${x(row.ci_high)}" y2="${y}" stroke="${color}" stroke-width="7"/><line x1="${x(row.ci_low)}" y1="${y - 11}" x2="${x(row.ci_low)}" y2="${y + 11}" stroke="${color}" stroke-width="4"/><line x1="${x(row.ci_high)}" y1="${y - 11}" x2="${x(row.ci_high)}" y2="${y + 11}" stroke="${color}" stroke-width="4"/><circle cx="${x(row.estimate)}" cy="${y}" r="10" fill="${color}"/><text class="small" x="${x(row.ci_high) + 10}" y="${y + 7}">${row.estimate.toFixed(3)}</text>`;
});
body += `<text class="small" x="90" y="560">Participant-demeaned Pearson r; cluster-bootstrap 95% CIs; 77 stages, 16 participants.</text>`;

body += `<rect x="915" y="135" width="820" height="445" rx="18" fill="${C.pale}" stroke="${C.grid}"/><text class="panel" x="940" y="178">B  Incremental prediction beyond mean HRR</text>`;
body += `<text class="label" x="955" y="232">WEEE VO₂, leave-one-participant-out</text><text class="number" x="955" y="272">MAE ${wPerf.base_mae.toFixed(3)} → ${wPerf.augmented_mae.toFixed(3)} mL·kg⁻¹·min⁻¹</text><text class="small" x="955" y="306">ΔMAE +${wComp.mae.estimate.toFixed(3)} (95% CI ${wComp.mae.ci_low.toFixed(3)} to ${wComp.mae.ci_high.toFixed(3)})</text>`;
body += `<line x1="950" y1="337" x2="1700" y2="337" stroke="${C.grid}"/><text class="label" x="955" y="386">Malaga 180-s excess recovery VO₂</text><text class="number" x="955" y="426">MAE ${mPerf.base_participant_balanced_mae.toFixed(1)} → ${mPerf.augmented_participant_balanced_mae.toFixed(1)} mL</text><text class="small" x="955" y="460">ΔMAE +${primaryRecovery.mae_difference_augmented_minus_base.toFixed(3)} (95% CI ${primaryRecovery.ci_low.toFixed(3)} to ${primaryRecovery.ci_high.toFixed(3)})</text><text class="small" x="955" y="525">Positive ΔMAE favors the base model; both intervals include zero.</text>`;

body += `<rect x="65" y="610" width="820" height="455" rx="18" fill="${C.pale}" stroke="${C.grid}"/><text class="panel" x="90" y="653">C  Zephyr-to-reference absolute agreement</text>`;
const iccL = 330, iccR = 815;
for (let tick = 0; tick <= 1.0001; tick += 0.2) {
  const x = iccL + tick * (iccR - iccL);
  body += `<line x1="${x}" y1="700" x2="${x}" y2="935" stroke="${C.grid}"/><text class="small" x="${x}" y="965" text-anchor="middle">${tick.toFixed(1)}</text>`;
}
rows.forEach(([key, label, color], index) => {
  const value = agreement[key];
  const interval = agreementCI[key];
  const y = 750 + index * 80;
  const x = (number) => iccL + Math.max(0, Math.min(1, number)) * (iccR - iccL);
  body += `<text class="label" x="300" y="${y + 7}" text-anchor="end">${label}</text><line x1="${x(interval.icc_a1_ci_low)}" y1="${y}" x2="${x(interval.icc_a1_ci_high)}" y2="${y}" stroke="${color}" stroke-width="7"/><circle cx="${x(value.icc_a1)}" cy="${y}" r="10" fill="${color}"/><text class="small" x="${x(interval.icc_a1_ci_high) + 10}" y="${y + 7}">${value.icc_a1.toFixed(3)}</text>`;
});
body += `<text class="small" x="90" y="1010">ICC(A,1), participant-cluster 95% CIs; 77 paired stages from 16 participants.</text><text class="small" x="90" y="1038">tHRR-I bias −0.026; 95% limits of agreement −0.257 to 0.205 HRR units.</text>`;

body += `<rect x="915" y="610" width="820" height="455" rx="18" fill="${C.pale}" stroke="${C.grid}"/><text class="panel" x="940" y="653">D  Malaga recovery-window sensitivity</text>`;
const sxL = 1130, sxR = 1685, sMin = -3, sMax = 3;
const sx = (value) => sxL + (value - sMin) / (sMax - sMin) * (sxR - sxL);
for (const tick of [-3, -2, -1, 0, 1, 2, 3]) {
  const x = sx(tick);
  body += `<line x1="${x}" y1="700" x2="${x}" y2="950" stroke="${tick === 0 ? C.ink : C.grid}" stroke-width="${tick === 0 ? 2 : 1}"/><text class="small" x="${x}" y="980" text-anchor="middle">${tick}</text>`;
}
recoverySensitivity.forEach((row, index) => {
  const y = 750 + index * 85;
  body += `<text class="label" x="1100" y="${y + 7}" text-anchor="end">${row.window_seconds} s</text><line x1="${sx(row.ci_low)}" y1="${y}" x2="${sx(row.ci_high)}" y2="${y}" stroke="${C.orange}" stroke-width="7"/><circle cx="${sx(row.mae_difference_augmented_minus_base)}" cy="${y}" r="10" fill="${C.orange}"/><text class="small" x="${sx(row.ci_high) + 10}" y="${y + 7}">${row.mae_difference_augmented_minus_base >= 0 ? "+" : ""}${row.mae_difference_augmented_minus_base.toFixed(3)}</text>`;
});
body += `<text class="small" x="940" y="1010">ΔMAE (mL), augmented minus base; recovery-min baseline and 15-s smoothing.</text><text class="small" x="940" y="1038">All reviewer-requested sensitivity variants are reported in Supplementary Table S18.</text>`;
body += `<text class="small" x="80" y="1110">Associations describe construct convergence. Incremental prediction asks a distinct question and was not demonstrated.</text>`;

const svg = `<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">${body}</svg>`;
const name = "Figure_6_external_construct_validation";
await fs.writeFile(path.join(OUT, `${name}.svg`), svg, "utf8");
await fs.writeFile(path.join(MAIN, "SVG", `${name}.svg`), svg, "utf8");
const source = Buffer.from(svg);
await sharp(source, { density: 300 }).png({ compressionLevel: 9 }).withMetadata({ density: 300 }).toFile(path.join(OUT, `${name}.png`));
await sharp(source, { density: 300 }).png({ compressionLevel: 9 }).withMetadata({ density: 300 }).toFile(path.join(MAIN, "PNG", `${name}.png`));
await sharp(source, { density: 300 }).tiff({ compression: "lzw", resolutionUnit: "inch", xres: 300, yres: 300 }).toFile(path.join(OUT, `${name}.tiff`));
await sharp(source, { density: 300 }).tiff({ compression: "lzw", resolutionUnit: "inch", xres: 300, yres: 300 }).toFile(path.join(MAIN, "TIFF", `${name}.tiff`));
console.log(JSON.stringify({ figure: name, panels: 4, lambda_locked: 6.2 }, null, 2));
