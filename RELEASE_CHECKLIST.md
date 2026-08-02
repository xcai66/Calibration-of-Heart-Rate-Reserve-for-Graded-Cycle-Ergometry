# Current release checklist

## Completed for v1.2.1

- [x] Clarify that the central round-5 comparison is mean HRR versus mean HRR plus Δtilt with participant-balanced MAE used for inner selection.
- [x] Label the older Spearman-driven formula-family selection as an exploratory sensitivity analysis.
- [x] Re-render and visually inspect all 17 pages of the statistical appendix.
- [x] Confirm that formulas, samples, scripts, figures, and numerical results match the frozen final analysis.
- [x] Publish GitHub release `v1.2.1` and archive the exact release on Zenodo at version DOI `10.5281/zenodo.21742204`.
- [x] Record the version-specific DOI on `main` and synchronize the submission package.

## Final integrity checks

- [x] Rerun PMData from provider-distributed source files with the pinned Python environment.
- [x] Rerun WEEE and Malaga analyses without retuning λ.
- [x] Rebuild and inspect all five main figures and the statistical appendix.
- [x] Confirm that no third-party raw data are included in the release tree.
- [x] Parse-check Python and JSON files and retain the public reproduction report.
- [x] Retain only the maintained `v1.2.1` GitHub release and tag.
