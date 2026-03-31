#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/workspace/wan2.2/Wan2.2}"
VENV_DIR="${VENV_DIR:-.venv}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
LOG_FILE="${LOG_FILE:-${REPO_DIR}/api.log}"
PID_FILE="${PID_FILE:-${REPO_DIR}/api.pid}"

cd "${REPO_DIR}"
source "${VENV_DIR}/bin/activate"

if [[ -f "${PID_FILE}" ]]; then
  old_pid="$(cat "${PID_FILE}" || true)"
  if [[ -n "${old_pid}" ]] && kill -0 "${old_pid}" 2>/dev/null; then
    echo "API already running (pid=${old_pid})."
    exit 0
  fi
fi

nohup uvicorn api_server:app --host "${HOST}" --port "${PORT}" > "${LOG_FILE}" 2>&1 &
new_pid=$!
echo "${new_pid}" > "${PID_FILE}"
sleep 1

if kill -0 "${new_pid}" 2>/dev/null; then
  echo "API started (pid=${new_pid}) on ${HOST}:${PORT}"
  echo "Log: ${LOG_FILE}"
else
  echo "Failed to start API. Check log: ${LOG_FILE}"
  exit 1
fi
