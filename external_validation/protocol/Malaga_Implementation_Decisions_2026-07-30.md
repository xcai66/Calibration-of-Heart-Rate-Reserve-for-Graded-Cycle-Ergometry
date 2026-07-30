# Malaga implementation decisions

These decisions were made after checking column names, sampling intervals, and stage lengths, but before calculating any association between tHRR-I and an outcome.

1. Effort starts at the first record with treadmill speed greater than 5.05 km/h and ends at the last such record before speed returns to 5 km/h for recovery.
2. A test requires at least 60 seconds of pre-effort data and 180 seconds of post-effort recovery data.
3. The test-specific lower anchor is the minimum 30-second rolling median heart rate in the pre-effort segment. At least five valid observations are required in a rolling window. This is a walking/warm-up anchor, not resting heart rate.
4. HRmax is the maximum valid effort-phase heart rate. The HR range must be at least 30 beats/min.
5. Effort heart-rate coverage must be at least 80%. Intervals are weighted by time and capped at 30 seconds.
6. Recovery VO2 is median-smoothed over 15 seconds to limit single-breath noise. The baseline is the minimum smoothed value in the 180-second recovery interval. Excess VO2 is the trapezoidal integral of positive smoothed VO2 minus that baseline, reported in millilitres and millilitres per kilogram.
7. The primary modelling endpoint is total 180-second excess VO2 in millilitres. Ten participant-grouped folds are assigned with seed 20260730. Ordinary least squares is used for the prespecified base and augmented models. All reported prediction errors give each participant equal total weight.
8. The base model contains effort duration, mean HRR, age, sex, and body mass. The augmented model adds Delta_tilt. The locked index uses ten bins and lambda=6.2. No formula or outcome-driven tuning is allowed.
