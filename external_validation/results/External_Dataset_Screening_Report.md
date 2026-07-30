# External dataset screening report

Audit date: 2026-07-30 (Asia/Shanghai)

The formula, `lambda = 6.2`, eligibility criteria, comparator hierarchy, and primary outcome were frozen before outcome inspection. Dataset eligibility was based on access, time-resolved heart rate, physiological anchors, participant clustering, and an independent outcome. It was not based on whether results favored tHRR-I.

## Included datasets

1. **University of Malaga treadmill maximal exercise tests, version 1.0.1** (DOI: 10.13026/7ezk-j442). The PhysioNet record contains 992 maximal graded exercise tests with breath-by-breath heart rate, oxygen consumption, carbon dioxide production, and treadmill speed. The primary analysis used 758 tests from 668 participants after locked quality-control rules. The repository license and data-use terms apply.
2. **WEEE** (DOI: 10.5281/zenodo.6420886; source article DOI: 10.1038/s41597-022-01643-5). The public CC BY 4.0 dataset contains 17 participants, defined activity stages, multidevice heart rate, demographics, and indirect calorimetry. The construct analysis used 77 stages from 16 participants. Apple Watch agreement was not considered estimable because only one participant and two stages aligned after quality control.

## Screened but not analyzed

1. **SoccerMon** (DOI: 10.5281/zenodo.10033832). The repository reports 33,849 subjective records and 10,075 objective records. The four objective archives total 99.1 GB. The available documentation did not establish an analysis-ready session-level RPE linkage with defensible HRrest and HRmax anchors within the resources used for this revision. It was therefore excluded before outcome analysis.
2. **Polar futsal fatigue-monitoring record** (DOI: 10.5281/zenodo.15076183). The record describes wearable physiology and RPE categories and claims CC BY 4.0, but its Zenodo API response contained no downloadable files on the audit date. It was therefore unusable.

## Claim boundary

Neither included external dataset provides an eligible session-RPE endpoint to which the frozen PMData calibration can be applied. The extension is therefore an external construct and transportability evaluation, not an external predictive validation of RPE.
