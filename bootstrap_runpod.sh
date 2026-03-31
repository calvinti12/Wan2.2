#!/usr/bin/env bash
set -euo pipefail

# One-shot bootstrap for Wan2.2 on RunPod.
# Usage:
#   bash bootstrap_runpod.sh
# Optional env vars:
#   INSTALL_S2V=1 INSTALL_ANIMATE=1 DOWNLOAD_T2V=1 HF_TOKEN=xxx bash bootstrap_runpod.sh

REPO_DIR="${REPO_DIR:-/workspace/wan2.2/Wan2.2}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

INSTALL_S2V="${INSTALL_S2V:-0}"
INSTALL_ANIMATE="${INSTALL_ANIMATE:-0}"
DOWNLOAD_T2V="${DOWNLOAD_T2V:-0}"
T2V_CKPT_DIR="${T2V_CKPT_DIR:-./Wan2.2-T2V-A14B}"

echo "[1/8] Entering repo: ${REPO_DIR}"
cd "${REPO_DIR}"

echo "[2/8] Installing system packages"
apt-get update
apt-get install -y git build-essential ninja-build

echo "[3/8] Creating venv"
${PYTHON_BIN} -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"
pip install -U pip setuptools wheel

echo "[4/8] Installing PyTorch pinned stack"
pip install torch==2.5.1+cu124 torchvision==0.20.1+cu124 torchaudio==2.5.1+cu124 --index-url https://download.pytorch.org/whl/cu124
pip install "numpy>=1.23.5,<2"

echo "[5/8] Installing core dependencies"
pip install -r requirements.txt

echo "[6/8] Installing required extras discovered during setup"
pip install decord peft
pip install fastapi "uvicorn[standard]" "huggingface_hub[cli]"

if [[ "${INSTALL_S2V}" == "1" ]]; then
  echo "[extra] Installing S2V dependencies"
  pip install -r requirements_s2v.txt
fi

if [[ "${INSTALL_ANIMATE}" == "1" ]]; then
  echo "[extra] Installing Animate dependencies"
  pip install -r requirements_animate.txt
fi

echo "[7/8] Setting cache/tmp directories on /workspace"
mkdir -p /workspace/wan2.2/tmp /workspace/wan2.2/hf-home
export TMPDIR=/workspace/wan2.2/tmp
export HF_HOME=/workspace/wan2.2/hf-home

if [[ -n "${HF_TOKEN:-}" ]]; then
  echo "[extra] Logging in to Hugging Face token from env"
  hf auth login --token "${HF_TOKEN}"
fi

if [[ "${DOWNLOAD_T2V}" == "1" ]]; then
  echo "[extra] Downloading T2V weights"
  hf download Wan-AI/Wan2.2-T2V-A14B --local-dir "${T2V_CKPT_DIR}"
fi

echo "[8/8] Verifying environment"
python -c "import torch, flash_attn, decord, peft; print('OK', torch.__version__, torch.cuda.is_available())"
echo "Done."
echo "Next:"
echo "  source ${VENV_DIR}/bin/activate"
echo "  uvicorn api_server:app --host 0.0.0.0 --port 8000"
