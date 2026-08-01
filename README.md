# tHRR-I-PMData

Reproducible code, protocols, frozen derived results, and publication figures for the development and external construct evaluation of a bounded, tail-sensitive heart-rate-reserve distribution index (tHRR-I).

Repository: https://github.com/xcai66/tHRR-I-PMData

## Scope and evidential status

The formula family was developed retrospectively in the public PMData sports-logging dataset. PMData results are therefore exploratory method-development evidence, not independent validation. The round-5 release adds a direct nested comparison of mean HRR versus mean HRR plus Δtilt, participant-balanced inner selection by MAE, transparent variance and upper-zone-time comparators, exact participant-level paired tests, sample-flow reconciliation, and repeated-measures agreement analyses.

The ten-bin formula and λ = 6.2 were fixed before the external outcome analyses. WEEE supports within-participant convergence with graded oxygen uptake and transportability of the complete score from a Zephyr chest signal. It does not show incremental association or prediction beyond mean HRR, and high-running-stage retention was only 3/16. University of Malaga recovery analyses likewise show no stable incremental prediction after mean HRR and covariates. The score is a candidate retrospective session-review descriptor. It is not a validated training prescription, alert threshold, clinical measure, or injury-prevention tool.

## Author

BoTao Cai (蔡伯韬)<br>
College of Physical Education, Jimei University, Xiamen 361021, China<br>
Email: xcai2004xcai@gmail.com

The work was conducted independently without external funding. The author declares no competing financial or non-financial interests.

## Repository contents

- `analysis/`: frozen PMData session-level and summary outputs, including reviewer-round-5 incremental analyses.
- `external_validation/protocol/`: the dated external-analysis protocol and implementation decisions.
- `external_validation/results/`: derived non-identifying WEEE and Malaga results.
- `external_validation/data/processed/`: derived stage- and test-level analysis tables.
- `external_validation/manifests/`: source records and integrity information.
- `external_validation/scripts/`: WEEE, Malaga, synchronization, sensitivity, and Figure 5 scripts.
- `figures/`: publication figures in PNG and SVG formats.
- `results/tables/`: the auditable results workbook.
- `manifests/`: PMData source URLs, sizes, and SHA-256 checksums.
- `docs/`: statistical appendix and data-license documentation.
- `run_analysis.py`: PMData analysis order.
- `run_external_analysis.py`: external analysis order after licensed source data have been obtained.

## Third-party data access

Raw third-party files are not redistributed in this repository.

- PMData: https://datasets.simula.no/pmdata/ and https://osf.io/vx4bk/ (CC BY-NC 4.0).
- Malaga treadmill tests v1.0.1: https://doi.org/10.13026/7ezk-j442.
- WEEE: https://doi.org/10.5281/zenodo.6420886 (CC BY 4.0).

Users must obtain data from the original providers and follow their terms. Source provenance, retrieval decisions, and integrity information are documented in `DATA_LICENSE.md` and `external_validation/DATA_LICENSE_AND_PROVENANCE.md`.

## Python reproduction

The verified environment used Python 3.12.13. Install the pinned packages, obtain the licensed data, and set `PMDATA_ROOT` for the PMData reconstruction.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PMDATA_ROOT=/absolute/path/to/pmdata
python run_analysis.py
```

The external scripts expect source files under `external_validation/data/raw/`; this path is ignored by Git. Dataset-specific decisions and required files are documented in `external_validation/protocol/` and `external_validation/manifests/`.

```bash
python run_external_analysis.py
```

## Figure reproduction

The verified figure environment used Node.js and Sharp 0.34.5.

```bash
npm install
npm run all-figures
```

## Verified full rerun

The complete PMData, WEEE, and Malaga pipelines were rerun from the locally held, provider-distributed source files on 1 August 2026 with Python 3.12.13 and the pinned dependencies. All scripts exited successfully and reproduced the frozen round-5 estimates reported below. A machine-readable verification record and human-readable report are in `reproduction/`; raw console logs are retained in the submission package but are not published because they include machine-specific paths.

## Main reproducibility checks in the round-5 release

- Direct fully nested PMData comparison: mean HRR plus Δtilt MAE 1.232 versus 1.302 for mean HRR; ΔMAE -0.070 RPE units (95% participant-cluster bootstrap interval -0.165 to 0.035), exact P=0.228, with 11/15 participants favoring the augmented model.
- Fixed-λ=6.2 sensitivity: mean HRR plus Δtilt ΔMAE -0.074 (-0.155 to 0.002). Stand-alone fixed tHRR-I gave ΔMAE -0.074 (-0.133 to -0.017), but that comparison does not isolate distribution information.
- Transparent baselines were retained regardless of direction: mean HRR plus variance ΔMAE -0.008 (-0.064 to 0.054); mean HRR plus time at or above 80% HRR ΔMAE -0.023 (-0.136 to 0.107).
- Selection-aware transparent pipeline: ΔMAE -0.057 (-0.151 to 0.048); 14/15 outer folds selected Δtilt and one selected time at or above 80% HRR.
- Strict PMData matching tier: 203 sessions from 15 participants; ΔMAE -0.064 (-0.123 to -0.013).
- Circular within-participant RPE permutation, with λ reselected in all 5,000 replicates: empirical P = 0.00020.
- WEEE within-participant VO₂ association: r = 0.861 for tHRR-I and 0.855 for mean HRR; difference 0.006 (-0.008 to 0.027).
- WEEE incremental VO₂ prediction after adding Δtilt: ΔMAE 0.024 mL·kg⁻¹·min⁻¹ (-0.115 to 0.170).
- Zephyr tHRR-I agreement: participant-balanced CCC 0.846 (0.654 to 0.946), participant-balanced bias -0.025 HRR units (-0.044 to -0.001), and repeated-measures limits -0.262 to 0.213. The older stage-level ICC(A,1) is retained only as a secondary descriptor.
- WEEE sample flow: 102 possible stages from 17 participants, 96 stages after resting-anchor eligibility, and 77 final stages; high-running retention was 3/16 (18.8%).
- Malaga primary 180-second recovery endpoint: ΔMAE 0.009 mL (-1.234 to 1.276), with no stable benefit across endpoint and anchor variants.

## Random seeds

- `20260728`: original analysis.
- `20260729`: reviewer-revision bootstrap.
- `20260731`: repeated grouped splits, selection-aware analysis, permutation negative control, and external sensitivity analyses.
- `20260730`: raw-signal, physiological-anchor, and full-rematching analyses.
- `20260801`: round-5 participant-loss bootstrap, exact sign-flip tests, sample-flow reconciliation, and repeated-measures WEEE agreement.

## License and citation

Original code is released under the MIT License. Third-party data and derivative materials remain subject to their source terms. Cite the source datasets and the archived software release when reusing this work. Citation metadata are provided in `CITATION.cff`.

## Persistent archive

Release `v1.2.1` is a documentation-only clarification aligning the statistical appendix hierarchy with the round-5 incremental comparison; formulas, samples, scripts, figures, and numerical results are unchanged. Cite the frozen v1.2.1 archive at [10.5281/zenodo.21742204](https://doi.org/10.5281/zenodo.21742204). The concept DOI [10.5281/zenodo.21689574](https://doi.org/10.5281/zenodo.21689574) always resolves to the latest archived version. Release `v1.2.0` remains at [10.5281/zenodo.21740906](https://doi.org/10.5281/zenodo.21740906), release `v1.1.0` at [10.5281/zenodo.21710544](https://doi.org/10.5281/zenodo.21710544), and release `v1.0.0` at [10.5281/zenodo.21689575](https://doi.org/10.5281/zenodo.21689575).

[![DOI](https://zenodo.org/badge/1315350784.svg)](https://doi.org/10.5281/zenodo.21689574)
