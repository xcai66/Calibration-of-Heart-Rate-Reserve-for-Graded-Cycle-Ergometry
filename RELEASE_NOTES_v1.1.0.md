# tHRR-I-PMData v1.1.0

This release expands the reproducible evidence package for the bounded, tail-sensitive heart-rate-reserve distribution index (tHRR-I). It does not change the frozen ten-bin score definition or the externally evaluated value of lambda (6.2).

## Added

- Selection-aware outer leave-one-participant-out analysis that repeats formula-family and parameter selection inside each training fold.
- A stricter PMData session-matching analysis and a within-participant circular label-permutation negative control.
- Participant-cluster bootstrap intervals and repeated grouped-split sensitivity analyses.
- WEEE repeated-measures oxygen-uptake associations, incremental prediction analyses, chest-device agreement, synchronization checks, and anchor sensitivity analyses.
- University of Malaga recovery-endpoint analyses across the prespecified 180-second outcome and additional endpoint and anchor variants.
- Updated tables, figures, statistical appendix, and reviewer-response materials.

## Interpretation

PMData provides exploratory method-development evidence. WEEE supports convergence with oxygen uptake and wearable/chest-device reproducibility, but tHRR-I does not materially outperform mean HRR for the evaluated oxygen-uptake outcomes. Malaga analyses show no stable incremental prediction of recovery oxygen uptake after mean HRR and covariates. The index should therefore be treated as a candidate retrospective session-review descriptor, not a validated prescription, alert threshold, clinical measure, or injury-prevention tool.

## Data policy

No raw third-party data are redistributed. Users must obtain PMData, WEEE, and Malaga source files from the original providers and comply with their terms. The release contains code, manifests, derived non-identifying analysis outputs, figures, and documentation.
