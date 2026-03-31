# Wan2.2 A14B Reinstall Guide (RunPod)

This runbook is based on the exact errors encountered during setup and the fixes that worked.

Use this when recreating your pod/volume from scratch.

Quick path: run `bootstrap_runpod.sh` (added in this repo) for one-shot setup.

---

## 0) What to provision before starting

- GPU: `A100 80GB` (single GPU for A14B single-node runs)
- Storage:
  - Avoid tiny root-only setups.
  - Use a persistent workspace volume with enough capacity.
  - Practical targets:
    - Minimal working for one A14B family: a few hundred GB.
    - Comfortable for multiple A14B families + cache + outputs: 1.5TB+.
- Important: keep model/cache/temp under `/workspace`, not root overlay.

---

## 1) Start pod and base setup

```bash
cd /workspace
mkdir -p /workspace/wan2.2
cd /workspace/wan2.2

apt-get update && apt-get install -y git build-essential ninja-build
```

One-shot alternative after cloning:

```bash
cd /workspace/wan2.2/Wan2.2
bash bootstrap_runpod.sh
```

Optional flags:

```bash
INSTALL_S2V=1 INSTALL_ANIMATE=1 DOWNLOAD_T2V=1 bash bootstrap_runpod.sh
```

Clone your repo:

```bash
git clone https://github.com/calvinti12/Wan2.2.git
cd Wan2.2
```

If you need upstream updates from the official project later:

```bash
cd /workspace/wan2.2/Wan2.2
git remote add upstream https://github.com/Wan-Video/Wan2.2.git
git fetch upstream
```

Create venv:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip setuptools wheel
```

---

## 2) Critical env vars (prevents disk/tmp quota problems)

Set these before large downloads/builds:

```bash
mkdir -p /workspace/wan2.2/tmp /workspace/wan2.2/hf-home
export TMPDIR=/workspace/wan2.2/tmp
export HF_HOME=/workspace/wan2.2/hf-home
```

Why: we hit `Disk quota exceeded` during HF downloads. This helps keep temp/cache off the small root overlay.

---

## 3) Install PyTorch first (known good combo)

Use the version set that worked with flash-attn:

```bash
pip install torch==2.5.1+cu124 torchvision==0.20.1+cu124 torchaudio==2.5.1+cu124 --index-url https://download.pytorch.org/whl/cu124
pip install "numpy>=1.23.5,<2"
```

Sanity check:

```bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Expected: CUDA is `True` and device is your NVIDIA GPU.

---

## 4) Install repo requirements and flash-attn

Install requirements:

```bash
pip install -r requirements.txt
```

If `flash_attn` fails, use:

```bash
pip install psutil ninja packaging wheel setuptools einops
nvcc --version
MAX_JOBS=4 pip install flash-attn --no-build-isolation --no-cache-dir
```

### Known failures and fixes

1. `ModuleNotFoundError: No module named 'torch'` during flash-attn build  
   - Cause: build isolation not seeing torch  
   - Fix: `--no-build-isolation`

2. `ModuleNotFoundError: No module named 'psutil'`  
   - Fix: `pip install psutil`

3. `ImportError ... flash_attn_2_cuda... undefined symbol ... c10::Error`  
   - Cause: binary mismatch with torch  
   - Fix: pin torch stack to `2.5.1+cu124` and rebuild flash-attn from source.

---

## 5) Install extras that became required in practice

Even for `t2v`, importing `wan` can pull modules that need `decord`.

Install:

```bash
pip install decord
pip install peft
```

If needed:

```bash
pip install decord --prefer-binary
```

Optional (task-specific bundles):

```bash
pip install -r requirements_s2v.txt
pip install -r requirements_animate.txt
```

---

## 6) Verify full Python stack quickly

```bash
python -c "import torch, flash_attn, decord, peft; print('ok', torch.__version__)"
```

If this passes, environment is healthy.

---

## 7) Hugging Face auth + download

Install CLI:

```bash
pip install "huggingface_hub[cli]"
```

Login:

```bash
hf auth login
```

Download T2V A14B:

```bash
hf download Wan-AI/Wan2.2-T2V-A14B --local-dir ./Wan2.2-T2V-A14B
```

If interrupted, rerun the same command; it resumes.

---

## 8) First generation command (T2V)

```bash
python generate.py --task t2v-A14B --size '1280*720' --ckpt_dir ./Wan2.2-T2V-A14B --offload_model True --convert_model_dtype --prompt "Two anthropomorphic cats in comfy boxing gear and bright gloves fight intensely on a spotlighted stage."
```

### Known command typo to avoid

Wrong:

```bash
--offload_modelTrue
```

Correct:

```bash
--offload_model True
```

---

## 9) Next model downloads/tests

I2V:

```bash
hf download Wan-AI/Wan2.2-I2V-A14B --local-dir ./Wan2.2-I2V-A14B
python generate.py --task i2v-A14B --size '1280*720' --ckpt_dir ./Wan2.2-I2V-A14B --offload_model True --convert_model_dtype --image examples/i2v_input.JPG --prompt "Summer beach vacation style, a white cat wearing sunglasses sits on a surfboard."
```

S2V:

```bash
pip install -r requirements_s2v.txt
hf download Wan-AI/Wan2.2-S2V-14B --local-dir ./Wan2.2-S2V-14B
python generate.py --task s2v-14B --size '1024*704' --ckpt_dir ./Wan2.2-S2V-14B --offload_model True --convert_model_dtype --prompt "Summer beach vacation style, a white cat wearing sunglasses sits on a surfboard." --image examples/i2v_input.JPG --audio examples/talk.wav
```

Animate:

```bash
pip install -r requirements_animate.txt
hf download Wan-AI/Wan2.2-Animate-14B --local-dir ./Wan2.2-Animate-14B
```

Then follow preprocessing in:

- `README.md`
- `wan/modules/animate/preprocess/UserGuider.md`

---

## 10) Cost control checklist

- Stop pod when not using GPU.
- Keep only required checkpoints locally.
- Keep caches under `/workspace` (with `TMPDIR`/`HF_HOME`) to avoid root disk surprises.
- If storage billing is high, reduce provisioned volume size and rotate models instead of keeping all at once.

---

## 11) Fast troubleshooting checklist

1. GPU visible?
```bash
nvidia-smi
```

2. Torch CUDA OK?
```bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

3. Flash-attn import OK?
```bash
python -c "import flash_attn; print('flash-attn ok')"
```

4. Decord import OK?
```bash
python -c "import decord; print('decord ok')"
```

5. Space pressure?
```bash
df -h . / /tmp
du -sh ./Wan2.2-*
```

