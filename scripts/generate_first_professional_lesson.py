from __future__ import annotations

import json
import os
from pathlib import Path

from app.services.academy_lesson import create_academy_lesson

ROOT = Path(os.getenv("CENARA_STORAGE_DIR", "/MoneyPrinterTurbo/storage"))
MARKER = ROOT / "first-professional-lesson-v1.done"

if os.getenv("CENARA_GENERATE_FIRST_PRO_LESSON", "0") != "1":
    print("CENARA_FIRST_PRO_LESSON skip=disabled", flush=True)
    raise SystemExit(0)

if MARKER.exists():
    print("CENARA_FIRST_PRO_LESSON skip=already_done", flush=True)
    raise SystemExit(0)

print("CENARA_FIRST_PRO_LESSON stage=start", flush=True)

output, manifest = create_academy_lesson(
    topic="Fundamentos de Inteligência Artificial — diferença entre IA, Machine Learning e IA Generativa",
    objective="Fazer o aluno entender os três conceitos, reconhecer exemplos práticos e saber quando cada abordagem é usada.",
    minutes=3,
    voice_name="pt-BR-FranciscaNeural-Female",
    voice_rate=1.0,
    avatar_enabled=True,
)

if not output.is_file() or output.stat().st_size < 100_000:
    raise RuntimeError("professional lesson MP4 was not created")

payload = {
    "output": str(output),
    "engine": manifest.get("engine"),
    "quality_profile": manifest.get("quality_profile"),
    "master_format": manifest.get("master_format"),
    "lipsync_mode": manifest.get("lipsync_mode"),
    "audio_duration": manifest.get("audio_duration"),
}
MARKER.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print("CENARA_FIRST_PRO_LESSON PASS " + json.dumps(payload, ensure_ascii=False), flush=True)
