# Submission audit

Audit date: 2026-08-08

## Claim and terminology consistency

- Central claim is identical in the title, abstract, Results, Discussion, and Conclusion.
- `CycHRR-T` consistently denotes the pointwise transfer function.
- Unvalidated aggregate-score acronyms have been removed from the submission manuscript.
- `VO2R`, `workload fraction`, and `power fraction` are not conflated with fatigue or total training load.
- The model is described as an endpoint-preserving group calibration, not a biological law or universally superior nonlinear model.

## Evidence coverage

- Figure 1 supports direction selection and data separation.
- Figure 2 supports function shape and validation performance.
- Figure 3 supports intensity-specific comparisons, endpoint exclusion, 10%-band agreement, and anchor sensitivity.
- Tables 1 to 4 cover allocation, validation against raw HRR, fitted-linear comparison, and practical/robustness analyses.
- Machine-readable source data exist for each figure.

## Methods completeness

- Public dataset versions and DOIs are stated.
- Inclusion, exclusion, anchor, plausibility, split, cross-validation, tuning-grid, and external-processing rules are stated.
- Independent units and equal-unit weighting are stated.
- Primary estimand, bootstrap, sign-flip test, secondary status, and fixed seed are stated.
- Internal lock is distinguished from external preregistration.

## Reference hygiene

- 14 numbered references; 14 verified reference DOIs; no reference placeholders.
- Reference numbering is synchronized in English and Chinese.
- Dataset and software-provenance files are included.
- `references.bib` is ready for EndNote, Zotero, or BibTeX import.

## Declarations

- Author, affiliation, email, contribution, funding, and conflict statements are present.
- ORCID 0009-0002-3662-4539 is present in both manuscripts, the title page, citation metadata, and repository metadata.
- Code DOI remains an author-input placeholder until archival.
- Secondary-analysis ethics status is disclosed without claiming a local exemption that has not been obtained.
- AI-use disclosure is included for adaptation to target-journal policy.

## Reproducibility and artifact QA

- The complete raw-to-result analysis pipeline was rerun successfully after final revision.
- The standalone CycHRR-T implementation passed regression tests covering endpoint clipping, monotonicity, boundedness, its relation to the HRR identity map, duration weighting, and invalid-input rejection.
- The results workbook contains raw audit counts, locked validation, strong comparators, endpoint exclusion, intensity bands, 10%-band agreement, timing offsets, parameter sensitivity, anchor sensitivity, and key formula-linked results.
- English and Chinese Word/PDF manuscripts were rendered to 19 and 24 pages, respectively; all page groups were visually inspected without clipping, missing glyphs, or displaced figures. The two-page title/declarations file, one-page cover letter, and one-page highlights file were also inspected.
- The three figure families were exported as PNG, PDF, SVG, and TIFF; strict figure checks produced no blocking failures.

## Remaining target-journal actions

These items cannot be finalized before the journal is selected:

1. Apply journal-specific word, abstract, reference, table, and figure rules.
2. Replace the target-journal placeholder in the cover letter.
3. Archive the revised repository release and add its permanent DOI once Zenodo has created it.
4. Obtain an institutional secondary-analysis determination if requested by the journal or institution.

## Readiness decision

The package is ready for journal selection and format adaptation. Internal scientific maturity is approximately **3.8/5** for a specialized SCIE sport-measurement or exercise-physiology venue: originality 3.4, practical importance 3.4, technical soundness 4.1, transparency/reproducibility 4.4, and writing/presentation 4.3. The principal remaining risks are participant dependence that cannot be reconstructed from the source data, controlled graded-test generalizability, the small external sample, and HR-anchor transportability. This score reflects submission preparedness, not a guarantee of editorial review or acceptance.
