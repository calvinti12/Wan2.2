# Wan2.2 API Deployment (RunPod)

This adds a simple HTTP API for T2V generation using your existing setup.

Repo source of truth:

- `https://github.com/calvinti12/Wan2.2.git`

Fresh pod bootstrap:

```bash
cd /workspace
mkdir -p /workspace/wan2.2
cd /workspace/wan2.2
git clone https://github.com/calvinti12/Wan2.2.git
cd Wan2.2
```

## 1) Install API deps

```bash
cd /workspace/wan2.2/Wan2.2
source .venv/bin/activate
pip install fastapi "uvicorn[standard]"
```

### If you are browser-only (no local `scp`)

If your pod was cloned from `https://github.com/calvinti12/Wan2.2.git`, these files should already exist.
If they are missing, create them from the browser terminal:

1. Open the file in your local editor.
2. In pod terminal, run:

```bash
cd /workspace/wan2.2/Wan2.2
cat > api_server.py <<'EOF'
# paste full api_server.py content here
EOF
```

3. Repeat for the second script:

```bash
cd /workspace/wan2.2/Wan2.2
cat > auto_pod_generate.py <<'EOF'
# paste full auto_pod_generate.py content here
EOF
```

4. Verify files exist:

```bash
ls -la /workspace/wan2.2/Wan2.2 | grep -E "api_server.py|auto_pod_generate.py"
```

If your browser terminal supports editor upload, you can also use that UI instead of copy/paste.

## 2) Start the API

```bash
cd /workspace/wan2.2/Wan2.2
source .venv/bin/activate
uvicorn api_server:app --host 0.0.0.0 --port 8000
```

Expose port `8000` in your pod networking so you can call it externally.

### Start/stop without browser terminal (recommended)

This repo includes:

- `start_api.sh`
- `stop_api.sh`
- `status_api.sh`

Run on pod:

```bash
cd /workspace/wan2.2/Wan2.2
bash start_api.sh
bash status_api.sh
```

Stop:

```bash
cd /workspace/wan2.2/Wan2.2
bash stop_api.sh
```

From your local terminal via SSH (example):

```bash
ssh -p YOUR_SSH_PORT root@YOUR_POD_IP "cd /workspace/wan2.2/Wan2.2 && bash start_api.sh"
ssh -p YOUR_SSH_PORT root@YOUR_POD_IP "cd /workspace/wan2.2/Wan2.2 && bash status_api.sh"
ssh -p YOUR_SSH_PORT root@YOUR_POD_IP "cd /workspace/wan2.2/Wan2.2 && bash stop_api.sh"
```

## 3) Call the API

Create a job:

```bash
curl -X POST "http://YOUR_POD_HOST:8000/generate/t2v" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Two anthropomorphic cats in comfy boxing gear and bright gloves fight intensely on a spotlighted stage.",
    "ckpt_dir": "./Wan2.2-T2V-A14B",
    "size": "1280*720",
    "offload_model": true,
    "convert_model_dtype": true
  }'
```

Poll status:

```bash
curl "http://YOUR_POD_HOST:8000/jobs/JOB_ID"
```

When status is `completed`, download:

```bash
curl -L "http://YOUR_POD_HOST:8000/videos/JOB_ID.mp4" --output output.mp4
```

## 4) Can I call API while pod is OFF?

No. A stopped pod cannot receive HTTP requests.

Use one of these patterns:

1. Keep pod on while serving API.
2. Use an external orchestrator:
   - receives user request,
   - starts your RunPod pod via RunPod API,
   - waits for health check (`/health`),
   - submits generation request,
   - downloads result,
   - stops pod again.

## 5) One-command auto start/generate/stop

Use `auto_pod_generate.py` from your local machine (or another always-on machine).

### Prereqs

- Python 3.9+
- `pip install requests`
- Your RunPod API key + Pod ID
- Pod API (`uvicorn api_server:app --host 0.0.0.0 --port 8000`) configured on startup

### Env vars

```bash
export RUNPOD_API_KEY="your_runpod_api_key"
export RUNPOD_POD_ID="your_pod_id"
```

### Run

```bash
python auto_pod_generate.py \
  --prompt "Two anthropomorphic cats in comfy boxing gear and bright gloves fight intensely on a spotlighted stage." \
  --output outputs/cats.mp4
```

Optional flags:

- `--api-port 8000` (default 8000)
- `--startup-timeout 1200`
- `--job-timeout 7200`
- `--leave-running` (skip auto-stop)

Script behavior:

1. Starts pod if it is stopped
2. Polls RunPod for public IP/port mapping
3. Waits for `/health`
4. Sends `/generate/t2v`
5. Polls `/jobs/{id}`
6. Downloads video
7. Stops pod (unless `--leave-running`)

## 6) Notes

- `api_server.py` currently exposes `t2v-A14B` only.
- Jobs are in-memory (lost when process restarts).
- Videos are saved under `api_outputs/`.
