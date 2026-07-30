# Locked external-validation protocol for tHRR-I

Protocol date: 2026-07-30 (Asia/Shanghai)

Status: written before inspection of external outcome data. This is a prospective analysis specification for the public-data extension of the PMData development study. It is not a registered protocol and must not be described as preregistered.

## 1. Fixed index

The candidate index is frozen at the PMData development estimate `lambda = 6.2`:

`tHRR-I = sum_i[P_i c_i exp(6.2 c_i)] / sum_i[P_i exp(6.2 c_i)]`,

where `P_i` is the time-weighted proportion in HRR bin `i` and `c_i = (i - 0.5)/10` for ten bins. HRR is `(HR - HRrest)/(HRmax - HRrest)`, clipped to `[0, 1]` before binning. The continuous version is a prespecified sensitivity analysis only. The primary comparator is time-weighted mean HRR. The linear-decile score is retained as a secondary comparator because it was the principal PMData comparator.

No external dataset may be used to reselect the formula family, lambda, bin count, clipping rule, or comparator hierarchy. Dataset-specific regression coefficients may be estimated only for construct-validation models and must use participant-grouped validation.

## 2. Dataset eligibility

A public dataset is eligible if it has all of the following: a stable repository record and license; participant identifiers; time-resolved heart rate spanning a defined exercise bout; sufficient information to define or transparently approximate HRrest and HRmax; and at least one independently measured outcome relevant to internal load, cardiorespiratory response, energy expenditure, recovery, or exertion. Datasets are excluded if only summary heart rate is available, participant identity cannot be retained for clustered analysis, the exercise window cannot be reconstructed, or the access terms prohibit the planned analysis.

Eligibility is determined from documentation and variable availability, not from whether the result favors tHRR-I. All downloaded eligible datasets and all prespecified comparisons will be reported, including null or adverse findings.

## 3. Validation roles and claim boundaries

### 3.1 Primary external construct validation: Malaga treadmill tests

The University of Malaga PhysioNet dataset (version 1.0.1; DOI 10.13026/7ezk-j442) is the primary external construct dataset. The independent unit is the participant. Repeated tests from the same participant remain clustered.

The effort phase will be identified from treadmill speed. HRmax is the maximum quality-controlled heart rate observed during the maximal test. Because the repository does not provide a resting measurement, the primary analysis will use an explicitly named test-specific lower anchor derived from the lowest stable heart rate during the pre-effort/warm-up segment when that segment is identifiable. It will not be called clinical resting heart rate. Tests without an identifiable lower-anchor segment or with an implausible HR range will be excluded by rule and counted.

The primary construct endpoint is post-effort excess oxygen consumption during the first 180 seconds after effort cessation, expressed as the time integral of VO2 above the recovery-period minimum. The principal comparison is the participant-grouped cross-validated incremental prediction of this endpoint by `Delta_tilt = tHRR-I - mean HRR` after duration, mean HRR, age, sex, and body mass. This outcome is not algebraically derived from heart rate and provides a bounded test of whether upper-tail distribution information adds physiological information beyond mean exposure. Secondary outcomes are peak VO2, peak VCO2/VO2 ratio, one-minute heart-rate recovery, and the within-test association between HRR and VO2 reserve where feasible.

Performance will be reported as participant-grouped cross-validated MAE, RMSE, and R-squared for the base and augmented models, with paired participant-cluster bootstrap intervals for performance differences. The coefficient for Delta_tilt and a cluster-bootstrap interval will be reported descriptively. No causal or clinical-threshold claim will be made.

### 3.2 Secondary device and energy-expenditure transportability: WEEE

WEEE (Zenodo DOI 10.5281/zenodo.6420886) is eligible if the downloaded archive provides synchronized reference chest heart rate, wrist-device heart rate, participant age, defined activity stages, and indirect-calorimetry data. HRrest will be estimated from the seated-rest stage. HRmax will use the Tanaka age-predicted equation because the protocol is not maximal; this is a deployment-oriented anchor and will be labelled as such.

For each participant and activity stage, tHRR-I will be calculated separately from the reference chest signal and each eligible wrist signal. Primary device outcomes are absolute agreement with reference tHRR-I and Delta_tilt using mean bias, participant-clustered limits of agreement, MAE, and a two-way absolute-agreement ICC when estimable. The construct endpoint is indirect-calorimetry energy expenditure or VO2. Models containing activity duration and mean HRR will be compared with models adding Delta_tilt using leave-one-participant-out validation. These analyses are secondary and cannot establish external RPE prediction.

### 3.3 External exertion feasibility datasets

SoccerMon and the Polar futsal dataset will first undergo a variable and linkage audit. They enter an external RPE analysis only if session-level RPE can be linked without ambiguity to time-resolved HR and if defensible lower and upper heart-rate anchors are available. If eligibility is met, the PMData formula and lambda remain fixed. A PMData-trained RPE calibration, including its intercept and slope, will be frozen and applied without refitting for the primary prediction analysis. Recalibration-in-the-large and intercept/slope recalibration will be secondary. If eligibility is not met, the files will be listed as screened but excluded, with the exact reason; no external RPE validation claim will be made.

## 4. Signal processing

Duplicate timestamps will be removed. HR values outside 30–220 beats/min will be invalid. Intervals will be time weighted and capped at 30 seconds; a 15-second cap is a sensitivity analysis. A bout or stage requires at least 80% temporal coverage and at least 5 minutes of valid HR for laboratory stages or 10 minutes for sessions. HRR values outside `[0, 1]` will be counted before clipping. Analyses will be repeated after winsorizing the upper 1% of HR values within participant and after perturbing HRmax by plus/minus 5 beats/min and the lower anchor by plus/minus 3 beats/min where meaningful.

## 5. Statistical principles

Participants, not breaths, timestamps, stages, or sessions, are the independent sampling units. Cross-validation and bootstrapping will therefore be grouped by participant. Repeated tests and stages are retained within participant folds. The bootstrap will resample participants with replacement and retain all observations from each selected participant. Five thousand replicates and a fixed random seed of 20260730 will be used.

Primary contrasts will be defined within each dataset. Dataset roles will not be pooled into one universal p value. Effect estimates and 95% bootstrap intervals will be emphasized. Dataset-screening, exclusions, missingness, model failures, and all null or adverse results will be retained in machine-readable outputs. The analysis is an external construct and transportability evaluation unless a truly eligible session-RPE dataset is obtained; it is not automatically an external predictive validation of RPE.

## 6. Multiplicity and interpretation

One primary endpoint is specified for Malaga. WEEE and all other endpoints are secondary. Secondary analyses will be labelled exploratory and their false-discovery-rate-adjusted p values, if p values are reported, will use the Benjamini-Hochberg procedure within dataset. Emphasis remains on effect sizes and uncertainty. No result will be described as clinically validated, prescriptive, or mechanistic.

## 7. Reproducibility and provenance

Each downloaded file will be recorded with repository URL, version, access date, byte size, and SHA-256 digest. Raw third-party data will not be added to the public code repository unless redistribution is clearly permitted and appropriate. Scripts, manifests, variable audits, derived non-identifying tables, and figures will be included in the submission package. The manuscript Data Availability statement will distinguish PMData, Malaga, WEEE, and any other reused datasets by DOI and access route.

## 8. Ethics boundary

The source studies' ethics and consent statements will be cited from their publications or repository records. This secondary analysis will not be represented as institutionally exempt or non-human-subject research until Jimei University provides an independent determination. The existing author action item therefore remains open.
