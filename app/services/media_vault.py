from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[2]
STORAGE = ROOT / "storage"
VAULT_DIR = STORAGE / "media_vault"
VAULT_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST_PATH = ROOT / "media_vault" / "drive_manifest.json"
INDEX_PATH = VAULT_DIR / "index.json"

DRIVE_URL_RE = re.compile(r"https://drive\.google\.com/file/d/([^/]+)/view")

def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        return {"items": []}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

def load_index() -> dict[str, Any]:
    if not INDEX_PATH.is_file():
        return {"items": []}
    try:
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"items": []}

def save_index(data: dict[str, Any]) -> None:
    INDEX_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _candidate_urls(file_id: str) -> list[str]:
    return [
        f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t",
        f"https://drive.google.com/uc?export=download&id={file_id}",
    ]

def _looks_like_video(path: Path) -> bool:
    ffprobe = os.getenv("FFPROBE_BIN") or "ffprobe"
    try:
        p = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "stream=codec_type,width,height,duration:format=duration",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=20, check=True,
        )
        body = json.loads(p.stdout or "{}")
        return any(s.get("codec_type") == "video" for s in body.get("streams", []))
    except Exception:
        return path.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm", ".m4v"}

def _probe(path: Path) -> dict[str, Any]:
    ffprobe = os.getenv("FFPROBE_BIN") or "ffprobe"
    try:
        p = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "stream=index,codec_name,codec_type,width,height,r_frame_rate,duration:format=duration,size,bit_rate",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return json.loads(p.stdout or "{}")
    except Exception:
        return {}

def download_drive_video(file_id: str, target: Path, timeout: int = 180) -> tuple[bool, str]:
    target.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0 XPEX-Cenara-MediaVault/1.0"}
    last = "not_attempted"
    for url in _candidate_urls(file_id):
        try:
            with requests.get(url, headers=headers, stream=True, timeout=(20, timeout), allow_redirects=True) as r:
                ctype = (r.headers.get("content-type") or "").lower()
                if r.status_code >= 400:
                    last = f"http_{r.status_code}"
                    continue
                if "text/html" in ctype:
                    last = "drive_requires_public_file_or_confirmation"
                    continue
                tmp = target.with_suffix(target.suffix + ".part")
                total = 0
                with tmp.open("wb") as f:
                    for chunk in r.iter_content(1024 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > 1_500_000_000:
                            raise RuntimeError("file_too_large")
                        f.write(chunk)
                if total < 10_000:
                    tmp.unlink(missing_ok=True)
                    last = "payload_too_small"
                    continue
                tmp.replace(target)
                return True, ctype
        except Exception as exc:
            last = type(exc).__name__
    return False, last

def ingest_manifest(limit: int | None = None) -> dict[str, Any]:
    manifest = load_manifest()
    existing = load_index()
    known = {str(x.get("drive_file_id")): x for x in existing.get("items", [])}
    result_items = []
    counts = {"registered": 0, "downloaded": 0, "blocked": 0, "invalid": 0}
    items = manifest.get("items", [])
    if limit:
        items = items[: max(0, int(limit))]
    for pos, item in enumerate(items, start=1):
        file_id = str(item.get("drive_file_id") or "").strip()
        if not file_id:
            continue
        row = dict(known.get(file_id) or item)
        row.setdefault("rights", "review_required")
        if row.get("local_path") and Path(row["local_path"]).is_file():
            row["status"] = "downloaded"
            counts["downloaded"] += 1
            result_items.append(row)
            continue
        target = VAULT_DIR / f"drive-{pos:03d}-{file_id}.mp4"
        ok, detail = download_drive_video(file_id, target)
        if ok and _looks_like_video(target):
            row.update(status="downloaded", local_path=str(target), probe=_probe(target), source="google_drive")
            counts["downloaded"] += 1
        elif ok:
            target.unlink(missing_ok=True)
            row.update(status="invalid_media", detail=detail)
            counts["invalid"] += 1
        else:
            row.update(status="blocked", detail=detail)
            counts["blocked"] += 1
        counts["registered"] += 1
        result_items.append(row)
    data = {"version": "1.0", "counts": counts, "items": result_items}
    save_index(data)
    return data

def search_vault(query: str = "", orientation: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
    q = (query or "").lower().strip()
    out = []
    for item in load_index().get("items", []):
        if item.get("status") != "downloaded":
            continue
        probe = item.get("probe") or {}
        video = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {})
        w, h = int(video.get("width") or 0), int(video.get("height") or 0)
        item_orientation = "vertical" if h > w else ("square" if h == w and w else "horizontal")
        if orientation and orientation != item_orientation:
            continue
        hay = json.dumps(item, ensure_ascii=False).lower()
        if q and q not in hay:
            continue
        enriched = dict(item)
        enriched["orientation"] = item_orientation
        out.append(enriched)
        if len(out) >= limit:
            break
    return out
