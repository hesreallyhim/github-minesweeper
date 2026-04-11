#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
JOBS_DIR="${FACTORY_JOBS_DIR:-${REPO_ROOT}/factory-jobs}"
STATE_DIR="${FACTORY_STATE_DIR:-${REPO_ROOT}/factory/state}"
RUN_SINGLE="${FACTORY_RUN_SINGLE:-${SCRIPT_DIR}/run_single_job.sh}"

mkdir -p "${STATE_DIR}"

shopt -s nullglob
mapfile -t JOBS < <(printf '%s\n' "${JOBS_DIR}"/[0-9][0-9]-*.md | sort)

if [[ "${#JOBS[@]}" -eq 0 ]]; then
  echo "No factory jobs found under ${JOBS_DIR}" >&2
  exit 2
fi

for job in "${JOBS[@]}"; do
  marker="${STATE_DIR}/$(basename "${job}" .md).done"
  if [[ -f "${marker}" ]]; then
    echo "Skipping completed job: ${job}"
    continue
  fi

  echo "Running job: ${job}"
  "${RUN_SINGLE}" "${job}"
  touch "${marker}"
done
