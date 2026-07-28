# tHRR-I-PMData

Reproducible code, frozen derived results, and publication figures for the development and nested evaluation of a tail-sensitive normalized heart-rate-reserve index (tHRR-I) in PMData.

Repository: https://github.com/xcai66/tHRR-I-PMData

## Study status

This repository supports an exploratory secondary analysis of the public PMData sports-logging dataset. The formula family was developed after inspecting PMData. The study is therefore an internal method-development evaluation, not an independent external validation. The ten-bin formula and the full-development estimate of λ = 6.2 must be locked and tested in an independent dataset before training prescription, automated alerts, clinical interpretation, or rehabilitation use.

## Author

Botao Cai (蔡伯韬)  
College of Physical Education, Jimei University, Xiamen 361021, China

The study was independently conducted by the author without external funding. The author declares no competing financial or non-financial interests.

## Repository contents

- `analysis/`: frozen session-level and summary outputs used in the manuscript, figures, tables, and sensitivity analyses.
- `figures/`: publication figures in PNG and SVG formats.
- `results/tables/`: the auditable results workbook.
- `manifests/`: file-level source URLs, sizes, and SHA-256 checksums for the licensed PMData inputs.
- `docs/`: the statistical reproducibility appendix and the PMData licence copy.
- `*.py`: data reconstruction, nested evaluation, bootstrap, sensitivity, and reviewer-revision analyses.
- `build_improved_figures.mjs`: deterministic figure generation.
- `run_analysis.py`: primary Python run order.

## Data access

PMData is available from the original sources:

- https://datasets.simula.no/pmdata/
- https://osf.io/vx4bk/

PMData is distributed under CC BY-NC 4.0. Raw PMData files are not redistributed in this repository. Users must obtain the dataset from the original provider and comply with its licence. Set `PMDATA_ROOT` to the licensed local PMData directory before running reconstruction.

## Python reproduction

The verified environment used Python 3.12.13 with package versions pinned in `requirements.txt`.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PMDATA_ROOT=/absolute/path/to/pmdata
python run_analysis.py
```

The optional download scripts retrieve the required PMData files from the original OSF record and verify checksums. Heart-rate files are large. Review the licence and available storage before downloading.

## Figure reproduction

The verified figure environment used Node.js and Sharp 0.34.5.

```bash
npm install
npm run figures
```

## Frozen main result

The primary analysis contained 255 sessions from 15 participants. Participant-balanced held-out MAE was 1.206 RPE units for tHRR-I and 1.302 for the linear decile score. The difference was −0.097 RPE units, with a reviewer-revision conditional 95% interval from −0.164 to −0.033. Pooled cross-validated R² was 0.138. The improvement was small and does not establish practical superiority.

## Random seeds

- `20260728`: original analysis
- `20260729`: reviewer-revision bootstrap
- `20260731`: repeated grouped splits and round-two sensitivity analyses

## Licence and citation

Original code is released under the MIT License. PMData and derived material based on PMData remain subject to the original CC BY-NC 4.0 terms described in `DATA_LICENSE.md`. Cite the PMData paper and the archived repository release when reusing this work. Citation metadata are provided in `CITATION.cff`.

## Persistent archive

After the public GitHub release is archived in Zenodo, the version-specific DOI will be added here and to the manuscript's Data and Code Availability statements.
