# Statistical reporting audit

Audit date: 2026-08-08

## Design and independent units

- The complete graded test is the analysis unit for the main public dataset.
- The ACTES participant is the external-validation unit.
- Stage rows and 10-second bins are nested observations and are not counted as independent replicates.
- Model fitting uses inverse stage-count weights so that each development test contributes equally.
- The main source has no stable participant identifier. Possible repeated tests and development-holdout participant overlap cannot be resolved. All intervals therefore condition on test-level independence.

## Data separation

- Chronological splits were created before model comparison: earlier 70% development, latest 30% holdout within sport.
- Candidate sport, function family, and parameters were chosen using development data only.
- The temporal cycling holdout contained 84 tests and was not used for tuning.
- ACTES contained 18 participants and was processed after model lock.
- The internal lock was not an externally time-stamped preregistration. The analysis is classified as exploratory methods development with held-out validation.

## Primary estimand

Mean of complete-test VO2R MAE differences:

`CycHRR-T MAE − raw HRR MAE`

Negative values favor CycHRR-T. This estimand is paired at the complete-test level.

## Primary result

- Raw HRR MAE: 0.0616979.
- CycHRR-T MAE: 0.0509500.
- Difference: −0.0107478.
- Percentile cluster-bootstrap 95% CI: −0.0153094 to −0.0060236.
- Relative change: −17.4201%.
- Test-level wins: 57 of 84.
- Two-sided sign-flip p=0.00004.

The CI is the principal uncertainty summary. It does not account for unknown participant overlap or uncertainty introduced by selecting among sports and function families.

## Secondary analyses

- Workload, binned representation, external VO2R, and external power were prespecified after direction lock but are secondary.
- Their p values are reported as descriptive.
- No familywise multiplicity adjustment was applied.
- Interpretation is based primarily on paired effect estimates and 95% CIs.

## Strong comparator result

Temporal-holdout VO2R did not show incremental improvement over development-fitted linear calibration:

- Versus scaled linear: difference 0.0001401, 95% CI −0.0007672 to 0.0010571.
- Versus affine linear: difference 0.0005309, 95% CI −0.0013377 to 0.0024524.

These results are retained in the abstract, Results, Discussion, Conclusion, Table 3, and Figure 3. The manuscript does not claim universal nonlinear superiority.

## Endpoint-coupling check

The top target value was removed separately within every analysis unit and metrics were recomputed without refitting. Improvement relative to raw HRR persisted for temporal and external VO2R. For temporal normalized workload, however, the apparent advantage over scaled linear calibration disappeared after endpoint removal. The manuscript therefore distinguishes robust calibration gain from advantages created by a bounded target and endpoint-preserving formula.

## Intensity-specific check

Errors were summarized in four observed-HRR bands using the same unit-weighting rule. Relative to scaled linear calibration, the transfer was modestly better for VO2R within observations at 0.60 to <0.90 HRR in the temporal holdout but not at >=0.90 HRR. In ACTES, scaled linear calibration was better for VO2R within the >=0.90 HRR band. These findings reject a general claim that the quadratic tail captures high-intensity metabolic curvature better than a fitted linear alternative.

## Practical classification check

Exact 10%-wide VO2R-band agreement increased from 50.9% with raw HRR to 59.7% with CycHRR-T in the temporal holdout and from 43.6% to 51.1% in ACTES. The corresponding advantage over scaled linear calibration was small in the temporal holdout and 2.0 percentage points externally. Within-one-band agreement was also reported so readers can distinguish exact-category improvement from clinically or practically large misclassification.

## Calibration and error reporting

- MAE is the primary accuracy metric because it is directly interpretable on the 0-to-1 target scale.
- RMSE, mean bias, calibration intercept, calibration slope, and calibration R2 are reported as descriptive supporting metrics.
- R2 is not used as the optimization criterion or as the sole evidence of validity.
- Raw, scaled-linear, affine-linear, and locked nonlinear estimates are evaluated with identical unit weighting.

## Sensitivity and robustness

- Resting HR and HRmax were perturbed independently by −5, 0, and +5 beats·min−1 without refitting.
- Some +5 beats·min−1 HRmax scenarios reversed the model contrast.
- The manuscript therefore requires defensible measured anchors and avoids age-predicted-HRmax deployment claims.
- ACTES HR series were shifted from −30 to +30 seconds relative to metabolic and power targets; superiority over raw HRR persisted throughout this range.
- Nearby parameter pairs produced nearly identical temporal VO2R MAE, so tau=0.90 and kappa=5.75 are not interpreted as uniquely estimated physiological constants.

## Reproducibility check

The full pipeline was rerun from the public source archive on 2026-08-08. It reproduced:

- 819 included tests and 6,230 active stages.
- Cycling development/holdout counts of 195/84, with one missing-date cycling test excluded from splitting.
- Locked primary and external estimates to the precision reported in the manuscript.
- All primary, strong-comparator, endpoint-exclusion, intensity-band, category-agreement, timing-offset, parameter, and anchor-sensitivity tables.
- All three figures and their machine-readable source data.

## Audit decision

Statistical reporting is suitable for an exploratory sport-methods manuscript. The added checks directly address fitted-linear alternatives, endpoint coupling, intensity localization, practical classification, timing alignment, parameter non-uniqueness, and anchor transportability. Remaining irreducible limitations are unknown participant dependence, non-preregistered direction selection, a small adolescent external sample, and validation intervals conditional on the selected model. These limitations are explicit rather than hidden by favorable summary metrics.
