from __future__ import annotations

import os
from pathlib import Path
import requests
from loguru import logger

AVATAR_ENGINES = (
    ("echomimic_v3", "CENARA_ECHOMIMIC_V3_ENDPOINT"),
    ("liveavatar", "CENARA_LIVEAVATAR_ENDPOINT"),
    ("musetalk_v15", "CENARA_MUSETALK_API_URL"),
    ("liveportrait", "CENARA_LIVEPORTRAIT_ENDPOINT"),
)


def _secret(name: str) -> str:
    return str(os.getenv(name, "") or "").strip()


def configured_avatar_engines() -> list[str]:
    return [name for name, env in AVATAR_ENGINES if _secret(env)]


def render_avatar(face: Path, audio: Path, output: Path) -> tuple[bool, str]:
    token = _secret("CENARA_AVATAR_API_TOKEN") or _secret("CENARA_MUSETALK_API_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    for name, env in AVATAR_ENGINES:
        endpoint = _secret(env).rstrip("/")
        if not endpoint:
            continue
        route = "/lipsync" if name == "musetalk_v15" else "/avatar"
        try:
            with face.open("rb") as ff, audio.open("rb") as af:
                r = requests.post(
                    endpoint + route,
                    headers=headers,
                    files={"face": (face.name, ff, "image/jpeg"), "audio": (audio.name, af, "audio/mpeg")},
                    data={"engine": name},
                    timeout=(30, 1800),
                )
            if r.status_code < 400 and len(r.content) > 100_000:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(r.content)
                return True, name
        except Exception as exc:
            logger.warning(f"avatar engine {name} failed: {type(exc).__name__}")
    return False, "unavailable"
