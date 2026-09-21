"""Generate the first official XPeX Academy lesson exactly once."""

from __future__ import annotations

import os
from pathlib import Path

from app.services.academy_lesson import AcademyLessonError, create_academy_lesson

ROOT = Path(os.getenv("CENARA_STORAGE_DIR", "/MoneyPrinterTurbo/storage"))
MARKER = ROOT / "academy-first-lesson.done"


def main() -> int:
    if os.getenv("CENARA_ACADEMY_FIRST_LESSON_ON_START", "0") != "1":
        print("CENARA_ACADEMY_FIRST_LESSON disabled")
        return 0
    if MARKER.exists():
        print(f"CENARA_ACADEMY_FIRST_LESSON PASS existing=true marker={MARKER}")
        return 0

    print("CENARA_ACADEMY_FIRST_LESSON stage=start")
    try:
        output, manifest = create_academy_lesson(
            topic="Fundamentos de Inteligência Artificial — diferença entre IA, Machine Learning e IA Generativa",
            objective="Fazer o aluno entender os três conceitos, reconhecer exemplos práticos e saber quando cada abordagem é usada.",
            minutes=3,
            voice_name="pt-BR-FranciscaNeural-Female",
            voice_rate=1.0,
            avatar_enabled=True,
        )
    except AcademyLessonError as exc:
        print(f"CENARA_ACADEMY_FIRST_LESSON FAILED detail={str(exc)[:320]}")
        return 2
    except Exception as exc:
        print(f"CENARA_ACADEMY_FIRST_LESSON FAILED unexpected={type(exc).__name__} detail={str(exc)[:260]}")
        return 3

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(str(output), encoding="utf-8")
    print(
        "CENARA_ACADEMY_FIRST_LESSON PASS "
        f"path={output} bytes={output.stat().st_size} duration={manifest.get('audio_duration')} "
        f"engine={manifest.get('engine')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
