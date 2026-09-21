"""Cenara Frontier Media Hub.

Server-side adapters for frontier video/image generation. Secrets are read only
from environment variables and are never returned to the UI/logs.
"""

from __future__ import annotations

import base64
import math
import os
from pathlib import Path
from typing import Any

import requests
from loguru import logger

from app.models.schema import MaterialInfo, VideoAspect


VIDEO_MODELS: dict[str, dict[str, Any]] = {
    "seedance-2": {
        "provider": "fal",
        "endpoint": "bytedance/seedance-2.0/text-to-video",
        "label": "Seedance 2.0",
        "open_source": False,
        "durations": range(4, 16),
    },
    "seedance-2-fast": {
        "provider": "fal",
        "endpoint": "bytedance/seedance-2.0/fast/text-to-video",
        "label": "Seedance 2.0 Fast",
        "open_source": False,
        "durations": range(4, 16),
    },
    "veo-3.1": {
        "provider": "fal",
        "endpoint": "fal-ai/veo3.1",
        "label": "Veo 3.1",
        "open_source": False,
        "durations": (4, 6, 8),
    },
    "kling-3-pro": {
        "provider": "fal",
        "endpoint": "fal-ai/kling-video/o3/pro/text-to-video",
        "label": "Kling O3 Pro",
        "open_source": False,
        "durations": range(3, 16),
    },
    "wan-2.5": {
        "provider": "fal",
        "endpoint": "fal-ai/wan-25-preview/text-to-video",
        "label": "Wan 2.5",
        "open_source": True,
        "durations": (5, 10),
    },
    "wan-2.2-open": {
        "provider": "fal",
        "endpoint": "fal-ai/wan/v2.2-5b/text-to-video",
        "label": "Wan 2.2 5B",
        "open_source": True,
        "durations": (5,),
    },
}

DEFAULT_VIDEO_MODEL = "seedance-2"
DEFAULT_NANO_BANANA_MODEL = "gemini-3.1-flash-image"


class FrontierMediaError(RuntimeError):
    pass


def _secret(name: str) -> str:
    return str(os.getenv(name, "") or "").strip()


def video_model_id() -> str:
    selected = str(os.getenv("CENARA_FRONTIER_VIDEO_MODEL", DEFAULT_VIDEO_MODEL) or DEFAULT_VIDEO_MODEL).strip()
    return selected if selected in VIDEO_MODELS else DEFAULT_VIDEO_MODEL


def provider_status() -> dict[str, Any]:
    model_id = video_model_id()
    spec = VIDEO_MODELS[model_id]
    return {
        "video_model": model_id,
        "video_label": spec["label"],
        "video_provider": spec["provider"],
        "video_ready": bool(_secret("FAL_KEY")),
        "image_model": str(os.getenv("CENARA_NANO_BANANA_MODEL", DEFAULT_NANO_BANANA_MODEL) or DEFAULT_NANO_BANANA_MODEL),
        "image_ready": bool(_secret("GEMINI_API_KEY") or _secret("GOOGLE_API_KEY")),
    }


def _aspect_value(video_aspect: VideoAspect | str) -> str:
    text = getattr(video_aspect, "value", video_aspect)
    text = str(text or "9:16")
    if "16:9" in text or "landscape" in text:
        return "16:9"
    if "1:1" in text or "square" in text:
        return "1:1"
    return "9:16"


def _duration_for_model(requested: int, model_id: str) -> int:
    durations = list(VIDEO_MODELS[model_id]["durations"])
    requested = max(3, int(requested or 5))
    return min(durations, key=lambda value: abs(int(value) - requested))


def _resolution_for_model(model_id: str) -> str:
    desired = str(os.getenv("CENARA_FRONTIER_RESOLUTION", "1080p") or "1080p").lower()
    if model_id == "wan-2.2-open":
        return "720p"
    if model_id == "wan-2.5" and desired not in {"480p", "1080p"}:
        return "1080p"
    if desired not in {"480p", "720p", "1080p", "4k"}:
        return "1080p"
    return desired


def _cinematic_prompt(prompt: str) -> str:
    base = " ".join(str(prompt or "").split()).strip()
    style = str(
        os.getenv(
            "CENARA_FRONTIER_STYLE",
            "premium cinematic technology film, polished commercial art direction, "
            "natural human motion, physically plausible lighting, smooth intentional camera movement, "
            "high production value, clean composition, no generated text, no watermarks",
        )
        or ""
    ).strip()
    return f"{base}. {style}"[:3500]


def _fal_payload(model_id: str, prompt: str, aspect_ratio: str, duration: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "prompt": _cinematic_prompt(prompt),
        "aspect_ratio": aspect_ratio,
    }
    if model_id in {"seedance-2", "seedance-2-fast"}:
        payload.update(
            duration=str(_duration_for_model(duration, model_id)),
            resolution=_resolution_for_model(model_id),
            generate_audio=True,
            bitrate_mode="high",
            end_user_id=str(os.getenv("CENARA_FAL_END_USER_ID", "xpex-internal")),
        )
    elif model_id == "veo-3.1":
        payload.update(
            duration=f"{_duration_for_model(duration, model_id)}s",
            resolution=_resolution_for_model(model_id),
            generate_audio=True,
            auto_fix=True,
        )
    elif model_id == "kling-3-pro":
        payload.update(
            duration=str(_duration_for_model(duration, model_id)),
            generate_audio=True,
            shot_type="intelligent",
        )
    elif model_id == "wan-2.5":
        payload.update(
            duration=str(_duration_for_model(duration, model_id)),
            resolution=_resolution_for_model(model_id),
        )
    else:
        payload.update(duration=str(_duration_for_model(duration, model_id)))
    return payload


def generate_video_url(
    prompt: str,
    *,
    video_aspect: VideoAspect | str,
    duration: int = 5,
    model_id: str | None = None,
) -> tuple[str, str]:
    api_key = _secret("FAL_KEY")
    if not api_key:
        raise FrontierMediaError("FAL_KEY is not configured")
    selected = model_id or video_model_id()
    if selected not in VIDEO_MODELS:
        raise FrontierMediaError("Unsupported frontier video model")

    spec = VIDEO_MODELS[selected]
    endpoint = spec["endpoint"]
    payload = _fal_payload(selected, prompt, _aspect_value(video_aspect), duration)
    logger.info(f"Cenara Frontier generation started model={selected} endpoint={endpoint}")

    try:
        response = requests.post(
            f"https://fal.run/{endpoint}",
            headers={"Authorization": f"Key {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=(30, 900),
        )
    except requests.RequestException as exc:
        raise FrontierMediaError(f"Frontier video transport failed: {type(exc).__name__}") from exc

    if response.status_code >= 400:
        safe_detail = " ".join((response.text or "").split())[:300]
        raise FrontierMediaError(
            f"Frontier video provider failed HTTP {response.status_code}"
            + (f" detail={safe_detail}" if safe_detail else "")
        )

    try:
        body = response.json()
        video = body.get("video") or {}
        url = str(video.get("url") or body.get("video_url") or "").strip()
    except Exception as exc:
        raise FrontierMediaError("Frontier video provider returned invalid JSON") from exc
    if not url.startswith("https://"):
        raise FrontierMediaError("Frontier video provider returned no downloadable video URL")
    logger.info(f"Cenara Frontier generation completed model={selected}")
    return url, selected


def generate_frontier_materials(
    *,
    search_terms: list[str],
    video_aspect: VideoAspect | str,
    requested_duration: int,
    audio_duration: float = 0.0,
) -> list[MaterialInfo]:
    if not search_terms:
        return []
    clip_duration = max(3, int(requested_duration or 5))
    target_count = max(1, math.ceil(max(float(audio_duration or 0), clip_duration) / clip_duration))
    max_clips = max(1, min(4, int(os.getenv("CENARA_FRONTIER_MAX_CLIPS", "2") or 2)))
    target_count = min(target_count, max_clips)

    results: list[MaterialInfo] = []
    for index in range(target_count):
        term = search_terms[index % len(search_terms)]
        url, model = generate_video_url(
            term,
            video_aspect=video_aspect,
            duration=clip_duration,
        )
        results.append(MaterialInfo(provider=f"frontier:{model}", url=url, duration=clip_duration))
    return results


def generate_nano_banana_image(prompt: str, output_path: str) -> str:
    api_key = _secret("GEMINI_API_KEY") or _secret("GOOGLE_API_KEY")
    if not api_key:
        raise FrontierMediaError("GEMINI_API_KEY is not configured")
    model = str(os.getenv("CENARA_NANO_BANANA_MODEL", DEFAULT_NANO_BANANA_MODEL) or DEFAULT_NANO_BANANA_MODEL)
    try:
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json={"model": model, "input": [{"type": "text", "text": _cinematic_prompt(prompt)}]},
            timeout=(30, 300),
        )
    except requests.RequestException as exc:
        raise FrontierMediaError(f"Nano Banana transport failed: {type(exc).__name__}") from exc
    if response.status_code >= 400:
        raise FrontierMediaError(f"Nano Banana provider failed HTTP {response.status_code}")
    body = response.json()
    encoded = (((body.get("interaction") or body).get("output_image") or {}).get("data") or "")
    if not encoded:
        raise FrontierMediaError("Nano Banana returned no image")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(encoded))
    return str(path)
