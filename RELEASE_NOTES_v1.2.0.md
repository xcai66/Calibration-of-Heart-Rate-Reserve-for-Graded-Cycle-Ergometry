# Release notes: v1.2.0

This release freezes the statistical-strengthening revision and the source-to-result reproduction audit completed on 1 August 2026.

## Added

- `reviewer_round5_analysis.py` with direct nested comparison of mean HRR versus mean HRR plus Δtilt.
- Participant-balanced inner selection by MAE, participant-level paired losses, 5,000 participant-cluster bootstrap intervals, exact sign-flip tests, and leave-one-participant influence ranges.
- Transparent distribution comparators: variance, upper-zone time, and upper-tail area.
- A selection-aware transparent outer pipeline retaining all candidate results regardless of direction.
- PMData sequential and rule-specific sample-flow reconciliation.
- `reviewer_round5_weee_agreement.py` with participant-balanced concordance, repeated-measures limits of agreement, and stage-specific attrition.
- Revised Figure 4, Figure 5, statistical appendix tables S27-S30, and results-workbook sheets.

## Model decision

The ten-bin tHRR-I formula is retained without further outcome-guided modification. λ=6.2 is frozen as the transportable research candidate for the next independent study. This is a model-freezing decision, not evidence that 6.2 is universally optimal.

## Main revised results

- Fully nested mean HRR plus Δtilt: MAE 1.232 versus 1.302 for mean HRR; ΔMAE -0.070 (-0.165 to 0.035), exact P=0.228, 11/15 participants favoring augmentation.
- Fixed λ=6.2 incremental sensitivity: ΔMAE -0.074 (-0.155 to 0.002).
- Stand-alone fixed tHRR-I: ΔMAE -0.074 (-0.133 to -0.017), exact P=0.030; this does not isolate incremental distribution information.
- Zephyr tHRR-I participant-balanced CCC 0.846 (0.654 to 0.946), bias -0.025 (-0.044 to -0.001), repeated-measures limits -0.262 to 0.213.
- WEEE high-running-stage retention 3/16 (18.8%).

## Reproduction verification

The PMData and external-validation pipelines were rerun from provider-distributed source files with Python 3.12.13 and the exact packages in `requirements.txt`. The complete runs exited successfully and reproduced the frozen estimates. All five main figures were regenerated. `reproduction/REPRODUCTION_REPORT_2026-08-01.md` records the verification boundary and result fingerprints.
