from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "media_vault" / "drive_manifest.json"
INDEX_PATH = ROOT / "storage" / "media_vault" / "index.json"

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

def registered_sources() -> list[dict[str, Any]]:
    return list(load_manifest().get("items", []))

def search_vault(query: str = "", limit: int = 30) -> list[dict[str, Any]]:
    q = (query or "").strip().lower()
    out = []
    for item in load_index().get("items", []):
        hay = json.dumps(item, ensure_ascii=False).lower()
        if q and q not in hay:
            continue
        out.append(item)
        if len(out) >= limit:
            break
    return out
