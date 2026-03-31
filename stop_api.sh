#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/workspace/wan2.2/Wan2.2}"
PID_FILE="${PID_FILE:-${REPO_DIR}/api.pid}"

if [[ ! -f "${PID_FILE}" ]]; then
  echo "No pid file found: ${PID_FILE}"
  exit 0
fi

pid="$(cat "${PID_FILE}" || true)"
if [[ -z "${pid}" ]]; then
  echo "Empty pid file: ${PID_FILE}"
  rm -f "${PID_FILE}"
  exit 0
fi

if kill -0 "${pid}" 2>/dev/null; then
  kill "${pid}"
  sleep 1
  if kill -0 "${pid}" 2>/dev/null; then
    echo "PID ${pid} still running, sending SIGKILL..."
    kill -9 "${pid}" || true
  fi
  echo "API stopped (pid=${pid})."
else
  echo "Process ${pid} not running."
fi

rm -f "${PID_FILE}"
