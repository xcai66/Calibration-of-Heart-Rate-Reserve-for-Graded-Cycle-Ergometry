# Project scope

## Working title

Calibration of Heart-Rate Reserve for Graded Cycle Ergometry: An Endpoint-Preserving Transfer Evaluated Against Linear Alternatives

## One-sentence argument

In graded cycle ergometry, a locked, bounded HRR transfer improves concurrent VO2R and normalized-workload estimation relative to an uncalibrated identity mapping, but does not show general nonlinear superiority over fitted linear calibration and therefore remains an endpoint-preserving group calibration rather than a validated training-response or clinical score.

## Study type

- Secondary analysis of public, deidentified datasets.
- Methods-development and external-validation study.
- No new participant recruitment, intervention, or data collection.
- No attempt to replace the author's earlier null free-living study with a selectively positive re-analysis.

## Primary question

Can a fixed endpoint-preserving transformation improve graded cycling-intensity estimation relative to raw HRR, and does it add accuracy beyond development-fitted linear calibration?

## Primary target and metric

- Target: oxygen-uptake reserve (VO2R).
- Metric: mean absolute error (MAE), calculated within each complete test file or participant and then averaged across analysis units.
- Primary validation: latest-date 30% temporal holdout of the cycling subset.

## Secondary targets and analyses

- Normalized external load: cycling power divided by test-specific maximal power.
- External task validation: ACTES participants.
- Ten-bin HRR representation matching the INTERLIVE framework.
- Strong comparators: development-fitted scaled-linear and affine-linear models.
- Anchor sensitivity: resting HR and maximal HR perturbed by plus or minus 5 beats/min.
- Reviewer-requested robustness: intensity bands, endpoint removal, 10% band agreement, ACTES time offsets, and nearby parameter sets.

## Direction-selection rule

The sport and nonlinear family were selected using only the earlier 70% development tests. Four sports were compared with identical preprocessing and grouped five-fold cross-validation: cycling, running, rowing, and kayaking. The final temporal holdout was not used for sport selection or parameter optimization.

## Locked method

For HRR fraction h in [0,1],

g(h) = [h + kappa * max(h - tau, 0)^2] / [1 + kappa * (1 - tau)^2]

with tau = 0.90 and kappa = 5.75. The denominator anchors g(1) at 1, and clipping anchors the operational domain at 0-1.

The duration-weighted mean of g(h), and that mean multiplied by duration, are implementation descriptors only. They are not named or presented as validated training-load scores.

## Boundaries

- Intended for sustained cycling or cycling ergometry with reliable HR recordings.
- Requires defensible resting and maximal HR anchors, preferably measured rather than age-predicted.
- Not validated for sprint starts, resistance exercise, team sports, disease populations, medication-altered HR, heat stress, dehydration, or free-living optical-sensor error.
- Does not estimate anaerobic energy contribution, neuromuscular load, fatigue, recovery need, injury risk, or training adaptation.
- Public data do not contain stable participant identifiers in the main graded-test dataset, so repeated tests by the same person cannot be identified. The complete test is the analysis unit.

## Administrative facts

- Author: BoTao Cai (蔡伯韬).
- Affiliation: College of Physical Education, Jimei University, Xiamen, Fujian, China.
- Email: xcai2004xcai@gmail.com.
- Funding: none reported.
- Competing interests: none reported.
- ORCID: 0009-0002-3662-4539.
- Target journal: not yet fixed; use generic SCIE sport/exercise-science conventions.
