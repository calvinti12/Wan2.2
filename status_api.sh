#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/workspace/wan2.2/Wan2.2}"
PID_FILE="${PID_FILE:-${REPO_DIR}/api.pid}"
LOG_FILE="${LOG_FILE:-${REPO_DIR}/api.log}"
PORT="${PORT:-8000}"

if [[ -f "${PID_FILE}" ]]; then
  pid="$(cat "${PID_FILE}" || true)"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    echo "API running (pid=${pid})"
  else
    echo "PID file exists but process is not running."
  fi
else
  echo "API not running (no pid file)."
fi

echo "Health check (localhost:${PORT}):"
if command -v curl >/dev/null 2>&1; then
  curl -s "http://127.0.0.1:${PORT}/health" || true
  echo
fi

if [[ -f "${LOG_FILE}" ]]; then
  echo "Last 20 log lines:"
  tail -n 20 "${LOG_FILE}"
else
  echo "No log file yet: ${LOG_FILE}"
fi
