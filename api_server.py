import os
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "api_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

JOBS_LOCK = threading.Lock()
GEN_LOCK = threading.Lock()  # serialize GPU generation
JOBS: Dict[str, "JobState"] = {}


@dataclass
class JobState:
    id: str
    status: str = "queued"  # queued | running | completed | failed
    output_file: Optional[str] = None
    error: Optional[str] = None
    logs: str = ""


class T2VRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    ckpt_dir: str = "./Wan2.2-T2V-A14B"
    size: str = "1280*720"
    offload_model: bool = True
    convert_model_dtype: bool = True


app = FastAPI(title="Wan2.2 API", version="0.1.0")


def _run_t2v_job(job_id: str, req: T2VRequest) -> None:
    output_file = OUTPUT_DIR / f"{job_id}.mp4"
    cmd = [
        "python",
        "generate.py",
        "--task",
        "t2v-A14B",
        "--size",
        req.size,
        "--ckpt_dir",
        req.ckpt_dir,
        "--offload_model",
        str(req.offload_model),
        "--prompt",
        req.prompt,
        "--save_file",
        str(output_file),
    ]
    if req.convert_model_dtype:
        cmd.append("--convert_model_dtype")

    with JOBS_LOCK:
        JOBS[job_id].status = "running"

    # One generation at a time on a single GPU instance.
    with GEN_LOCK:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )

    logs = (proc.stdout or "") + "\n" + (proc.stderr or "")
    with JOBS_LOCK:
        JOBS[job_id].logs = logs[-12000:]
        if proc.returncode == 0 and output_file.exists():
            JOBS[job_id].status = "completed"
            JOBS[job_id].output_file = output_file.name
        else:
            JOBS[job_id].status = "failed"
            JOBS[job_id].error = f"generate.py exited with code {proc.returncode}"


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/generate/t2v")
def generate_t2v(req: T2VRequest):
    job_id = str(uuid.uuid4())
    state = JobState(id=job_id)
    with JOBS_LOCK:
        JOBS[job_id] = state

    t = threading.Thread(target=_run_t2v_job, args=(job_id, req), daemon=True)
    t.start()

    return {"job_id": job_id, "status_url": f"/jobs/{job_id}"}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    with JOBS_LOCK:
        state = JOBS.get(job_id)
        if not state:
            raise HTTPException(status_code=404, detail="Job not found")

        resp = {
            "id": state.id,
            "status": state.status,
            "error": state.error,
            "logs_tail": state.logs,
        }
        if state.status == "completed" and state.output_file:
            resp["video_url"] = f"/videos/{state.output_file}"
        return resp


@app.get("/videos/{filename}")
def get_video(filename: str):
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(path, media_type="video/mp4", filename=filename)
