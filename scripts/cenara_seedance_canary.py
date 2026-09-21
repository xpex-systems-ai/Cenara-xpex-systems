"""One-shot real Seedance 2 canary for Cenara.

Uses the configured FAL_KEY, writes one short cinematic master to the persistent
Railway volume, validates it with ffprobe, and exits. Idempotent by output file.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import requests

from app.models.schema import VideoAspect
from app.services.frontier_media import FrontierMediaError, generate_video_url

OUT = Path("/MoneyPrinterTurbo/storage/canary/seedance2-first-flight.mp4")


def _valid_mp4(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 100_000:
        return False
    try:
        probe = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration,size",
                "-of", "json", str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        payload = json.loads(probe.stdout or "{}")
        duration = float(((payload.get("format") or {}).get("duration")) or 0)
        size = int(((payload.get("format") or {}).get("size")) or 0)
        return duration > 1 and size > 100_000
    except Exception:
        return False


def main() -> int:
    if os.getenv("CENARA_SEEDANCE_CANARY_ON_START", "0") != "1":
        print("SEEDANCE2_CANARY disabled")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if _valid_mp4(OUT):
        print(f"SEEDANCE2_CANARY PASS existing=true path={OUT} bytes={OUT.stat().st_size}")
        return 0

    prompt = (
        "Cinematic launch film for XPeX Academy. A futuristic premium AI learning "
        "studio at night, elegant dark navy environment with subtle cyan and warm "
        "orange accents, holographic knowledge interfaces, natural camera dolly, "
        "confident adult presenter silhouette interacting with floating AI diagrams, "
        "refined commercial lighting, sophisticated motion design feeling, clean "
        "composition, no on-screen text, no logos, no watermark."
    )

    try:
        url, model = generate_video_url(
            prompt,
            video_aspect=VideoAspect.landscape,
            duration=5,
            model_id="seedance-2",
        )
        print(f"SEEDANCE2_CANARY provider_done model={model}")
        with requests.get(url, stream=True, timeout=(30, 300)) as response:
            response.raise_for_status()
            tmp = OUT.with_suffix(".part")
            with tmp.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fh.write(chunk)
            tmp.replace(OUT)
    except FrontierMediaError as exc:
        print(f"SEEDANCE2_CANARY FAILED provider={type(exc).__name__} detail={str(exc)[:220]}")
        return 2
    except Exception as exc:
        print(f"SEEDANCE2_CANARY FAILED transport={type(exc).__name__}")
        return 3

    if not _valid_mp4(OUT):
        print("SEEDANCE2_CANARY FAILED validation=false")
        return 4

    print(f"SEEDANCE2_CANARY PASS existing=false path={OUT} bytes={OUT.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
