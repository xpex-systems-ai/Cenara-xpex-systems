from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import requests
from loguru import logger

from app.services import voice


class AcademyLessonError(RuntimeError):
    pass


def _clean(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_drawtext(value: str, limit: int = 84) -> str:
    value = _clean(value)[:limit]
    return (
        value.replace("\\", "")
        .replace("'", "’")
        .replace(":", " -")
        .replace("%", " por cento")
    )


def _openrouter_lesson(topic: str, objective: str, minutes: int) -> dict:
    topic = _clean(topic)
    objective = _clean(objective)
    words = 430 if minutes <= 3 else 570
    fallback_script = (
        f"Bem-vindo à XPeX Academy. Nesta aula vamos estudar {topic}. "
        f"Nosso objetivo é {objective or 'entender o conceito e aplicar na prática'}. "
        "Começando pelo conceito mais amplo: inteligência artificial é o campo que busca construir sistemas capazes de executar tarefas "
        "que normalmente exigiriam alguma forma de inteligência humana, como reconhecer padrões, compreender linguagem, recomendar opções "
        "ou apoiar decisões. Dentro desse campo existe o Machine Learning, ou aprendizado de máquina. Em vez de programarmos cada regra "
        "manualmente, fornecemos dados e exemplos para que o sistema aprenda padrões e use esses padrões em novas situações. "
        "Pense em um filtro de spam. Não precisamos escrever uma regra para cada mensagem possível. O modelo aprende características comuns "
        "de mensagens indesejadas e passa a classificar novas mensagens com base no que aprendeu. "
        "Agora chegamos à IA Generativa. Ela também usa modelos aprendidos a partir de muitos dados, mas seu objetivo principal é produzir "
        "novo conteúdo: texto, imagem, áudio, código ou vídeo. Um assistente que cria um resumo, uma imagem a partir de uma descrição ou um "
        "rascunho de e-mail é um exemplo de IA generativa. "
        "Então guarde esta relação: IA é o campo mais amplo. Machine Learning é uma das principais abordagens dentro desse campo. "
        "IA Generativa é uma categoria de sistemas modernos que usa modelos aprendidos para criar novas saídas. "
        "Na prática, escolha a tecnologia pelo problema, e não pelo nome mais novo. Se você precisa classificar clientes em grupos, um modelo "
        "de Machine Learning pode ser suficiente. Se você precisa escrever uma resposta personalizada, um modelo generativo pode ser mais adequado. "
        "Se a tarefa exige uma decisão crítica, como saúde, finanças ou segurança, aumente a validação e mantenha supervisão humana. "
        "Vamos fazer um exercício rápido. Pense em uma tarefa repetitiva do seu dia. Primeiro, defina qual é a entrada. Depois, diga qual resultado "
        "você espera. Em seguida, pergunte: eu preciso prever uma categoria, reconhecer um padrão ou gerar novo conteúdo? Essa pergunta já ajuda "
        "a separar Machine Learning tradicional de IA Generativa. "
        "Outro ponto importante é que respostas generativas são probabilísticas. Um texto pode parecer convincente e ainda conter uma informação "
        "incorreta. Por isso, valide fatos, fontes e decisões importantes antes de usar a saída em produção. "
        "Para fechar, leve três ideias. Primeiro: inteligência artificial é o guarda-chuva. Segundo: Machine Learning aprende padrões a partir de dados. "
        "Terceiro: IA Generativa produz novo conteúdo com base nesses padrões aprendidos. "
        "Na próxima aula da XPeX Academy vamos aprofundar como modelos de linguagem funcionam e por que eles conseguem gerar respostas tão naturais."
    )
    fallback = {
        "title": topic or "Aula XPeX Academy",
        "script": fallback_script,
        "sections": [
            {"title": "Abertura", "visual": f"premium AI education studio, XPeX Academy inspired, topic {topic}, dark navy, cyan and orange"},
            {"title": "Inteligência Artificial", "visual": "artificial intelligence concept, connected systems, professional education, realistic technology"},
            {"title": "Machine Learning", "visual": "machine learning patterns, data flowing into a model, clean educational visualization, realistic"},
            {"title": "IA Generativa", "visual": "generative AI producing text images audio and code, premium educational visualization"},
            {"title": "Aplicação prática", "visual": f"professional learner applying {topic} in a modern workplace, realistic"},
            {"title": "Resumo", "visual": f"clean futuristic learning environment summarizing {topic}, premium education"},
        ],
    }

    key = _clean(os.getenv("OPENROUTER_API_KEY", ""))
    if not key:
        return fallback

    system = (
        "Você é o diretor pedagógico da XPeX Academy. Responda SOMENTE JSON válido com as chaves "
        "title, script, sections. sections é uma lista de 6 a 8 objetos com title e visual. "
        f"O script deve ter aproximadamente {words} palavras, em português brasileiro, natural, didático, "
        "sem listas faladas longas, sem marketing exagerado e adequado para narração. "
        "Cada visual deve ser um prompt em inglês para uma imagem educacional premium 16:9, sem texto, sem logos, "
        "com continuidade visual dark navy, cyan e orange. A aula precisa ter abertura, explicação, exemplo, prática, "
        "alerta de uso responsável e fechamento."
    )
    user = f"Tema: {topic}\nObjetivo: {objective or 'ensinar o tema de forma prática'}\nDuração alvo: {minutes} minutos."
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://cenara-xpex-systems-production.up.railway.app",
                "X-Title": "Cenara XPeX Academy",
            },
            json={
                "model": os.getenv("OPENROUTER_MODEL", "openrouter/free"),
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": 0.45,
                "max_tokens": 2400,
            },
            timeout=(12, 28),
        )
        if response.status_code >= 400:
            return fallback
        raw = str((((response.json().get("choices") or [{}])[0].get("message") or {}).get("content")) or "").strip()
        raw = re.sub(r"^\\s*```(?:json)?|\\s*```\\s*$", "", raw, flags=re.I | re.M).strip()
        data = json.loads(raw)
        script = _clean(data.get("script", ""))
        sections = data.get("sections") or []
        if len(script) < 500 or not isinstance(sections, list) or len(sections) < 4:
            return fallback
        return {
            "title": _clean(data.get("title")) or fallback["title"],
            "script": script,
            "sections": [
                {"title": _clean(x.get("title")) or f"Parte {idx+1}", "visual": _clean(x.get("visual"))}
                for idx, x in enumerate(sections[:8]) if isinstance(x, dict)
            ],
        }
    except Exception as exc:
        logger.warning(f"academy director fallback: {type(exc).__name__}")
        return fallback


def _pollinations_image(prompt: str, target: Path, width: int, height: int, seed: int) -> bool:
    cleaned = _clean(prompt)
    if not cleaned:
        return False
    try:
        r = requests.get(
            "https://image.pollinations.ai/prompt/" + quote(cleaned[:1400], safe=""),
            params={"width": width, "height": height, "seed": seed, "nologo": "true", "enhance": "true", "model": "flux"},
            timeout=(20, 180),
        )
        if r.status_code >= 400 or "image" not in str(r.headers.get("content-type", "")).lower() or len(r.content) < 20_000:
            return False
        target.write_bytes(r.content)
        return target.is_file() and target.stat().st_size > 20_000
    except Exception:
        return False


def _audio_duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0.0
    try:
        p = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, check=True, timeout=30,
        )
        return float((json.loads(p.stdout).get("format") or {}).get("duration") or 0)
    except Exception:
        return 0.0


def _make_srt(script: str, duration: float, target: Path) -> None:
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\\s+", script) if x.strip()]
    if not sentences:
        sentences = [script]
    weights = [max(1, len(s.split())) for s in sentences]
    total = max(1, sum(weights))

    def ts(value: float) -> str:
        value = max(0.0, value)
        ms = int(round((value - int(value)) * 1000))
        sec = int(value)
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    cursor = 0.0
    rows = []
    for idx, (sentence, weight) in enumerate(zip(sentences, weights), 1):
        seg = duration * weight / total
        end = min(duration, cursor + seg)
        rows.append(f"{idx}\n{ts(cursor)} --> {ts(end)}\n{sentence}\n")
        cursor = end
    target.write_text("\n".join(rows), encoding="utf-8")


def _synthesize(script: str, task_dir: Path, voice_name: str, rate: float) -> tuple[Path, float]:
    audio = task_dir / "lesson-voice.mp3"
    maker = voice.tts(
        text=script,
        voice_name=voice.parse_voice_name(voice_name),
        voice_rate=rate,
        voice_file=str(audio),
        voice_volume=1.0,
    )
    if maker is None or not audio.is_file() or audio.stat().st_size < 4_000:
        raise AcademyLessonError("Falha ao gerar narração Edge TTS")
    duration = _audio_duration(audio)
    if duration <= 5:
        raise AcademyLessonError("Narração gerada com duração inválida")
    return audio, duration


def _render_visual_clip(image: Path, output: Path, seconds: float, width: int, height: int, idx: int) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AcademyLessonError("FFmpeg ausente")
    frames = max(60, int(seconds * 30))
    if idx % 3 == 0:
        zp = f"zoompan=z='min(zoom+0.0011,1.12)':x='iw/2-(iw/zoom/2)+on*0.45':y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps=30"
    elif idx % 3 == 1:
        zp = f"zoompan=z='min(zoom+0.0010,1.10)':x='iw/2-(iw/zoom/2)-on*0.38':y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps=30"
    else:
        zp = f"zoompan=z='min(zoom+0.0012,1.11)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)-on*0.22':d={frames}:s={width}x{height}:fps=30"
    vf = (
        f"crop=iw:ih-28:0:0,"
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"{zp},"
        "eq=contrast=1.03:saturation=1.04,format=yuv420p"
    )
    subprocess.run(
        [ffmpeg, "-y", "-loop", "1", "-i", str(image), "-vf", vf, "-t", f"{seconds:.3f}",
         "-r", "30", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
         "-movflags", "+faststart", str(output)],
        check=True, capture_output=True, text=True, timeout=max(180, int(seconds * 5)),
    )


def _fallback_slide(task_dir: Path, title: str, seconds: float, width: int, height: int, idx: int) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    out = task_dir / f"slide-fallback-{idx:02d}.mp4"
    safe = _safe_drawtext(title, 60)
    vf = (
        f"color=c=0x07111f:s={width}x{height}:r=30:d={seconds},"
        f"drawbox=x='mod(t*90,{width+320})-320':y='h*0.14':w=320:h=120:color=0x0ea5e9@0.18:t=fill,"
        f"drawbox=x='{width}-mod(t*70,{width+280})':y='h*0.68':w=280:h=110:color=0xff7a00@0.15:t=fill,"
        f"drawtext=text='XPeX Academy':fontcolor=0x21d4f4:fontsize={max(26,int(width*0.027))}:x=w*0.07:y=h*0.16,"
        f"drawtext=text='{safe}':fontcolor=white:fontsize={max(34,int(width*0.045))}:x=w*0.07:y=h*0.42,"
        "format=yuv420p"
    )
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", vf, "-t", f"{seconds:.3f}", "-r", "30", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-movflags", "+faststart", str(out)],
        check=True, capture_output=True, text=True, timeout=max(120, int(seconds * 4)),
    )
    return out


def create_academy_lesson(
    topic: str,
    objective: str = "",
    minutes: int = 3,
    voice_name: str = "pt-BR-FranciscaNeural-Female",
    voice_rate: float = 1.0,
    avatar_enabled: bool = True,
) -> tuple[Path, dict]:
    topic = _clean(topic)
    if not topic:
        raise AcademyLessonError("Informe o tema da aula")
    minutes = 4 if int(minutes or 3) >= 4 else 3
    task_id = f"academy-{int(time.time())}-{uuid4().hex[:8]}"
    task_dir = Path(os.getenv("CENARA_STORAGE_DIR", "/MoneyPrinterTurbo/storage")) / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    lesson = _openrouter_lesson(topic, objective, minutes)
    audio, audio_duration = _synthesize(lesson["script"], task_dir, voice_name, voice_rate)
    sections = lesson["sections"] or [{"title": "Aula", "visual": topic}]
    section_seconds = max(10.0, audio_duration / len(sections))
    width, height = 1280, 720

    avatar = task_dir / "academy-avatar.jpg"
    if avatar_enabled:
        avatar_prompt = (
            "professional Brazilian AI instructor, friendly adult educator, chest-up portrait, dark navy smart casual outfit, "
            "modern futuristic education studio, cyan and warm orange rim light, clean background, realistic photography, "
            "consistent presenter identity, no text, no logo"
        )
        _pollinations_image(avatar_prompt, avatar, 640, 640, 1447)

    clips = []
    base_seed = 7301
    for idx, section in enumerate(sections):
        visual = task_dir / f"visual-{idx+1:02d}.jpg"
        prompt = (
            (section.get("visual") or topic)
            + ". XPeX Academy educational film, dark navy, cyan and orange accents, professional, realistic, 16:9, no text, no logo."
        )
        ok = _pollinations_image(prompt, visual, 1024, 576, base_seed + idx)
        clip = task_dir / f"visual-{idx+1:02d}.mp4"
        if ok:
            try:
                _render_visual_clip(visual, clip, section_seconds, width, height, idx)
            except Exception:
                clip = _fallback_slide(task_dir, section.get("title") or f"Parte {idx+1}", section_seconds, width, height, idx)
        else:
            clip = _fallback_slide(task_dir, section.get("title") or f"Parte {idx+1}", section_seconds, width, height, idx)
        clips.append(clip)

    ffmpeg = shutil.which("ffmpeg")
    listing = task_dir / "lesson-clips.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in clips), encoding="utf-8")
    visuals = task_dir / "lesson-visuals.mp4"
    subprocess.run(
        [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-t", f"{audio_duration:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
         "-r", "30", "-movflags", "+faststart", str(visuals)],
        check=True, capture_output=True, text=True, timeout=max(300, int(audio_duration * 3)),
    )

    srt = task_dir / "lesson.srt"
    _make_srt(lesson["script"], audio_duration, srt)
    final = task_dir / "xpex-academy-lesson.mp4"

    if avatar_enabled and avatar.is_file() and avatar.stat().st_size > 20_000:
        filter_complex = (
            "[0:v]scale=1280:720[base];"
            "[2:v]crop=iw:ih-28:0:0,scale=235:235,format=rgba,"
            "fade=t=in:st=0:d=0.5:alpha=1[av];"
            "[base][av]overlay=x=W-w-38:y='H-h-34+8*sin(2*PI*t/4)':shortest=1[v]"
        )
        cmd = [
            ffmpeg, "-y", "-i", str(visuals), "-i", str(audio), "-loop", "1", "-i", str(avatar),
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "1:a:0", "-t", f"{audio_duration:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(final),
        ]
    else:
        cmd = [
            ffmpeg, "-y", "-i", str(visuals), "-i", str(audio),
            "-map", "0:v:0", "-map", "1:a:0", "-t", f"{audio_duration:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(final),
        ]
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=max(420, int(audio_duration * 4)))

    if not final.is_file() or final.stat().st_size < 100_000:
        raise AcademyLessonError("MP4 final não foi criado")

    manifest = {
        "task_id": task_id,
        "title": lesson["title"],
        "topic": topic,
        "objective": objective,
        "script": lesson["script"],
        "sections": sections,
        "voice": voice_name,
        "audio_duration": round(audio_duration, 2),
        "avatar_enabled": bool(avatar_enabled and avatar.is_file()),
        "output": str(final),
        "engine": "xpex_academy_lesson_v1",
    }
    (task_dir / "lesson-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return final, manifest
