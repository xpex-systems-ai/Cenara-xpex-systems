"""One-shot free-stack first flight: OpenRouter Free -> Hugging Face open video."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import requests

from app.services.frontier_media import FrontierMediaError, generate_huggingface_video_file

OUT = Path("/MoneyPrinterTurbo/storage/canary/hf-openrouter-first-flight.mp4")
META = Path("/MoneyPrinterTurbo/storage/canary/hf-openrouter-first-flight.json")


def _valid_mp4(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 100_000:
        return False
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration,size", "-of", "json", str(path)],
            capture_output=True, text=True, check=True, timeout=30,
        )
        fmt = json.loads(result.stdout or "{}").get("format") or {}
        return float(fmt.get("duration") or 0) > 1 and int(fmt.get("size") or 0) > 100_000
    except Exception:
        return False


def _director_prompt() -> str:
    api_key = str(os.getenv("OPENROUTER_API_KEY", "") or "").strip()
    model = str(os.getenv("OPENROUTER_MODEL", "openrouter/free") or "openrouter/free").strip()
    fallback = (
        "Premium cinematic launch film for XPeX Academy. Futuristic AI learning studio at night, "
        "elegant dark navy architecture, cyan and warm orange accent lighting, glass interfaces, "
        "an adult educator walking through a luminous knowledge environment, subtle volumetric light, "
        "smooth dolly camera, natural human motion, refined commercial art direction, no text, no logos, "
        "no watermark, realistic materials, sophisticated motion, high-end technology brand film."
    )
    if not api_key:
        return fallback

    instruction = (
        "Write ONE concise text-to-video prompt, under 110 words, for a premium 5-second commercial "
        "brand film for XPeX Academy. Style: OpenAI/Canva-level polished technology campaign, realistic "
        "human motion, smooth deliberate camera, dark navy with cyan and warm orange accents. "
        "No on-screen text, no logos, no watermark. Return only the prompt."
    )
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://cenara-xpex-systems-production.up.railway.app",
                "X-Title": "Cenara XPeX",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": instruction}],
                "temperature": 0.6,
                "max_tokens": 180,
            },
            timeout=(20, 120),
        )
        if response.status_code >= 400:
            print(f"HF_OPENROUTER_CANARY director_fallback=true http={response.status_code}")
            return fallback
        body = response.json()
        content = str((((body.get("choices") or [{}])[0].get("message") or {}).get("content")) or "").strip()
        return content[:1200] if content else fallback
    except Exception as exc:
        print(f"HF_OPENROUTER_CANARY director_fallback=true error={type(exc).__name__}")
        return fallback


def main() -> int:
    if os.getenv("CENARA_HF_CANARY_ON_START", "0") != "1":
        print("HF_OPENROUTER_CANARY disabled")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if _valid_mp4(OUT):
        print(f"HF_OPENROUTER_CANARY PASS existing=true path={OUT} bytes={OUT.stat().st_size}")
        return 0

    prompt = _director_prompt()
    model = str(
        os.getenv("CENARA_HF_VIDEO_MODEL", "Lightricks/LTX-Video-0.9.8-13B-distilled")
        or "Lightricks/LTX-Video-0.9.8-13B-distilled"
    ).strip()
    print(f"HF_OPENROUTER_CANARY director_ready=true model={model}")

    try:
        generate_huggingface_video_file(prompt, str(OUT), model=model)
    except FrontierMediaError as exc:
        print(f"HF_OPENROUTER_CANARY FAILED detail={' '.join(str(exc).split())[:420]}")
        return 2
    except Exception as exc:
        print(f"HF_OPENROUTER_CANARY FAILED unexpected={type(exc).__name__}")
        return 3

    if not _valid_mp4(OUT):
        print("HF_OPENROUTER_CANARY FAILED validation=false")
        return 4

    META.write_text(
        json.dumps({"model": model, "prompt": prompt, "bytes": OUT.stat().st_size}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"HF_OPENROUTER_CANARY PASS existing=false path={OUT} bytes={OUT.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
