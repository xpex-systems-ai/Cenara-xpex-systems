from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORAGE = Path(os.getenv("CENARA_STORAGE_DIR", str(ROOT / "storage")))
TASK = STORAGE / "tasks" / "bounty-16601-final-v2"
FINAL = TASK / "xpex-bounty-16601-final-v3.mp4"
VISUAL = TASK / "cenara-structured-storyboard-v3.mp4"
AUDIO = TASK / "voice.mp3"


def valid_mp4(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 10_000:
        return False
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return True
    try:
        p = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        data = json.loads(p.stdout or "{}")
        duration = float((data.get("format") or {}).get("duration") or 0)
        return duration > 1 and any(s.get("codec_type") == "video" for s in data.get("streams", []))
    except Exception:
        return False


def main() -> int:
    if valid_mp4(FINAL):
        print(f"CENARA_BOUNTY_16601_V3_BOOT status=ready path={FINAL} bytes={FINAL.stat().st_size}", flush=True)
        return 0

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("CENARA_BOUNTY_16601_V3_BOOT status=failed reason=ffmpeg_missing", flush=True)
        return 2

    clips = [TASK / f"structured-shot-{i}.mp4" for i in range(1, 6)]
    missing = [str(p) for p in clips if not valid_mp4(p)]
    if missing:
        print("CENARA_BOUNTY_16601_V3_BOOT status=waiting reason=missing_shots missing=" + ",".join(missing), flush=True)
        return 3

    inputs: list[str] = []
    filters: list[str] = []
    labels: list[str] = []
    for i, clip in enumerate(clips):
        inputs += ["-i", str(clip)]
        label = f"v{i}"
        filters.append(
            f"[{i}:v]fps=30,scale=720:1280:force_original_aspect_ratio=increase,"
            f"crop=720:1280,setsar=1,setpts=PTS-STARTPTS[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append("".join(labels) + f"concat=n={len(clips)}:v=1:a=0[vout]")

    try:
        subprocess.run(
            [ffmpeg, "-y", *inputs, "-filter_complex", ";".join(filters), "-map", "[vout]",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
             "-r", "30", "-movflags", "+faststart", str(VISUAL)],
            check=True, capture_output=True, text=True, timeout=360,
        )
    except subprocess.CalledProcessError as exc:
        detail = " ".join((exc.stderr or "").split())[-700:]
        print(f"CENARA_BOUNTY_16601_V3_BOOT status=failed stage=visual detail={detail}", flush=True)
        return 4

    if not valid_mp4(VISUAL):
        print("CENARA_BOUNTY_16601_V3_BOOT status=failed stage=visual_validation", flush=True)
        return 5
    if not AUDIO.is_file() or AUDIO.stat().st_size < 1_000:
        print("CENARA_BOUNTY_16601_V3_BOOT status=waiting reason=voice_missing", flush=True)
        return 6

    try:
        subprocess.run(
            [ffmpeg, "-y", "-i", str(VISUAL), "-i", str(AUDIO),
             "-map", "0:v:0", "-map", "1:a:0",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
             "-c:a", "aac", "-b:a", "192k", "-shortest",
             "-movflags", "+faststart", str(FINAL)],
            check=True, capture_output=True, text=True, timeout=360,
        )
    except subprocess.CalledProcessError as exc:
        detail = " ".join((exc.stderr or "").split())[-700:]
        print(f"CENARA_BOUNTY_16601_V3_BOOT status=failed stage=master detail={detail}", flush=True)
        return 7

    if not valid_mp4(FINAL):
        print("CENARA_BOUNTY_16601_V3_BOOT status=failed stage=final_validation", flush=True)
        return 8

    print(f"CENARA_BOUNTY_16601_V3_BOOT status=ready path={FINAL} bytes={FINAL.stat().st_size}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
