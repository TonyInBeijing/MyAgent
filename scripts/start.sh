#!/usr/bin/env bash
# One-shot launcher: activate conda → ensure Ollama + qwen3.5:9b → enter chat.
#
# Usage:
#   ./scripts/start.sh                 # prepare + interactive chat
#   ./scripts/start.sh -v              # chat with verbose tool traces
#   ./scripts/start.sh "算一下 1+1"    # single-shot message then exit
#   ./scripts/start.sh --ollama-only   # only prepare Ollama / model
#   ./scripts/start.sh -- tools        # pass through to myagent (tools/skills/…)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONDA_ENV_NAME="${MYAGENT_CONDA_ENV:-my-agent}"
OLLAMA_ONLY=0
PASS_THROUGH=0
AGENT_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ollama-only)
      OLLAMA_ONLY=1
      shift
      ;;
    --)
      PASS_THROUGH=1
      shift
      AGENT_ARGS+=("$@")
      break
      ;;
    -h|--help)
      sed -n '2,12p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *)
      AGENT_ARGS+=("$1")
      shift
      ;;
  esac
done

activate_conda() {
  if ! command -v conda >/dev/null 2>&1; then
    echo "[start] error: conda not found in PATH" >&2
    exit 1
  fi
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
  if ! conda env list | awk '{print $1}' | grep -qx "${CONDA_ENV_NAME}"; then
    echo "[start] error: conda env '${CONDA_ENV_NAME}' not found" >&2
    echo "[start] create it or set MYAGENT_CONDA_ENV=your-env" >&2
    exit 1
  fi
  # shellcheck disable=SC1091
  conda activate "${CONDA_ENV_NAME}"
  echo "[start] conda env: ${CONDA_ENV_NAME} ($(command -v python))"
}

ensure_myagent() {
  if command -v myagent >/dev/null 2>&1; then
    return 0
  fi
  if [[ -f "${ROOT_DIR}/pyproject.toml" ]]; then
    echo "[start] myagent not on PATH; installing editable package …"
    pip install -e "${ROOT_DIR}"
  fi
  if ! command -v myagent >/dev/null 2>&1; then
    echo "[start] error: myagent CLI missing after install" >&2
    echo "[start] try: conda activate ${CONDA_ENV_NAME} && pip install -e ${ROOT_DIR}" >&2
    exit 1
  fi
}

echo "[start] project: ${ROOT_DIR}"
activate_conda
cd "${ROOT_DIR}"

# Starts Ollama if needed, pulls/warms qwen3.5:9b (see scripts/ollama_qwen3.5.sh)
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/ollama_qwen3.5.sh"

echo "[start] Ollama ready: ${OLLAMA_HOST} · model=${OLLAMA_MODEL}"

if [[ "${OLLAMA_ONLY}" -eq 1 ]]; then
  exit 0
fi

ensure_myagent

# Default: interactive chat. Bare args → myagent chat …
# With `--`: pass remaining args as the full myagent command (e.g. -- tools).
if [[ "${PASS_THROUGH}" -eq 1 ]]; then
  if [[ ${#AGENT_ARGS[@]} -eq 0 ]]; then
    exec myagent chat
  fi
  exec myagent "${AGENT_ARGS[@]}"
fi

exec myagent chat "${AGENT_ARGS[@]}"
