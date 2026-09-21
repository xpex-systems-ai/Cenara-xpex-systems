"""One-shot production proof for Cenara's zero-cost visual video path."""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

import requests

OUTDIR = Path("/MoneyPrinterTurbo/storage/canary/free-video")
OUTDIR.mkdir(parents=True, exist_ok=True)
OUT = OUTDIR / "cenara-free-canary.mp4"


def valid(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 50_000:
        return False
    try:
        r = subprocess.run(
            ["ffprobe","-v","error","-show_entries","format=duration","-of","json",str(path)],
            capture_output=True,text=True,check=True,timeout=20,
        )
        return float((json.loads(r.stdout).get("format") or {}).get("duration") or 0) > 1
    except Exception:
        return False


def image(prompt: str, target: Path, seed: int) -> bool:
    try:
        r = requests.get(
            "https://image.pollinations.ai/prompt/" + quote(prompt, safe=""),
            params={"width":1024,"height":576,"seed":seed,"nologo":"true","enhance":"true","model":"flux"},
            timeout=(20,150),
        )
        if r.status_code >= 400 or "image" not in str(r.headers.get("content-type","")).lower() or len(r.content) < 20_000:
            return False
        target.write_bytes(r.content)
        return True
    except Exception:
        return False


def main() -> int:
    if os.getenv("CENARA_FREE_VIDEO_CANARY_ON_START","0") != "1":
        print("CENARA_FREE_VIDEO_CANARY disabled")
        return 0
    if valid(OUT):
        print(f"CENARA_FREE_VIDEO_CANARY PASS existing=true bytes={OUT.stat().st_size}")
        return 0
    prompt = (
        "premium cinematic AI education studio, futuristic learning environment, "
        "dark navy architecture, cyan and warm orange lighting, realistic adult presenter, "
        "smooth commercial composition, no text, no logo, no watermark"
    )
    imgs=[]
    seed=int(time.time())%100000
    for i,suffix in enumerate(["wide establishing shot","medium hero shot","close-up premium campaign frame"]):
        p=OUTDIR/f"shot-{i+1}.jpg"
        if image(prompt+", "+suffix,p,seed+i*19):
            imgs.append(p)
    if not imgs:
        print("CENARA_FREE_VIDEO_CANARY FAILED stage=images")
        return 2
    ffmpeg="ffmpeg"
    clips=[]
    for i,p in enumerate(imgs):
        clip=OUTDIR/f"clip-{i+1}.mp4"
        try:
            subprocess.run([
                ffmpeg,"-y","-loop","1","-i",str(p),
                "-vf","scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,zoompan=z='min(zoom+0.0012,1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=60:s=1280x720:fps=30,format=yuv420p",
                "-t","2","-r","30","-an","-c:v","libx264","-preset","veryfast","-movflags","+faststart",str(clip)
            ],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=120)
            if valid(clip): clips.append(clip)
        except Exception:
            pass
    if not clips:
        print("CENARA_FREE_VIDEO_CANARY FAILED stage=clips")
        return 3
    listing=OUTDIR/"concat.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in clips),encoding="utf-8")
    try:
        subprocess.run([ffmpeg,"-y","-f","concat","-safe","0","-i",str(listing),"-c:v","libx264","-pix_fmt","yuv420p","-movflags","+faststart",str(OUT)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=180)
    except Exception:
        print("CENARA_FREE_VIDEO_CANARY FAILED stage=concat")
        return 4
    if not valid(OUT):
        print("CENARA_FREE_VIDEO_CANARY FAILED stage=validation")
        return 5
    print(f"CENARA_FREE_VIDEO_CANARY PASS existing=false bytes={OUT.stat().st_size} path={OUT}")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
