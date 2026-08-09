# Figure contract

## Figure 1

- Core conclusion: graded cycle ergometry was selected before final validation because it combined a sizeable development benefit, 195 development test files, an untouched temporal holdout, and an external cycling task.
- Archetype: schematic-led composite.
- Final size: 183 mm wide.
- Panel a: development-only nonlinear improvement by sport with test-level bootstrap intervals.
- Panel b: data-separation and parameter-lock workflow.
- Interpretive risk: post-selection use of holdout data. The panel shows the sealed split and lock explicitly.

## Figure 2

- Core conclusion: the locked endpoint-preserving transfer reduces error relative to raw HRR, while fitted linear models prevent an unsupported claim of nonlinear superiority.
- Archetype: quantitative grid with a transfer-curve explainer.
- Final size: 183 mm wide.
- Panel a: identity mapping and locked transfer curve.
- Panel b: model MAE with 95% cluster-bootstrap intervals across four continuous-target settings.
- Interpretive risk: a weak baseline could inflate the claim. Scaled and affine linear comparators are shown.

## Figure 3

- Core conclusion: incremental value beyond scaled linear calibration varies by intensity and endpoint inclusion, while practical band agreement and HR-anchor failure regions define application boundaries.
- Archetype: quantitative robustness grid.
- Final size: 183 mm wide.
- Panel a: intensity-specific CycHRR-T minus scaled-linear MAE differences.
- Panel b: full-data and maximum-target-excluded comparisons.
- Panel c: exact 10% target-band agreement.
- Panel d: resting/maximal HR anchor sensitivity.
- Interpretive risk: endpoint normalization, hidden high-intensity failures, and inflated practical interpretation. The figure exposes all three rather than averaging them away.

## Shared export contract

- Backend: Python/matplotlib only.
- Outputs: SVG with editable text, PDF with TrueType text, 600 dpi TIFF, and PNG preview.
- Palette: neutral grey for raw HRR, light blue/grey for fitted linear models, dark blue for CycHRR-T, green only for improvement.
- Source data: CSV files generated beside the figures.
