# Release checklist

## Completed for v1.1.0

- [x] Confirm that the repository contains no raw PMData, WEEE, or Malaga files.
- [x] Confirm that `CITATION.cff` contains the repository URL and the author spelling "BoTao Cai".
- [x] Freeze the selection-aware PMData analyses, permutation control, strict matching analysis, WEEE repeated-measures analyses, device-agreement audit, synchronization audit, and Malaga sensitivity analyses.
- [x] Rebuild the results workbook, figures, statistical appendix, and manuscript-facing outputs from the frozen results.
- [x] Parse-check all Python and JSON files and audit the repository for oversized or disallowed raw-data files.
- [x] Record the previous release DOI (`10.5281/zenodo.21689575`) and stable concept DOI (`10.5281/zenodo.21689574`).

## Publication actions

- [ ] Push the frozen v1.1.0 commit to GitHub.
- [ ] Create GitHub release `v1.1.0` from the frozen commit.
- [ ] Publish the linked Zenodo archive and obtain its version-specific DOI.
- [ ] Add the new version-specific DOI to the main branch, manuscript, cover letter, response letter, and Data and Code Availability statement.
- [ ] Re-render all Word documents and verify the final PDF pages after DOI insertion.
- [ ] Re-run repository and submission-package integrity checks before journal submission.
