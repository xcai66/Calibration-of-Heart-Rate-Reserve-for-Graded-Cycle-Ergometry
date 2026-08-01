# Release checklist

## Completed for v1.2.1

- [x] Clarify that the central round-5 comparison is mean HRR versus mean HRR plus Δtilt with participant-balanced MAE used for inner selection.
- [x] Label the older Spearman-driven formula-family selection as an exploratory sensitivity analysis.
- [x] Re-render and visually inspect all 17 pages of the statistical appendix.
- [x] Confirm that formulas, samples, scripts, figures, and numerical results are unchanged from v1.2.0.
- [x] Publish GitHub release `v1.2.1` and archive the exact release on Zenodo at version DOI `10.5281/zenodo.21742204`.
- [x] Record the version-specific DOI on `main` and synchronize the submission package.

## Completed for v1.2.0

- [x] Rerun PMData from provider-distributed source files with the pinned Python environment.
- [x] Rerun WEEE and Malaga analyses from provider-distributed source files without retuning λ.
- [x] Rebuild and visually inspect all five main figures.
- [x] Confirm that no third-party raw data are included in the release tree.
- [x] Add a public reproduction report and machine-readable verification record.
- [x] Update release metadata to version 1.2.0 and retain the stable concept DOI across versions.
- [x] Push commit `db4392c`, tag `v1.2.0`, and publish the GitHub release.
- [x] Archive the exact release on Zenodo at version DOI `10.5281/zenodo.21740906`.
- [x] Backfill the version DOI into the repository citation metadata and submission package.

## Completed for v1.1.0

- [x] Confirm that the repository contains no raw PMData, WEEE, or Malaga files.
- [x] Confirm that `CITATION.cff` contains the repository URL and the author spelling "BoTao Cai".
- [x] Freeze the selection-aware PMData analyses, permutation control, strict matching analysis, WEEE repeated-measures analyses, device-agreement audit, synchronization audit, and Malaga sensitivity analyses.
- [x] Rebuild the results workbook, figures, statistical appendix, and manuscript-facing outputs from the frozen results.
- [x] Parse-check all Python and JSON files and audit the repository for oversized or disallowed raw-data files.
- [x] Record the previous release DOI (`10.5281/zenodo.21689575`) and stable concept DOI (`10.5281/zenodo.21689574`).

## Publication actions

- [x] Push the frozen v1.1.0 commit to GitHub.
- [x] Create GitHub release `v1.1.0` from the frozen commit.
- [x] Publish the linked Zenodo archive with version-specific DOI `10.5281/zenodo.21710544`.
- [x] Add the new version-specific DOI to the main branch, manuscript, cover letter, response letter, and Data and Code Availability statement.
- [x] Re-render all Word documents and verify the final PDF pages after DOI insertion (58 pages across five files).
- [x] Re-run repository and submission-package integrity checks before journal submission.
