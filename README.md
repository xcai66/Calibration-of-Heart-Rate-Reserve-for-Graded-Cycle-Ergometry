# Calibration of Heart-Rate Reserve for Graded Cycle Ergometry

CycHRR-T is a reproducible methods project evaluating a bounded, endpoint-preserving group calibration of heart-rate reserve (HRR) for concurrent intensity estimation in graded cycle ergometry.

## Locked function

For HRR fraction `h` clipped to `[0, 1]`:

```text
g(h) = [h + 5.75 * max(h - 0.90, 0)^2] / 1.0575
```

The function was selected using development-only grouped cross-validation. The final temporal cycling holdout and the ACTES external dataset were not used for parameter tuning.

## Repository structure

```text
00_foundation/    Claim boundaries and manuscript argument map
01_sources/       Public source archives and source licenses
02_data/          Extracted raw files and derived analysis data
03_code/          Reproducible analysis and figure code
04_results/       Tables, source-data workbook, and figures
05_manuscript/    English and Chinese manuscripts
06_submission/    Submission-facing and reference files
07_review/        Citation, statistical, submission, and visual QA records
```

## Reproduce the analysis

1. Install Python 3.12 or newer.
2. Create an isolated environment and install `03_code/requirements.txt`.
3. Ensure these public source files are present:
   - `01_sources/data_v2_clean.zip`, from Zenodo DOI `10.5281/zenodo.10841412`.
   - `01_sources/actes_test_measure.csv`, from PhysioNet DOI `10.13026/2qs3-kh43`.
4. From the project root, run:

```bash
bash 03_code/run_all.sh
```

The pipeline extracts the workbooks, recreates the deterministic development/holdout split, performs development-only candidate comparison, applies the locked model, runs complete-unit uncertainty, endpoint-exclusion, intensity-band, practical-agreement, time-offset, parameter, and anchor analyses, and regenerates the manuscript figures.

Run the implementation tests with:

```bash
python3 03_code/test_cychrr.py
```

## Apply CycHRR-T to a heart-rate file

Prepare a CSV containing an `hr` column in beats per minute. An optional `duration_seconds` column supplies the time represented by each row; otherwise, rows receive equal weight. Then run:

```bash
python3 03_code/07_apply_cychrr.py input.csv output.csv --rest-hr 55 --max-hr 190
```

The output includes clipped raw HRR and pointwise `CycHRR-T`. It also reports a descriptive duration-weighted mean transformed intensity and an exploratory duration-weighted exposure. These summaries are not validated training-load scores. Because the validation used graded cycle-ergometer data with directly determined HR anchors, replacing measured anchors with age-predicted or error-prone values can materially alter performance.

## Primary result

In 84 temporally held-out cycling test files, CycHRR-T reduced complete-test VO2R MAE from 0.0617 to 0.0510 relative to raw HRR, an absolute improvement of 1.07 percentage points. Exact 10% VO2R-band agreement increased from 50.9% to 59.7%. Performance was similar to development-fitted linear calibration for the primary target, and high-intensity VO2R analyses did not establish an advantage for the quadratic tail. The method is therefore an endpoint-preserving group calibration, not a universally superior nonlinear model.

## Scope

Validated here:

- Concurrent VO2R and normalized workload estimation in controlled graded cycling.
- Continuous HRR and an INTERLIVE-compatible 10-bin representation.
- Temporal and external laboratory-task transport without refitting.

Not validated here:

- Wrist-photoplethysmography accuracy.
- Outdoor cycling, interval recovery, prolonged cardiovascular drift, heat, altitude, or medication-altered HR.
- Fatigue, recovery, training adaptation, injury risk, clinical outcome, or return-to-play decisions.

Duration-weighted session summaries are implementation descriptors only. The study evaluates the pointwise transfer against concurrent metabolic and mechanical intensity and does not validate aggregate scores against training-response outcomes.

## Data licenses

The development dataset is licensed CC BY 4.0 by its creators. ACTES is distributed under the PhysioNet Open Data Commons Attribution License. Their original licenses and citations must be retained. Analysis code in this package is MIT licensed. The manuscript and newly generated figures are provided for the author's scholarly use; journal copyright terms may supersede this package after publication.

## Citation

The public repository is https://github.com/xcai66/Calibration-of-Heart-Rate-Reserve-for-Graded-Cycle-Ergometry. The v2.0.0 software archive is [10.5281/zenodo.21860652](https://doi.org/10.5281/zenodo.21860652), and future versions remain linked by the stable concept DOI [10.5281/zenodo.21689574](https://doi.org/10.5281/zenodo.21689574). Cite the accompanying manuscript, the relevant archived software version, and both source datasets.

## Contact

BoTao Cai, College of Physical Education, Jimei University, Xiamen, Fujian, China. Email: xcai2004xcai@gmail.com. ORCID: https://orcid.org/0009-0002-3662-4539.
