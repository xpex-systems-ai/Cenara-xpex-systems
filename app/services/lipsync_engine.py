from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests
from loguru import logger


def _valid_mp4(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 100_000


def _remote_musetalk(face: Path, audio: Path, output: Path) -> bool:
    url = str(os.getenv("CENARA_MUSETALK_API_URL", "") or "").strip().rstrip("/")
    if not url:
        return False
    token = str(os.getenv("CENARA_MUSETALK_API_TOKEN", "") or "").strip()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        with face.open("rb") as face_fh, audio.open("rb") as audio_fh:
            response = requests.post(
                f"{url}/lipsync",
                headers=headers,
                files={
                    "face": (face.name, face_fh, "image/jpeg"),
                    "audio": (audio.name, audio_fh, "audio/mpeg"),
                },
                data={"version": os.getenv("CENARA_MUSETALK_VERSION", "v15")},
                timeout=(30, 1800),
            )
        if response.status_code >= 400:
            logger.warning(f"MuseTalk remote failed http={response.status_code}")
            return False
        ctype = str(response.headers.get("content-type", "")).lower()
        if "video" not in ctype and len(response.content) < 100_000:
            return False
        output.write_bytes(response.content)
        return _valid_mp4(output)
    except Exception as exc:
        logger.warning(f"MuseTalk remote unavailable: {type(exc).__name__}")
        return False


def _local_wav2lip_noncommercial(face: Path, audio: Path, output: Path) -> bool:
    # The upstream open-source Wav2Lip weights are explicitly non-commercial.
    # Keep this disabled by default for XPeX production.
    if str(os.getenv("CENARA_ALLOW_NONCOMMERCIAL_WAV2LIP", "0")) != "1":
        return False
    wav2lip_dir = Path(str(os.getenv("CENARA_WAV2LIP_DIR", "") or "").strip())
    checkpoint = Path(str(os.getenv("CENARA_WAV2LIP_CHECKPOINT", "") or "").strip())
    if not wav2lip_dir.is_dir() or not checkpoint.is_file():
        return False
    inference = wav2lip_dir / "inference.py"
    if not inference.is_file():
        return False
    python_bin = str(os.getenv("CENARA_WAV2LIP_PYTHON", "python") or "python")
    try:
        subprocess.run(
            [
                python_bin, str(inference),
                "--checkpoint_path", str(checkpoint),
                "--face", str(face),
                "--audio", str(audio),
                "--outfile", str(output),
            ],
            cwd=str(wav2lip_dir),
            check=True,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        return _valid_mp4(output)
    except Exception as exc:
        logger.warning(f"Wav2Lip research fallback failed: {type(exc).__name__}")
        return False


def render_lipsync(face: Path, audio: Path, output: Path) -> tuple[bool, str]:
    """Production priority: MuseTalk remote -> research-only Wav2Lip -> caller fallback."""
    output.parent.mkdir(parents=True, exist_ok=True)
    if _remote_musetalk(face, audio, output):
        return True, "musetalk_v15"
    if _local_wav2lip_noncommercial(face, audio, output):
        return True, "wav2lip_noncommercial"
    return False, "unavailable"
