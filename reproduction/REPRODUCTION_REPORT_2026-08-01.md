# Full reproduction report, 1 August 2026

## Scope

The complete PMData development pipeline and the locked WEEE and University of Malaga external-analysis pipelines were executed from locally held copies of the files distributed by the original providers. Third-party raw files were not copied into this release. All analyses used the frozen ten-bin tHRR-I formula and, for external evaluation, λ = 6.2 without outcome-guided retuning.

## Environment

- Python 3.12.13.
- Exact numerical and workbook packages listed in `requirements.txt`.
- Node.js with Sharp 0.34.5 for figure rendering.
- Random seeds are listed in the repository README and source scripts.

## Reproduced result fingerprints

- PMData: 255 sessions from 15 participants.
- Fully nested mean HRR plus Δtilt: participant-balanced MAE 1.232097 versus 1.302046 for mean HRR; ΔMAE -0.069950, 95% participant-cluster bootstrap interval -0.165443 to 0.034878, exact two-sided sign-flip P = 0.227539, 11/15 participants favoring augmentation.
- Fixed λ = 6.2 incremental sensitivity: ΔMAE -0.073789, interval -0.154945 to 0.001799, exact P = 0.098450.
- Fixed λ = 6.2 stand-alone tHRR-I: ΔMAE -0.074372, interval -0.133081 to -0.017170, exact P = 0.029968. This comparison does not isolate incremental distribution information.
- Selection-aware transparent pipeline: ΔMAE -0.057097, interval -0.150988 to 0.048250.
- Strict PMData matching tier: ΔMAE -0.064339, interval -0.123205 to -0.012562.
- WEEE: 77 eligible stages from 16 participants. Within-participant association with stage VO₂ was 0.860886 for tHRR-I and 0.854632 for mean HRR; difference 0.006254, interval -0.007539 to 0.027031.
- WEEE incremental prediction: ΔMAE +0.024208 mL·kg⁻¹·min⁻¹, interval -0.115456 to 0.170494.
- Zephyr tHRR-I agreement: participant-balanced CCC 0.846436, interval 0.654160 to 0.946413; bias -0.024567, interval -0.043911 to -0.000739; repeated-measures limits -0.262367 to 0.213234 HRR units.
- Malaga: 758 eligible tests from 668 participants. Primary 180-second recovery endpoint ΔMAE +0.008545 mL, interval -1.234117 to 1.276085; ΔR² -0.001737, interval -0.005923 to 0.002082.

## Warnings and verification conclusion

The PMData run produced only pandas future-compatibility warnings. External processing produced expected all-missing summaries for device-specific estimates that had insufficient data and were not used for the central claims. Neither pipeline failed. All five main figures were regenerated and visually reviewed. The rerun therefore confirms that the repository code reproduces the frozen manuscript-facing estimates from the provider-distributed source data within the stated software environment.

