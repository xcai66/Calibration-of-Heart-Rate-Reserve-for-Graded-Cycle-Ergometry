# Argument map

## Central claim

A bounded, endpoint-preserving HRR transfer improves an uncalibrated identity mapping across temporal and external graded cycling data, but its incremental value beyond fitted linear calibration is target- and intensity-dependent.

## Logic chain

1. **Relevance**: HR is widely available and is an individualized internal-response signal, but generic HRR scoring assumes that HRR position is directly transferable to physiological intensity.
2. **Gap**: Evidence increasingly disputes universal 1:1 HRR-VO2R equivalence and indicates mode-, intensity-, and duration-dependent behavior.
3. **Opportunity**: INTERLIVE's 10-bin score is deliberately simple and extensible. A fixed group calibration can retain interpretability when individual calibration is unavailable.
4. **Direction selection**: Compare four sports under identical development-only grouped validation. Choose cycling because it combines a large sample, a clear development gain, and external graded cycle-ergometry data.
5. **Method**: Use a normalized quadratic tail above 90% HRR, with parameters locked at tau=0.90 and kappa=5.75.
6. **Main evidence**: Temporal holdout and ACTES validation show lower VO2R and normalized-power error than raw HRR.
7. **Strong-comparator check**: The method is comparable to fitted linear calibration for primary temporal VO2R; workload superiority can depend on endpoint-containing observations.
8. **Boundary tests**: Intensity bands, endpoint exclusion, 10% band agreement, time offsets, parameter alternatives, and HR-anchor perturbations locate where the method helps and fails.
9. **Reuse**: Provide continuous and 10-bin algorithms, code, split files, per-unit metrics, and figure source data.
10. **Boundary**: Require reliable HR anchors and graded or sustained cycling; do not claim session adaptation, fatigue, injury, clinical utility, or validation of any consumer device.

## Rival explanations addressed

- **Simple rescaling explains the full gain**: tested using scaled-linear and affine-linear comparators. It explains much, but not all external and mechanical improvement.
- **Stage-level pseudoreplication inflates precision**: metrics and resampling use complete test files or participants as analysis units.
- **The result depends on one arbitrary split**: development uses grouped five-fold CV; final evaluation uses a chronological holdout and independent dataset.
- **The nonlinear parameters were selected after seeing final results**: split and parameter-lock files are stored; holdout analyses run only after the lock.
- **Ten-bin quantization destroys the effect**: tested directly and retained benefit relative to raw 10-bin scoring.
- **Endpoint normalization creates the benefit**: tested by removing each unit's maximum target observation and excluding HRR >=0.95.
- **The quadratic tail adds high-intensity VO2R accuracy**: not supported; the manuscript states this negative result directly.
- **Consumer-wearable deployment is proven**: explicitly rejected; both validation datasets used research-grade HR measurement.
