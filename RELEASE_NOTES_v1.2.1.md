# Release notes: v1.2.1

This patch release corrects the analysis hierarchy described in the statistical appendix.

## Corrected

- The principal round-5 comparison is now consistently described as participant-balanced outer-fold MAE for binned mean HRR versus binned mean HRR plus Δtilt.
- Inner λ selection is consistently described as participant-grouped leave-one-participant-out validation minimizing participant-balanced MAE.
- The earlier Spearman-driven formula-family selection is explicitly retained as an exploratory sensitivity analysis rather than the central comparison.

## Unchanged

- tHRR-I and Δtilt formulas
- PMData, WEEE, and Malaga sample definitions
- Analysis scripts and random seeds
- Figures and machine-readable results
- All reported numerical estimates, intervals, and exact P values

The release continues to preserve favorable, null, and unfavorable comparator results. Third-party raw data are not redistributed.
