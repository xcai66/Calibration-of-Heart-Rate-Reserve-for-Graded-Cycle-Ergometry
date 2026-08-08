# Style guide and terminology ledger

## Canonical terms

| Canonical term | First-use definition | Disallowed variants |
|---|---|---|
| heart-rate reserve (HRR) | (HR - resting HR) / (maximal HR - resting HR) | cardiac reserve score; HR reserve percentage when a fraction is meant |
| oxygen-uptake reserve (VO2R) | (VO2 - resting VO2) / (maximal VO2 - resting VO2) | VO2max fraction |
| cycle-ergometry-derived HRR transfer (CycHRR-T) | the locked pointwise function g(h) | cycling-specific physiological law; nonlinear load score |
| duration-weighted mean transformed intensity | implementation-only mean of g(h) | CycHRR-IS; physiological load; fatigue score |
| duration-weighted exposure descriptor | duration multiplied by mean g(h) | CycHRR-D; validated training load |
| raw HRR identity mapping | prediction equal to h | traditional model when calibration is fitted |
| scaled-linear comparator | development-fitted slope through the origin | nonlinear comparator |
| affine-linear comparator | development-fitted intercept and slope | raw linear score |
| temporal holdout | latest-date 30% of cycling tests | validation cohort when participant identity is unknown |
| ACTES external task validation | PhysioNet graded cycling dataset with 18 participants | population-wide external validation |
| complete-test analysis unit | one graded test file | independent participant when identity is unknown |
| 10% intensity-band agreement | agreement between target and predicted 10% reserve bands | validated training-zone accuracy |

## Writing rules

- Use restrained, sport-science SCI prose.
- Abstract contains no em dashes.
- Use one message per paragraph and one hedge per claim.
- Report the comparator, analysis unit, effect size, and confidence interval together.
- Use "improved relative to raw HRR" for the decisive result.
- Use "no clear difference" or "context-dependent incremental benefit" relative to calibrated linear models.
- Do not use "superior" without the named comparator and confidence interval.
- Do not use "clinical", "diagnostic", "prevents overtraining", "predicts adaptation", or "valid for consumer wearables".
- Use past tense in Results, present tense for established knowledge, and calibrated interpretation in Discussion.

## Number and symbol conventions

- Fractions are reported on 0-1 scale in Methods and metrics; percentages only for interpretation.
- MAE and confidence intervals use four decimal places in tables and three significant decimals in prose.
- Use tau = 0.90 and kappa = 5.75 everywhere.
- Use 95% CI, not confidence bounds or error range.
- Define n as number of complete tests or participants, never stage rows.
