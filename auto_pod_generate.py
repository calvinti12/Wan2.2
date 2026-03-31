#!/usr/bin/env python3
import argparse
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests


RUNPOD_BASE = "https://rest.runpod.io/v1"


def _headers(api_key: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def runpod_start_pod(api_key: str, pod_id: str) -> None:
    r = requests.post(f"{RUNPOD_BASE}/pods/{pod_id}/start", headers=_headers(api_key), timeout=30)
    if r.status_code not in (200, 202):
        raise RuntimeError(f"Failed to start pod: {r.status_code} {r.text}")


def runpod_stop_pod(api_key: str, pod_id: str) -> None:
    r = requests.post(f"{RUNPOD_BASE}/pods/{pod_id}/stop", headers=_headers(api_key), timeout=30)
    if r.status_code not in (200, 202):
        raise RuntimeError(f"Failed to stop pod: {r.status_code} {r.text}")


def runpod_get_pod(api_key: str, pod_id: str) -> Dict[str, Any]:
    r = requests.get(f"{RUNPOD_BASE}/pods/{pod_id}", headers=_headers(api_key), timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Failed to get pod: {r.status_code} {r.text}")
    return r.json()


def resolve_api_base_url(pod: Dict[str, Any], api_port: int) -> Optional[str]:
    public_ip = pod.get("publicIp")
    port_mappings = pod.get("portMappings") or {}
    mapped = port_mappings.get(str(api_port))
    if public_ip and mapped:
        return f"http://{public_ip}:{mapped}"
    return None


def wait_for_pod_and_api(
    api_key: str,
    pod_id: str,
    timeout_s: int,
    api_port: int,
    explicit_api_base_url: Optional[str] = None,
) -> str:
    deadline = time.time() + timeout_s
    last_status = None
    api_base = explicit_api_base_url

    while time.time() < deadline:
        pod = runpod_get_pod(api_key, pod_id)
        status = pod.get("desiredStatus")
        if status != last_status:
            print(f"[wait] Pod desiredStatus={status}")
            last_status = status

        if not api_base and status == "RUNNING":
            api_base = resolve_api_base_url(pod, api_port)
            if api_base:
                print(f"[wait] Resolved API URL: {api_base}")

        if api_base:
            try:
                r = requests.get(f"{api_base}/health", timeout=5)
                if r.status_code == 200:
                    print("[wait] API is healthy.")
                    return api_base
            except Exception:
                pass

        time.sleep(5)

    raise TimeoutError("Timed out waiting for pod/API readiness.")


def submit_job(
    api_base_url: str,
    prompt: str,
    ckpt_dir: str,
    size: str,
    offload_model: bool,
    convert_model_dtype: bool,
) -> str:
    payload = {
        "prompt": prompt,
        "ckpt_dir": ckpt_dir,
        "size": size,
        "offload_model": offload_model,
        "convert_model_dtype": convert_model_dtype,
    }
    r = requests.post(f"{api_base_url}/generate/t2v", json=payload, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Failed to submit job: {r.status_code} {r.text}")
    data = r.json()
    return data["job_id"]


def wait_for_job(api_base_url: str, job_id: str, timeout_s: int) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = requests.get(f"{api_base_url}/jobs/{job_id}", timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"Job status failed: {r.status_code} {r.text}")
        data = r.json()
        status = data.get("status")
        print(f"[job] {job_id}: {status}")
        if status == "completed":
            return data
        if status == "failed":
            raise RuntimeError(f"Generation failed: {data.get('error')}\n{data.get('logs_tail', '')}")
        time.sleep(5)
    raise TimeoutError("Timed out waiting for generation job.")


def download_video(api_base_url: str, video_url: str, out_file: Path) -> None:
    url = f"{api_base_url}{video_url}" if video_url.startswith("/") else video_url
    with requests.get(url, stream=True, timeout=120) as r:
        if r.status_code != 200:
            raise RuntimeError(f"Video download failed: {r.status_code} {r.text}")
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with out_file.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


def main() -> None:
    parser = argparse.ArgumentParser(description="Start RunPod pod, generate T2V video, download, stop pod.")
    parser.add_argument("--pod-id", default=os.getenv("RUNPOD_POD_ID"))
    parser.add_argument("--runpod-api-key", default=os.getenv("RUNPOD_API_KEY"))
    parser.add_argument("--api-base-url", default=os.getenv("WAN_API_BASE_URL"))
    parser.add_argument("--api-port", type=int, default=int(os.getenv("WAN_API_PORT", "8000")))
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--ckpt-dir", default="./Wan2.2-T2V-A14B")
    parser.add_argument("--size", default="1280*720")
    parser.add_argument("--offload-model", action="store_true", default=True)
    parser.add_argument("--no-offload-model", action="store_false", dest="offload_model")
    parser.add_argument("--convert-model-dtype", action="store_true", default=True)
    parser.add_argument("--no-convert-model-dtype", action="store_false", dest="convert_model_dtype")
    parser.add_argument("--startup-timeout", type=int, default=1200)
    parser.add_argument("--job-timeout", type=int, default=7200)
    parser.add_argument("--output", default="outputs/generated.mp4")
    parser.add_argument("--leave-running", action="store_true", help="Do not stop pod at the end.")
    args = parser.parse_args()

    if not args.pod_id:
        raise SystemExit("Missing --pod-id or RUNPOD_POD_ID.")
    if not args.runpod_api_key:
        raise SystemExit("Missing --runpod-api-key or RUNPOD_API_KEY.")

    started_here = False
    try:
        pod = runpod_get_pod(args.runpod_api_key, args.pod_id)
        if pod.get("desiredStatus") != "RUNNING":
            print("[pod] Starting pod...")
            runpod_start_pod(args.runpod_api_key, args.pod_id)
            started_here = True
        else:
            print("[pod] Pod already running.")

        api_base_url = wait_for_pod_and_api(
            api_key=args.runpod_api_key,
            pod_id=args.pod_id,
            timeout_s=args.startup_timeout,
            api_port=args.api_port,
            explicit_api_base_url=args.api_base_url,
        )

        print("[job] Submitting generation request...")
        job_id = submit_job(
            api_base_url=api_base_url,
            prompt=args.prompt,
            ckpt_dir=args.ckpt_dir,
            size=args.size,
            offload_model=args.offload_model,
            convert_model_dtype=args.convert_model_dtype,
        )
        print(f"[job] Submitted: {job_id}")

        result = wait_for_job(api_base_url, job_id, timeout_s=args.job_timeout)
        video_url = result.get("video_url")
        if not video_url:
            raise RuntimeError("Job completed but no video_url returned.")

        out_file = Path(args.output)
        print(f"[job] Downloading to {out_file} ...")
        download_video(api_base_url, video_url, out_file)
        print(f"[done] Saved video: {out_file}")

    finally:
        if not args.leave_running and started_here:
            try:
                print("[pod] Stopping pod...")
                runpod_stop_pod(args.runpod_api_key, args.pod_id)
                print("[pod] Stop requested.")
            except Exception as e:
                print(f"[warn] Failed to stop pod automatically: {e}")


if __name__ == "__main__":
    main()
