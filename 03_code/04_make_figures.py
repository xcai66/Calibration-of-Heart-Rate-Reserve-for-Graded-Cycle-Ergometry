#!/usr/bin/env python3
"""Create submission-grade manuscript figures from analysis outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
import pandas as pd


COLORS = {
    "raw_linear": "#777777",
    "scaled_linear": "#B7C9D6",
    "affine_linear": "#78A9C4",
    "cycling_tail": "#1E5A8A",
    "accent": "#2F8F6B",
    "warning": "#C86B4A",
    "grid": "#D9DEE3",
    "text": "#202124",
}

FIGURE_WIDTH_MM = 183


def configure():
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 7,
        "axes.titlesize": 8,
        "axes.labelsize": 7,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "legend.fontsize": 6.5,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "axes.linewidth": 0.7,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
    })


def bootstrap_mean_ci(values, seed=20260808, n_boot=10000):
    values = np.asarray(values, dtype=float)
    rng = np.random.RandomState(seed)
    sample = values[rng.randint(0, len(values), size=(n_boot, len(values)))].mean(axis=1)
    return float(values.mean()), float(np.quantile(sample, 0.025)), float(np.quantile(sample, 0.975))


def save_figure(fig, base):
    fig.savefig(base.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(base.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(base.with_suffix(".tiff"), dpi=600, bbox_inches="tight")
    fig.savefig(base.with_suffix(".png"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def panel_label(ax, label):
    ax.text(-0.10, 1.12, label, transform=ax.transAxes, fontsize=8, fontweight="bold", va="top")


def make_figure1(tables, out, source):
    per = pd.read_csv(tables / "development_grouped_cv_per_test.csv")
    rows = []
    sport_order = ["Cycling", "Running", "Rowing", "Kayak"]
    for sport in sport_order:
        subset = per[(per["sport"] == sport) & (per["target"] == "vo2r")]
        raw = subset[subset["family"] == "linear"][["file", "mae"]].rename(columns={"mae": "raw"})
        tail = subset[subset["family"] == "tail"][["file", "mae"]].rename(columns={"mae": "tail"})
        paired = raw.merge(tail, on="file")
        relative = 100 * (paired["raw"] - paired["tail"]) / paired["raw"].mean()
        mean, low, high = bootstrap_mean_ci(relative, seed=20260808 + len(rows))
        rows.append({"sport": sport, "n_tests": len(paired), "relative_mae_reduction_percent": mean, "ci_low": low, "ci_high": high})
    sport_source = pd.DataFrame(rows)
    sport_source.to_csv(source / "figure1_sport_selection.csv", index=False)

    fig = plt.figure(figsize=(FIGURE_WIDTH_MM / 25.4, 78 / 25.4))
    grid = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.25], wspace=0.34)
    ax = fig.add_subplot(grid[0, 0])
    y = np.arange(len(sport_order))
    values = sport_source.set_index("sport").loc[sport_order, "relative_mae_reduction_percent"].to_numpy()
    low = sport_source.set_index("sport").loc[sport_order, "ci_low"].to_numpy()
    high = sport_source.set_index("sport").loc[sport_order, "ci_high"].to_numpy()
    colors = [COLORS["cycling_tail"]] + ["#AEB8C1"] * 3
    ax.barh(y, values, color=colors, height=0.60, edgecolor="none")
    ax.errorbar(values, y, xerr=[values - low, high - values], fmt="none", ecolor=COLORS["text"], elinewidth=0.8, capsize=2)
    n_by_sport = sport_source.set_index("sport")["n_tests"].to_dict()
    ax.set_yticks(y, [f"{sport} (n={int(n_by_sport[sport])})" for sport in sport_order])
    ax.invert_yaxis()
    ax.set_xlabel("Reduction in VO$_2$R MAE vs raw HRR (%)")
    ax.axvline(0, color=COLORS["text"], lw=0.7)
    ax.grid(axis="x", color=COLORS["grid"], lw=0.5)
    ax.set_axisbelow(True)
    ax.set_title("Development-only grouped cross-validation", loc="left", fontweight="bold")
    panel_label(ax, "a")

    ax2 = fig.add_subplot(grid[0, 1])
    ax2.axis("off")
    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1)
    boxes = [
        (0.02, 0.57, 0.20, 0.26, "Four sports\n819 valid tests", "#EEF2F5"),
        (0.28, 0.57, 0.20, 0.26, "Earlier 70%\nmodel selection", "#E8F0F6"),
        (0.54, 0.57, 0.18, 0.26, "Lock transfer\nτ=0.90, κ=5.75", "#DCEAF4"),
        (0.78, 0.57, 0.20, 0.26, "Latest 30%\n84 test files", "#D5E4EF"),
        (0.54, 0.12, 0.18, 0.22, "No refitting", "#F3F5F7"),
        (0.78, 0.10, 0.20, 0.26, "ACTES external\n18 participants", "#DDEEE8"),
    ]
    for x, y0, w, h, text, face in boxes:
        patch = FancyBboxPatch((x, y0), w, h, boxstyle="round,pad=0.012,rounding_size=0.02", fc=face, ec="#A8B2BA", lw=0.7)
        ax2.add_patch(patch)
        ax2.text(x + w / 2, y0 + h / 2, text, ha="center", va="center", fontsize=6.8, linespacing=1.25)
    arrows = [((0.22, 0.70), (0.28, 0.70)), ((0.48, 0.70), (0.54, 0.70)), ((0.72, 0.70), (0.78, 0.70)), ((0.63, 0.57), (0.63, 0.34)), ((0.72, 0.23), (0.78, 0.23))]
    for start, end in arrows:
        ax2.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=8, lw=0.8, color="#66717A"))
    ax2.text(0.02, 0.94, "Sealed development and validation sequence", fontsize=8, fontweight="bold", va="top")
    ax2.text(0.02, 0.04, "Final validation was opened only after sport, family and parameters were fixed.", fontsize=6.4, color="#4A535A")
    panel_label(ax2, "b")
    save_figure(fig, out / "Figure_1_Study_design_and_sport_selection")


def make_figure2(tables, out, source):
    per = pd.read_csv(tables / "strong_comparator_per_unit.csv")
    per = per[per["representation"] == "continuous"].copy()
    settings = [
        ("Graded-test temporal holdout", "vo2r", "Temporal\nVO$_2$R"),
        ("Graded-test temporal holdout", "load_fraction", "Temporal\nload fraction"),
        ("ACTES external validation", "vo2r", "External\nVO$_2$R"),
        ("ACTES external validation", "power_fraction", "External\npower fraction"),
    ]
    models = ["raw_linear", "scaled_linear", "affine_linear", "cycling_tail"]
    rows = []
    for dataset, target, label in settings:
        block = per[(per["dataset"] == dataset) & (per["target"] == target)]
        for j, model in enumerate(models):
            mean, low, high = bootstrap_mean_ci(block[model], seed=20260820 + len(rows))
            rows.append({"dataset": dataset, "target": target, "label": label, "model": model, "mae": mean, "ci_low": low, "ci_high": high, "n_units": len(block)})
    bar_source = pd.DataFrame(rows)
    bar_source.to_csv(source / "figure2_validation_mae.csv", index=False)
    h = np.linspace(0, 1, 501)
    g = (h + 5.75 * np.maximum(h - 0.90, 0) ** 2) / (1 + 5.75 * 0.10**2)
    pd.DataFrame({"hrr": h, "raw_identity": h, "cycling_transfer": g}).to_csv(source / "figure2_transfer_curve.csv", index=False)

    fig = plt.figure(figsize=(FIGURE_WIDTH_MM / 25.4, 86 / 25.4))
    grid = fig.add_gridspec(1, 2, width_ratios=[0.78, 1.45], wspace=0.32)
    ax = fig.add_subplot(grid[0, 0])
    ax.plot(h, h, color=COLORS["raw_linear"], lw=1.4, ls="--", label="Raw HRR")
    ax.plot(h, g, color=COLORS["cycling_tail"], lw=1.8, label="CycHRR-T")
    ax.axvline(0.90, color=COLORS["warning"], lw=0.8, ls=":")
    ax.text(0.90, 0.15, "tail threshold\nτ=0.90", ha="right", va="bottom", fontsize=6.2, color=COLORS["warning"])
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="Heart-rate reserve, h", ylabel="Transformed intensity, g(h)")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(color=COLORS["grid"], lw=0.5)
    ax.legend(loc="upper left")
    ax.set_title("Locked endpoint-preserving transfer", loc="left", fontweight="bold")
    panel_label(ax, "a")

    ax2 = fig.add_subplot(grid[0, 1])
    x = np.arange(len(settings))
    width = 0.18
    offsets = np.linspace(-1.5 * width, 1.5 * width, len(models))
    labels = {"raw_linear": "Raw HRR", "scaled_linear": "Scaled linear", "affine_linear": "Affine linear", "cycling_tail": "CycHRR-T"}
    for model, offset in zip(models, offsets):
        block = bar_source[bar_source["model"] == model].set_index("label")
        ordered_labels = [item[2] for item in settings]
        vals = block.loc[ordered_labels, "mae"].to_numpy()
        lows = block.loc[ordered_labels, "ci_low"].to_numpy()
        highs = block.loc[ordered_labels, "ci_high"].to_numpy()
        ax2.bar(x + offset, vals, width, color=COLORS[model], label=labels[model], edgecolor="none")
        ax2.errorbar(x + offset, vals, yerr=[vals - lows, highs - vals], fmt="none", ecolor="#333333", elinewidth=0.6, capsize=1.5)
    tick_labels = []
    for item in settings:
        n = int(bar_source[bar_source["label"] == item[2]]["n_units"].iloc[0])
        tick_labels.append(f"{item[2]}\n(n={n})")
    ax2.set_xticks(x, tick_labels)
    ax2.set_ylabel("Mean absolute error")
    ax2.set_ylim(0, 0.13)
    ax2.grid(axis="y", color=COLORS["grid"], lw=0.5)
    ax2.set_axisbelow(True)
    ax2.legend(ncol=2, loc="upper left", columnspacing=1.0, handlelength=1.6)
    ax2.set_title("Temporal and independent validation", loc="left", fontweight="bold")
    panel_label(ax2, "b")
    save_figure(fig, out / "Figure_2_Locked_transfer_and_validation")


def make_figure3(tables, out, source):
    settings = [
        ("Graded-test temporal holdout", "vo2r", "Temporal\nVO$_2$R"),
        ("Graded-test temporal holdout", "load_fraction", "Temporal\nload"),
        ("ACTES external validation", "vo2r", "External\nVO$_2$R"),
        ("ACTES external validation", "power_fraction", "External\npower"),
    ]
    band = pd.read_csv(tables / "intensity_band_summary.csv")
    band = band[band["comparator"] == "scaled_linear"].copy()
    endpoint = pd.read_csv(tables / "endpoint_exclusion_summary.csv")
    endpoint = endpoint[(endpoint["comparator"] == "scaled_linear") & endpoint["scenario"].isin([
        "all observations", "exclude each unit target maximum"
    ])].copy()
    bins = pd.read_csv(tables / "ten_percent_bin_agreement_summary.csv")
    bins = bins[bins["model"].isin(["raw_hrr", "scaled_linear", "cychrr_t"])].copy()
    sens = pd.read_csv(tables / "anchor_sensitivity.csv")
    band.to_csv(source / "figure3_intensity_bands.csv", index=False)
    endpoint.to_csv(source / "figure3_endpoint_exclusion.csv", index=False)
    bins.to_csv(source / "figure3_bin_agreement.csv", index=False)
    sens.to_csv(source / "figure3_anchor_sensitivity.csv", index=False)

    fig = plt.figure(figsize=(FIGURE_WIDTH_MM / 25.4, 150 / 25.4))
    grid = fig.add_gridspec(2, 2, hspace=0.48, wspace=0.38)
    ax = fig.add_subplot(grid[0, 0])
    band_order = ["<0.60", "0.60-<0.80", "0.80-<0.90", ">=0.90"]
    markers = ["o", "s", "^", "D"]
    line_colors = ["#1E5A8A", "#5B8FA8", "#2F8F6B", "#8E6C9F"]
    for (dataset, target, label), marker, color in zip(settings, markers, line_colors):
        block = band[(band["dataset"] == dataset) & (band["target"] == target)].set_index("hrr_band").loc[band_order]
        x = np.arange(len(band_order))
        center = block["delta_mae_tail_minus_comparator"].to_numpy()
        low = block["delta_ci_low"].to_numpy()
        high = block["delta_ci_high"].to_numpy()
        ax.errorbar(x, center, yerr=[center-low, high-center], marker=marker, ms=3.5, lw=1.0,
                    capsize=1.5, color=color, label=label.replace("\n", " "))
    ax.axhline(0, color=COLORS["warning"], lw=0.8, ls="--")
    ax.set_xticks(range(len(band_order)), band_order)
    ax.set_xlabel("Observed HRR band")
    ax.set_ylabel("MAE difference\nCycHRR-T minus scaled linear")
    ax.grid(axis="y", color=COLORS["grid"], lw=0.5)
    ax.set_axisbelow(True)
    ax.legend(fontsize=5.6, ncol=2, loc="lower left")
    ax.set_title("Intensity-specific comparison", loc="left", fontweight="bold")
    panel_label(ax, "a")

    ax2 = fig.add_subplot(grid[0, 1])
    x = np.arange(len(settings))
    width = 0.28
    scenarios = ["all observations", "exclude each unit target maximum"]
    scenario_labels = ["All observations", "Target maximum removed"]
    for j, (scenario, scenario_label) in enumerate(zip(scenarios, scenario_labels)):
        vals, lows, highs = [], [], []
        for dataset, target, _ in settings:
            row = endpoint[(endpoint["dataset"] == dataset) & (endpoint["target"] == target) & (endpoint["scenario"] == scenario)].iloc[0]
            vals.append(row["delta_mae_tail_minus_comparator"])
            lows.append(row["delta_ci_low"])
            highs.append(row["delta_ci_high"])
        vals, lows, highs = map(np.asarray, [vals, lows, highs])
        pos = x + (j - 0.5) * width
        ax2.errorbar(pos, vals, yerr=[vals-lows, highs-vals], fmt="o", ms=4, capsize=2,
                     color=[COLORS["cycling_tail"], COLORS["accent"]][j], label=scenario_label)
    ax2.axhline(0, color=COLORS["warning"], lw=0.8, ls="--")
    ax2.set_xticks(x, [s[2] for s in settings])
    ax2.set_ylabel("MAE difference\nCycHRR-T minus scaled linear")
    ax2.grid(axis="y", color=COLORS["grid"], lw=0.5)
    ax2.set_axisbelow(True)
    ax2.legend(fontsize=5.8, loc="lower left")
    ax2.set_title("Endpoint-exclusion audit", loc="left", fontweight="bold")
    panel_label(ax2, "b")

    ax3 = fig.add_subplot(grid[1, 0])
    models = ["raw_hrr", "scaled_linear", "cychrr_t"]
    model_labels = ["Raw HRR", "Scaled linear", "CycHRR-T"]
    model_colors = [COLORS["raw_linear"], COLORS["scaled_linear"], COLORS["cycling_tail"]]
    width = 0.23
    for j, (model, model_label, color) in enumerate(zip(models, model_labels, model_colors)):
        values = []
        for dataset, target, _ in settings:
            row = bins[(bins["dataset"] == dataset) & (bins["target"] == target) & (bins["model"] == model)].iloc[0]
            values.append(row["exact_10pct_bin_agreement"])
        ax3.bar(np.arange(len(settings)) + (j-1)*width, values, width, color=color, label=model_label, edgecolor="none")
    ax3.set_xticks(np.arange(len(settings)), [s[2] for s in settings])
    ax3.set_ylim(0, 0.70)
    ax3.set_ylabel("Exact 10% band agreement")
    ax3.grid(axis="y", color=COLORS["grid"], lw=0.5)
    ax3.set_axisbelow(True)
    ax3.legend(fontsize=5.8, ncol=3, loc="upper center")
    ax3.set_title("Practical intensity-band agreement", loc="left", fontweight="bold")
    panel_label(ax3, "c")

    ax4 = fig.add_subplot(grid[1, 1])
    pivot = sens.pivot(index="resting_hr_shift_bpm", columns="max_hr_shift_bpm", values="delta_mae").sort_index(ascending=False)
    image = ax4.imshow(pivot.to_numpy(), cmap="RdBu_r", vmin=-0.022, vmax=0.022, aspect="auto")
    ax4.set_xticks(range(len(pivot.columns)), [f"{int(v):+d}" for v in pivot.columns])
    ax4.set_yticks(range(len(pivot.index)), [f"{int(v):+d}" for v in pivot.index])
    ax4.set_xlabel("Maximal-HR shift (beats/min)")
    ax4.set_ylabel("Resting-HR shift (beats/min)")
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            value = pivot.iloc[i, j]
            ax4.text(j, i, f"{value:+.3f}", ha="center", va="center", fontsize=6.2, color="white" if abs(value) > 0.011 else "#222222")
    cbar = fig.colorbar(image, ax=ax4, fraction=0.050, pad=0.04)
    cbar.set_label("Tail minus raw MAE")
    ax4.set_title("HR-anchor sensitivity", loc="left", fontweight="bold")
    panel_label(ax4, "d")
    save_figure(fig, out / "Figure_3_Boundary_and_practical_robustness")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.output / "source_data"
    source.mkdir(parents=True, exist_ok=True)
    configure()
    make_figure1(args.tables, args.output, source)
    make_figure2(args.tables, args.output, source)
    make_figure3(args.tables, args.output, source)


if __name__ == "__main__":
    main()
