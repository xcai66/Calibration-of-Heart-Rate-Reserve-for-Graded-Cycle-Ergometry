# Third-party data licenses and provenance

This directory documents the source records, licences, and integrity information needed to obtain the third-party files used in the external analyses. The public repository and software archive do not contain third-party raw files. Analysts must obtain the source files from the original providers; those files retain their original ownership, licences, and access conditions.

- Malaga treadmill maximal exercise tests, version 1.0.1: PhysioNet, DOI `10.13026/7ezk-j442`. The PhysioNet Contributor Review Health Data License 1.5.0 and associated data-use agreement apply. File hashes are recorded in `manifests/malaga_manifest.json`.
- WEEE: Zenodo, DOI `10.5281/zenodo.6420886`, CC BY 4.0. Only the selected files needed for the locked analysis were retrieved through verified HTTP range extraction. CRC and SHA-256 values are recorded in `manifests/weee_selected_manifest.json`.
- Polar futsal record metadata: Zenodo, DOI `10.5281/zenodo.15076183`, record license CC BY 4.0. No dataset files were available from the API on the audit date.

Do not upload third-party raw files to the project GitHub or a Zenodo software release without a separate licence and redistribution review. Public code releases should contain scripts, manifests, derived non-identifying summaries, and links to the source repositories.
