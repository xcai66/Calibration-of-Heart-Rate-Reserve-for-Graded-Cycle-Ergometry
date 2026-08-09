#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

GRADED_ARCHIVE="${PROJECT_ROOT}/01_sources/data_v2_clean.zip"
GRADED_RAW="${PROJECT_ROOT}/02_data/raw/graded_tests"
DERIVED="${PROJECT_ROOT}/02_data/derived"
TABLES="${PROJECT_ROOT}/04_results/tables"
FIGURES="${PROJECT_ROOT}/04_results/figures"

if [[ ! -f "${GRADED_ARCHIVE}" ]]; then
  echo "Missing public source archive: ${GRADED_ARCHIVE}" >&2
  exit 1
fi
if [[ ! -f "${PROJECT_ROOT}/01_sources/actes_test_measure.csv" ]]; then
  echo "Missing ACTES source file." >&2
  exit 1
fi

mkdir -p "${GRADED_RAW}" "${DERIVED}" "${TABLES}" "${FIGURES}"

if [[ ! -f "${GRADED_RAW}/data/Data_Summary.xlsx" ]]; then
  unzip -q "${GRADED_ARCHIVE}" -d "${GRADED_RAW}"
fi

"${PYTHON_BIN}" "${SCRIPT_DIR}/01_extract_graded_tests.py" \
  --input "${GRADED_RAW}/data" \
  --output "${DERIVED}"

"${PYTHON_BIN}" "${SCRIPT_DIR}/02_compare_sports.py" \
  --input "${DERIVED}/graded_tests_tidy.csv" \
  --output "${TABLES}"

"${PYTHON_BIN}" "${SCRIPT_DIR}/03_validate_selected.py" \
  --graded "${DERIVED}/graded_tests_tidy.csv" \
  --splits "${TABLES}/predefined_test_splits.csv" \
  --actes "${PROJECT_ROOT}/01_sources/actes_test_measure.csv" \
  --output "${TABLES}"

"${PYTHON_BIN}" "${SCRIPT_DIR}/08_robustness_analyses.py" \
  --graded "${DERIVED}/graded_tests_tidy.csv" \
  --splits "${TABLES}/predefined_test_splits.csv" \
  --actes-processed "${TABLES}/actes_processed_10s.csv" \
  --linear-parameters "${TABLES}/development_linear_comparator_parameters.csv" \
  --output "${TABLES}"

"${PYTHON_BIN}" "${SCRIPT_DIR}/04_make_figures.py" \
  --tables "${TABLES}" \
  --output "${FIGURES}"

"${PYTHON_BIN}" "${SCRIPT_DIR}/05_build_results_workbook.py" \
  --root "${PROJECT_ROOT}" \
  --output "${PROJECT_ROOT}/04_results/CycHRR_T_Results_and_Source_Data.xlsx"

"${PYTHON_BIN}" "${SCRIPT_DIR}/test_cychrr.py"

echo "Analysis complete. Results are in ${PROJECT_ROOT}/04_results."
