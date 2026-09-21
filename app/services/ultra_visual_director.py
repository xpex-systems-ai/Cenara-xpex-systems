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
        "scientific-grade optical clarity, extremely clean micro-contrast, controlled highlights, "
        "deep blacks without crushed detail, precise geometry, realistic physical lighting, "
        "high dynamic range, cinematic 35mm composition, subtle volumetric atmosphere, "
        "smooth purposeful camera movement, premium educational documentary aesthetic, "
        "no text, no watermark, no visual gibberish, no deformed faces, no duplicate limbs"
    ),
    cut_seconds=5.0,
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
