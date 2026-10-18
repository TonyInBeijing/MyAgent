#!/usr/bin/env bash
# Ensure local Ollama is up and qwen3.5:9b is ready for MyAgent.
# Usage:
#   ./scripts/ollama_qwen3.5.sh          # start / check (default)
#   ./scripts/ollama_qwen3.5.sh status   # only check readiness
#   ./scripts/ollama_qwen3.5.sh stop     # stop Ollama started by this script
#   source ./scripts/ollama_qwen3.5.sh   # export env for current shell

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PID_FILE="${ROOT_DIR}/.myagent/ollama.pid"
LOG_FILE="${ROOT_DIR}/.myagent/ollama.log"
MODEL="${OLLAMA_MODEL:-qwen3.5:9b}"
DEFAULT_HOST="http://127.0.0.1:11434"
ACTION="${1:-start}"

load_dotenv() {
  local env_file="${ROOT_DIR}/.env"
  if [[ -f "${env_file}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${env_file}"
    set +a
  fi
}

normalize_host() {
  local host="${OLLAMA_HOST:-}"
  if [[ -z "${host}" ]]; then
    host="${DEFAULT_HOST}"
  fi
  # Allow host:port without scheme
  if [[ "${host}" != http://* && "${host}" != https://* ]]; then
    host="http://${host}"
  fi
  # Trim trailing slash
  host="${host%/}"
  export OLLAMA_HOST="${host}"
  export OLLAMA_MODEL="${MODEL}"
}

is_ready() {
  curl -sf "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1
}

wait_ready() {
  local retries="${1:-30}"
  local i
  for ((i = 1; i <= retries; i++)); do
    if is_ready; then
      return 0
    fi
    sleep 1
  done
  return 1
}

ensure_dirs() {
  mkdir -p "${ROOT_DIR}/.myagent"
}

start_server() {
  if is_ready; then
    echo "[ollama] already running at ${OLLAMA_HOST}"
    return 0
  fi

  if ! command -v ollama >/dev/null 2>&1; then
    echo "[ollama] error: 'ollama' not found in PATH" >&2
    exit 1
  fi

  ensure_dirs
  echo "[ollama] starting server (OLLAMA_HOST=${OLLAMA_HOST}) ..."
  # Prefer system service when available; fall back to background serve.
  if command -v systemctl >/dev/null 2>&1 && systemctl cat ollama >/dev/null 2>&1; then
    if systemctl is-active --quiet ollama 2>/dev/null; then
      :
    else
      systemctl start ollama >/dev/null 2>&1 || true
    fi
    if wait_ready 15; then
      echo "[ollama] ready via systemd"
      return 0
    fi
  fi

  nohup ollama serve >>"${LOG_FILE}" 2>&1 &
  local pid=$!
  echo "${pid}" >"${PID_FILE}"
  if ! wait_ready 30; then
    echo "[ollama] error: server failed to become ready. See ${LOG_FILE}" >&2
    exit 1
  fi
  echo "[ollama] started (pid ${pid}), log: ${LOG_FILE}"
}

ensure_model() {
  if ! command -v ollama >/dev/null 2>&1; then
    echo "[ollama] error: 'ollama' not found in PATH" >&2
    exit 1
  fi

  if ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -qx "${MODEL}"; then
    echo "[ollama] model ready: ${MODEL}"
    return 0
  fi

  echo "[ollama] pulling model ${MODEL} ..."
  ollama pull "${MODEL}"
  echo "[ollama] model ready: ${MODEL}"
}

warmup_model() {
  # Load model into memory so the first real request is faster.
  echo "[ollama] warming up ${MODEL} ..."
  curl -sf "${OLLAMA_HOST}/api/chat" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"${MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"stream\":false,\"options\":{\"num_predict\":1}}" \
    >/dev/null
  echo "[ollama] warmup done"
}

print_status() {
  if is_ready; then
    echo "[ollama] status: ready (${OLLAMA_HOST})"
    ollama list 2>/dev/null | awk -v m="${MODEL}" '
      NR==1 {print; next}
      $1==m {print; found=1}
      END { if (!found) print "  (model " m " not listed)" }
    '
  else
    echo "[ollama] status: not reachable at ${OLLAMA_HOST}"
    return 1
  fi
}

stop_server() {
  if [[ -f "${PID_FILE}" ]]; then
    local pid
    pid="$(cat "${PID_FILE}")"
    if kill -0 "${pid}" 2>/dev/null; then
      echo "[ollama] stopping pid ${pid} ..."
      kill "${pid}" 2>/dev/null || true
      wait "${pid}" 2>/dev/null || true
    fi
    rm -f "${PID_FILE}"
    echo "[ollama] stopped"
  else
    echo "[ollama] no pid file; skip stop (systemd-managed instances are left running)"
  fi
}

main() {
  load_dotenv
  normalize_host

  case "${ACTION}" in
    start)
      start_server
      ensure_model
      warmup_model
      print_status
      ;;
    status)
      print_status
      ;;
    stop)
      stop_server
      ;;
    *)
      echo "Usage: $0 [start|status|stop]" >&2
      exit 2
      ;;
  esac
}

# When sourced, prepare env + server for the parent process (e.g. start.sh).
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
  load_dotenv
  normalize_host
  start_server
  ensure_model
  warmup_model
else
  main
fi
