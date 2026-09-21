from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import yaml
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

ROOT = Path(os.getenv("MUSETALK_ROOT", "/opt/MuseTalk"))
RESULTS = Path(os.getenv("MUSETALK_RESULTS", "/tmp/musetalk-results"))
RESULTS.mkdir(parents=True, exist_ok=True)
TOKEN = str(os.getenv("MUSETALK_API_TOKEN", "") or "").strip()

app = FastAPI(title="Cenara MuseTalk Worker", version="1.0")


def auth(header: str | None):
    if TOKEN and header != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/health")
def health():
    checkpoint = ROOT / "models" / "musetalkV15" / "unet.pth"
    return {
        "ok": ROOT.is_dir() and checkpoint.is_file(),
        "engine": "MuseTalk",
        "version": "1.5",
        "checkpoint": checkpoint.is_file(),
    }


@app.post("/lipsync")
async def lipsync(
    face: UploadFile = File(...),
    audio: UploadFile = File(...),
    version: str = Form("v15"),
    authorization: str | None = Header(default=None),
):
    auth(authorization)
    job = RESULTS / uuid.uuid4().hex
    job.mkdir(parents=True, exist_ok=True)
    face_path = job / ("face.png" if "png" in (face.content_type or "") else "face.jpg")
    audio_path = job / "audio.mp3"
    face_path.write_bytes(await face.read())
    audio_path.write_bytes(await audio.read())

    cfg = {
        "task_0": {
            "video_path": str(face_path),
            "audio_path": str(audio_path),
        }
    }
    cfg_path = job / "inference.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    result_dir = job / "out"
    result_dir.mkdir(parents=True, exist_ok=True)

    if version != "v15":
        raise HTTPException(status_code=400, detail="Only MuseTalk v1.5 is enabled")

    cmd = [
        "python", "-m", "scripts.inference",
        "--inference_config", str(cfg_path),
        "--result_dir", str(result_dir),
        "--unet_model_path", str(ROOT / "models" / "musetalkV15" / "unet.pth"),
        "--unet_config", str(ROOT / "models" / "musetalkV15" / "musetalk.json"),
        "--version", "v15",
        "--ffmpeg_path", os.getenv("FFMPEG_PATH", "/usr/bin"),
        "--use_float16",
    ]
    try:
        subprocess.run(cmd, cwd=str(ROOT), check=True, capture_output=True, text=True, timeout=1800)
    except subprocess.CalledProcessError as exc:
        raise HTTPException(status_code=500, detail=(exc.stderr or exc.stdout or "MuseTalk failed")[-1200:])
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="MuseTalk timed out")

    candidates = sorted(result_dir.rglob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise HTTPException(status_code=500, detail="MuseTalk produced no MP4")
    final = candidates[0]
    return FileResponse(str(final), media_type="video/mp4", filename="musetalk.mp4")
