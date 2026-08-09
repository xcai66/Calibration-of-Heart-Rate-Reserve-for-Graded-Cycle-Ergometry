# CycHRR-T v2.0.0

This release supports the manuscript **“Calibration of Heart-Rate Reserve for Graded Cycle Ergometry: An Endpoint-Preserving Transfer Evaluated Against Linear Alternatives.”**

## Scope

CycHRR-T is a bounded, endpoint-preserving group calibration of heart-rate reserve for concurrent intensity estimation during graded cycle ergometry. It is not presented as a general fatigue, recovery, injury-risk, or free-living training-load score.

## Main additions

- Deterministic development and temporal holdout splits.
- Locked-model evaluation against raw HRR and strong development-fitted linear comparators.
- External laboratory-task validation using the ACTES graded-cycloergometer dataset without refitting.
- Complete-unit bootstrap uncertainty, endpoint-exclusion, intensity-band, practical-agreement, time-offset, parameter-sensitivity, and heart-rate-anchor analyses.
- Bilingual manuscripts, submission figures, source-data workbook, formula application utility, and implementation tests.

## Principal result

In 84 temporally held-out cycling test files, CycHRR-T reduced complete-test VO2R mean absolute error from 0.0617 for raw HRR to 0.0510 and increased exact 10% VO2R-band agreement from 50.9% to 59.7%. Performance was similar to development-fitted linear calibration for the primary target, so the release frames CycHRR-T as an interpretable endpoint-preserving calibration rather than a universally superior nonlinear model.

## Licensing and provenance

Analysis code is MIT licensed. Redistributed third-party source data retain the licenses stated in `01_sources/DATA_PROVENANCE_AND_LICENSES.md`. The stable software archive is maintained under Zenodo concept DOI `10.5281/zenodo.21689574`.
