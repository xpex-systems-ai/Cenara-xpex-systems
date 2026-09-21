import os

from app.models.schema import VideoAspect
from app.services import frontier_media


def test_frontier_registry_has_flagship_and_open_models():
    assert "seedance-2" in frontier_media.VIDEO_MODELS
    assert "veo-3.1" in frontier_media.VIDEO_MODELS
    assert "kling-3-pro" in frontier_media.VIDEO_MODELS
    assert frontier_media.VIDEO_MODELS["wan-2.2-open"]["open_source"] is True


def test_aspect_mapping():
    assert frontier_media._aspect_value(VideoAspect.landscape) == "16:9"
    assert frontier_media._aspect_value(VideoAspect.portrait) == "9:16"
    assert frontier_media._aspect_value(VideoAspect.square) == "1:1"


def test_seedance_payload_is_premium_and_audio_enabled(monkeypatch):
    monkeypatch.setenv("CENARA_FRONTIER_RESOLUTION", "1080p")
    payload = frontier_media._fal_payload(
        "seedance-2",
        "A premium AI academy introduction",
        "16:9",
        8,
    )
    assert payload["resolution"] == "1080p"
    assert payload["duration"] == "8"
    assert payload["generate_audio"] is True
    assert payload["bitrate_mode"] == "high"
    assert "no generated text" in payload["prompt"]


def test_provider_status_never_exposes_secret(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "super-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "another-secret")
    status = frontier_media.provider_status()
    serialized = repr(status)
    assert status["video_ready"] is True
    assert status["image_ready"] is True
    assert "super-secret" not in serialized
    assert "another-secret" not in serialized
