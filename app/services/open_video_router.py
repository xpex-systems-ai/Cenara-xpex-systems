"""Cenara Open Video Router.

One simple interface over several open video model families. The models may be
served by Hugging Face Inference, a public/free demo endpoint, or any compatible
HTTP worker. Cenara itself stays CPU-light.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from loguru import logger


OPEN_VIDEO_MODELS: dict[str, dict[str, Any]] = {
    "wan22": {
        "label": "Wan 2.2",
        "hf_model": "Wan-AI/Wan2.2-T2V-A14B",
        "endpoint_env": "CENARA_WAN22_ENDPOINT",
    },
    "ltx2": {
        "label": "LTX-2",
        "hf_model": "Lightricks/LTX-2",
        "endpoint_env": "CENARA_LTX2_ENDPOINT",
    },
    "mochi1": {
        "label": "Mochi 1",
        "hf_model": "genmo/mochi-1-preview",
        "endpoint_env": "CENARA_MOCHI1_ENDPOINT",
    },
    "skyreels": {
        "label": "SkyReels",
        "hf_model": "Skywork/SkyReels-V2",
        "endpoint_env": "CENARA_SKYREELS_ENDPOINT",
    },
    "hunyuan": {
        "label": "HunyuanVideo",
        "hf_model": "tencent/HunyuanVideo",
        "endpoint_env": "CENARA_HUNYUAN_ENDPOINT",
    },
}


class OpenVideoRouterError(RuntimeError):
    pass


def _secret(name: str) -> str:
    return str(os.getenv(name, "") or "").strip()


def _write_payload(payload: bytes, output: Path) -> Path:
    if not isinstance(payload, (bytes, bytearray)) or len(payload) < 100_000:
        raise OpenVideoRouterError("video payload invalid or empty")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(bytes(payload))
    return output


def _download(url: str, output: Path) -> Path:
    if not str(url).startswith("http"):
        raise OpenVideoRouterError("provider returned no downloadable URL")
    r = requests.get(url, timeout=(20, 900))
    if r.status_code >= 400:
        raise OpenVideoRouterError(f"download failed HTTP {r.status_code}")
    return _write_payload(r.content, output)


def _call_generic_endpoint(endpoint: str, prompt: str, output: Path, duration: int, aspect: str) -> Path:
    token = _secret("CENARA_OPEN_VIDEO_API_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    payload = {"prompt": prompt, "duration": int(duration), "aspect_ratio": aspect}
    r = requests.post(endpoint, json=payload, headers=headers, timeout=(30, 1200))
    if r.status_code >= 400:
        raise OpenVideoRouterError(f"endpoint failed HTTP {r.status_code}")
    ctype = str(r.headers.get("content-type", "")).lower()
    if "video" in ctype:
        return _write_payload(r.content, output)
    try:
        body = r.json()
    except Exception as exc:
        raise OpenVideoRouterError("endpoint returned neither video nor JSON") from exc
    url = str(body.get("video_url") or body.get("url") or ((body.get("video") or {}).get("url")) or "")
    return _download(url, output)


def _call_huggingface(model: str, prompt: str, output: Path) -> Path:
    token = _secret("HF_TOKEN")
    if not token:
        raise OpenVideoRouterError("HF_TOKEN not configured")
    try:
        from huggingface_hub import InferenceClient
    except Exception as exc:
        raise OpenVideoRouterError("huggingface_hub not installed") from exc
    provider = _secret("CENARA_HF_VIDEO_PROVIDER") or "auto"
    client = InferenceClient(provider=provider, api_key=token, timeout=1200)
    try:
        data = client.text_to_video(
            prompt,
            model=model,
            num_frames=int(_secret("CENARA_HF_VIDEO_FRAMES") or 81),
            num_inference_steps=int(_secret("CENARA_HF_VIDEO_STEPS") or 20),
        )
    except Exception as exc:
        raise OpenVideoRouterError("Hugging Face unavailable: " + " ".join(str(exc).split())[:240]) from exc
    return _write_payload(data, output)


def configured_models() -> list[str]:
    names = []
    for model_id, spec in OPEN_VIDEO_MODELS.items():
        if _secret(spec["endpoint_env"]):
            names.append(model_id)
    if _secret("HF_TOKEN"):
        for model_id in OPEN_VIDEO_MODELS:
            if model_id not in names:
                names.append(model_id)
    return names


def generate_open_video(
    prompt: str,
    output_path: str | Path,
    *,
    duration: int = 5,
    aspect: str = "16:9",
    preferred: str | None = None,
) -> tuple[Path, str]:
    """Try open video model families in priority order and return first valid MP4."""
    output = Path(output_path)
    preferred = str(preferred or _secret("CENARA_OPEN_VIDEO_MODEL") or "wan22").strip().lower()
    order = [preferred] + [m for m in ("wan22", "ltx2", "mochi1", "skyreels", "hunyuan") if m != preferred]
    errors = []

    for model_id in order:
        spec = OPEN_VIDEO_MODELS.get(model_id)
        if not spec:
            continue
        endpoint = _secret(spec["endpoint_env"])
        try:
            if endpoint:
                logger.info(f"OpenVideoRouter model={model_id} mode=endpoint")
                return _call_generic_endpoint(endpoint, prompt, output, duration, aspect), model_id
            if _secret("HF_TOKEN"):
                logger.info(f"OpenVideoRouter model={model_id} mode=huggingface")
                return _call_huggingface(spec["hf_model"], prompt, output), model_id
        except Exception as exc:
            errors.append(f"{model_id}:{type(exc).__name__}")
            logger.warning(f"OpenVideoRouter {model_id} failed: {' '.join(str(exc).split())[:180]}")

    raise OpenVideoRouterError("no open video backend available; " + ",".join(errors[-5:]))
