from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class UltraVisualProfile:
    name: str
    prompt_suffix: str
    cut_seconds: float
    prefer_video_model: str


ROMAN_PRECISION = UltraVisualProfile(
    name="roman_precision",
    prompt_suffix=(
        "NASA-grade aerospace documentary cinematography, real clean-room and precision-engineering visual language, "
        "scientific optical clarity, physically accurate materials, crisp fine detail, neutral whites, controlled highlights, "
        "deep blacks with preserved shadow detail, subtle cool-magenta scientific color separation, realistic lens behavior, "
        "wide establishing shots mixed with macro mechanical details, slow dolly and slider movement, restrained depth of field, "
        "high dynamic range, stable exposure, premium broadcast documentary finish, believable people and hands, "
        "no synthetic UI, no neon sci-fi fantasy, no generated text, no watermark, no gibberish, no deformed anatomy"
    ),
    cut_seconds=5.5,
    prefer_video_model="cosmos3",
)


def active_profile() -> UltraVisualProfile:
    mode = str(os.getenv("CENARA_ULTRA_VISUAL_PROFILE", "roman_precision") or "roman_precision").strip().lower()
    return ROMAN_PRECISION


def enhance_visual_prompt(prompt: str, *, subject_lock: str = "") -> str:
    profile = active_profile()
    continuity = ""
    if subject_lock:
        continuity = (
            f" STRICT SUBJECT CONTINUITY: {subject_lock}; preserve identity, wardrobe, proportions, "
            "face, hair, colors and camera-world consistency across shots."
        )
    return (" ".join(str(prompt or "").split()) + ". " + profile.prompt_suffix + continuity)[:3800]
