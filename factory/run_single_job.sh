#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <job-file>" >&2
  exit 2
fi

JOB_FILE_INPUT="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${REPO_ROOT}/factory/logs"
MODEL="${CLAUDE_MODEL:-opus}"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"

if [[ ! -x "$(command -v "${CLAUDE_BIN}" 2>/dev/null || true)" ]]; then
  echo "required command not found on PATH: ${CLAUDE_BIN}" >&2
  exit 2
fi

if [[ ! -f "${JOB_FILE_INPUT}" ]]; then
  echo "job file not found: ${JOB_FILE_INPUT}" >&2
  exit 2
fi

mkdir -p "${LOG_DIR}"

JOB_FILE="$(python3 - <<'PY' "${REPO_ROOT}" "${JOB_FILE_INPUT}"
import pathlib
import sys

repo_root = pathlib.Path(sys.argv[1]).resolve()
job_file = pathlib.Path(sys.argv[2]).resolve()
print(job_file.relative_to(repo_root))
PY
)"

JOB_BASENAME="$(basename "${JOB_FILE}" .md)"
LOG_FILE="${LOG_DIR}/${JOB_BASENAME}.log"

READ_FILES=()
READ_CANDIDATES=(
  "AGENTS.md"
  "WORKFLOW.md"
  "SPEC.md"
  "docs/v1-game-contract.md"
  "HANDOFF.md"
  "STATUS.md"
  "ROADMAP.md"
  "BOOTSTRAP.md"
  "factory-jobs/README.md"
  "${JOB_FILE}"
)
for rel in "${READ_CANDIDATES[@]}"; do
  if [[ -f "${REPO_ROOT}/${rel}" ]]; then
    READ_FILES+=("${rel}")
  fi
done

READ_BLOCK=""
for rel in "${READ_FILES[@]}"; do
  READ_BLOCK="${READ_BLOCK}- ${rel}"$'\n'
done

read -r -d '' PROMPT <<EOF || true
Read these existing files in order before starting:

${READ_BLOCK}
Execute only the assigned job in this repository.

Constraints:
- stay strictly within the assigned job scope
- use WORKFLOW.md as the authoritative phase plan when present
- update HANDOFF.md and STATUS.md before stopping
- update WORKFLOW.md if the phase status or notes materially changed
- do not create git commits unless the operator explicitly changes that rule
- prefer Makefile-managed operations when adding repeated tooling
- preserve blockers and high-signal failure context rather than improvising later phases

At the end, summarize:
1. what changed
2. verification run
3. blocker or next recommendation
EOF

CLAUDE_CMD=(
  "${CLAUDE_BIN}"
  -p
  --model "${MODEL}"
  --output-format text
  --permission-mode bypassPermissions
  "${PROMPT}"
)

(
  cd "${REPO_ROOT}"
  "${CLAUDE_CMD[@]}"
) | tee "${LOG_FILE}"
