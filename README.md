# tHRR-I-PMData

Reproducible code, protocols, frozen derived results, and publication figures for the development and external construct evaluation of a bounded, tail-sensitive heart-rate-reserve distribution index (tHRR-I).

Repository: https://github.com/xcai66/tHRR-I-PMData

## Scope and evidential status

The formula family was developed retrospectively in the public PMData sports-logging dataset. PMData results are therefore exploratory method-development evidence, not independent validation. Version 1.1.0 adds a selection-aware outer analysis, strict matching analysis, and within-participant label-permutation negative control.

The ten-bin formula and λ = 6.2 were fixed before the external outcome analyses. WEEE supports within-participant convergence with graded oxygen uptake and chest-signal reproducibility. It does not show incremental association or prediction beyond mean HRR. University of Malaga recovery analyses likewise show no stable incremental prediction after mean HRR and covariates. The score is a candidate retrospective session-review descriptor. It is not a validated training prescription, alert threshold, clinical measure, or injury-prevention tool.

## Author

BoTao Cai (蔡伯韬)<br>
College of Physical Education, Jimei University, Xiamen 361021, China<br>
Email: xcai2004xcai@gmail.com

The work was conducted independently without external funding. The author declares no competing financial or non-financial interests.

## Repository contents

- `analysis/`: frozen PMData session-level and summary outputs, including reviewer-round-4 analyses.
- `external_validation/protocol/`: the dated external-analysis protocol and implementation decisions.
- `external_validation/results/`: derived non-identifying WEEE and Malaga results.
- `external_validation/data/processed/`: derived stage- and test-level analysis tables.
- `external_validation/manifests/`: source records and integrity information.
- `external_validation/scripts/`: WEEE, Malaga, synchronization, sensitivity, and Figure 6 scripts.
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
npm run figures
npm run external-figure
```

## Main reproducibility checks in v1.1.0

- Selection-aware PMData outer LOPO: selected-pipeline MAE 1.208 versus 1.302 for the linear score; ΔMAE -0.094 RPE units (95% participant-cluster CI -0.161 to -0.031).
- Strict PMData matching tier: 203 sessions from 15 participants; ΔMAE -0.064 (-0.123 to -0.013).
- Circular within-participant RPE permutation, with λ reselected in all 5,000 replicates: empirical P = 0.00020.
- WEEE within-participant VO₂ association: r = 0.861 for tHRR-I and 0.855 for mean HRR; difference 0.006 (-0.008 to 0.027).
- WEEE incremental VO₂ prediction after adding Δtilt: ΔMAE 0.024 mL·kg⁻¹·min⁻¹ (-0.115 to 0.170).
- Zephyr tHRR-I agreement: ICC(A,1) 0.854 (0.667 to 0.952); Bland-Altman limits -0.257 to 0.205 HRR units.
- Malaga primary 180-second recovery endpoint: ΔMAE 0.009 mL (-1.234 to 1.276), with no stable benefit across endpoint and anchor variants.

## Random seeds

- `20260728`: original analysis.
- `20260729`: reviewer-revision bootstrap.
- `20260731`: repeated grouped splits, selection-aware analysis, permutation negative control, and external sensitivity analyses.
- `20260730`: raw-signal, physiological-anchor, and full-rematching analyses.

## License and citation

Original code is released under the MIT License. Third-party data and derivative materials remain subject to their source terms. Cite the source datasets and the archived software release when reusing this work. Citation metadata are provided in `CITATION.cff`.

## Persistent archive

Release `v1.1.0` is archived at the version-specific DOI [10.5281/zenodo.21710544](https://doi.org/10.5281/zenodo.21710544). Release `v1.0.0` remains at [10.5281/zenodo.21689575](https://doi.org/10.5281/zenodo.21689575). The concept DOI [10.5281/zenodo.21689574](https://doi.org/10.5281/zenodo.21689574) represents all versions and remains the stable citation target.

[![DOI](https://zenodo.org/badge/1315350784.svg)](https://doi.org/10.5281/zenodo.21689574)
