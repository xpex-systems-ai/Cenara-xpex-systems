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
from PIL import Image, ImageDraw, ImageFont


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
        "title, script, sections. sections é uma lista de 6 a 8 objetos com type, title e visual. "
        f"O script deve ter aproximadamente {words} palavras, em português brasileiro, natural, didático, "
        "sem listas faladas longas, sem marketing exagerado e adequado para narração. "
        "type deve alternar entre talking_head e support_visual, começando e terminando com talking_head. "
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
                {"type": _clean(x.get("type")) or ("talking_head" if idx in (0, len(sections)-1) or idx % 2 == 0 else "support_visual"), "title": _clean(x.get("title")) or f"Parte {idx+1}", "visual": _clean(x.get("visual"))}
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




def _split_script_for_sections(script: str, count: int) -> list[str]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script or "") if s.strip()]
    if not sentences:
        return [script or ""] * max(1, count)
    buckets = [[] for _ in range(max(1, count))]
    weights = [0] * len(buckets)
    for sentence in sentences:
        idx = min(range(len(buckets)), key=lambda i: weights[i])
        buckets[idx].append(sentence)
        weights[idx] += max(1, len(sentence.split()))
    return [" ".join(bucket).strip() for bucket in buckets]


def _normalize_timeline(sections: list[dict], script: str) -> list[dict]:
    if not sections:
        sections = [{"type": "talking_head", "title": "Aula", "visual": ""}]
    parts = _split_script_for_sections(script, len(sections))
    timeline = []
    for idx, section in enumerate(sections):
        kind = _clean(section.get("type")).lower()
        if kind not in {"talking_head", "support_visual"}:
            kind = "talking_head" if idx in (0, len(sections)-1) or idx % 2 == 0 else "support_visual"
        if idx == 0 or idx == len(sections) - 1:
            kind = "talking_head"
        timeline.append({
            "type": kind,
            "title": _clean(section.get("title")) or f"Parte {idx+1}",
            "visual": _clean(section.get("visual")),
            "script": parts[idx] if idx < len(parts) else "",
        })
    return timeline


def _render_presenter_motion(avatar: Path, audio: Path, output: Path, seconds: float, title: str) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AcademyLessonError("FFmpeg ausente")
    safe = _safe_drawtext(title, 58)
    frames = max(90, int(seconds * 30))
    # Preserve the full face/head and place instructor on the right instead of destructive crop/zoom.
    vf = (
        "scale=520:520:force_original_aspect_ratio=decrease,"
        "pad=1280:720:(ow-iw)-70:(oh-ih)/2:color=0x06101c,"
        "drawbox=x=0:y=0:w=650:h=720:color=0x081b2c@1:t=fill,"
        "drawbox=x=58:y=80:w=530:h=500:color=0x0b2c41@1:t=fill,"
        "drawtext=text='XPeX ACADEMY':fontcolor=0x21d4f4:fontsize=30:x=86:y=112,"
        f"drawtext=text='{safe}':fontcolor=white:fontsize=42:x=86:y=180,"
        "drawtext=text='Aula oficial':fontcolor=0xff7a00:fontsize=28:x=86:y=520,"
        f"zoompan=z='1.0+0.01*sin(on/20)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1280x720:fps=30,"
        "format=yuv420p"
    )
    subprocess.run(
        [ffmpeg, "-y", "-loop", "1", "-i", str(avatar), "-i", str(audio),
         "-vf", vf, "-t", f"{seconds:.3f}", "-r", "30",
         "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(output)],
        check=True, capture_output=True, text=True, timeout=max(240, int(seconds * 5)),
    )

def _try_wav2lip(avatar: Path, audio: Path, output: Path) -> bool:
    wav2lip_dir = Path(os.getenv("CENARA_WAV2LIP_DIR", "").strip())
    checkpoint = Path(os.getenv("CENARA_WAV2LIP_CHECKPOINT", "").strip())
    python_bin = os.getenv("CENARA_WAV2LIP_PYTHON", "python").strip() or "python"
    if not wav2lip_dir.is_dir() or not checkpoint.is_file():
        return False
    inference = wav2lip_dir / "inference.py"
    if not inference.is_file():
        return False
    try:
        subprocess.run(
            [python_bin, str(inference), "--checkpoint_path", str(checkpoint),
             "--face", str(avatar), "--audio", str(audio), "--outfile", str(output)],
            cwd=str(wav2lip_dir), check=True, capture_output=True, text=True, timeout=900,
        )
        return output.is_file() and output.stat().st_size > 100_000
    except Exception as exc:
        logger.warning(f"Wav2Lip unavailable, presenter fallback used: {type(exc).__name__}")
        return False


def _render_talking_head_scene(task_dir: Path, avatar: Path, audio: Path, seconds: float, title: str, idx: int) -> tuple[Path, str]:
    out = task_dir / f"scene-{idx+1:02d}-talking.mp4"
    if _try_wav2lip(avatar, audio, out):
        return out, "wav2lip"
    _render_presenter_motion(avatar, audio, out, seconds, title)
    return out, "presenter_motion"



def _font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    words = (text or "").split()
    lines, line = [], ""
    for word in words:
        trial = (line + " " + word).strip()
        box = draw.textbbox((0, 0), trial, font=font)
        if box[2] - box[0] <= max_width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines[:5]


def _branded_slide(task_dir: Path, title: str, body: str, idx: int) -> Path:
    out = task_dir / f"branded-support-{idx+1:02d}.png"
    img = Image.new("RGB", (1280, 720), (5, 16, 28))
    d = ImageDraw.Draw(img)

    # premium XPeX frame
    d.rounded_rectangle((42, 36, 1238, 684), radius=34, fill=(8, 27, 44), outline=(26, 91, 122), width=2)
    d.rounded_rectangle((72, 66, 1208, 142), radius=22, fill=(8, 44, 65))
    d.text((96, 88), "XPeX ACADEMY", font=_font(26, True), fill=(31, 212, 244))
    d.text((96, 176), title, font=_font(46, True), fill="white")

    # visual concept cards, deterministic and readable
    concepts = []
    low = title.lower()
    if "machine" in low:
        concepts = [("DADOS", "exemplos"), ("MODELO", "aprende padrões"), ("PREVISÃO", "aplica")]
    elif "generativa" in low:
        concepts = [("PROMPT", "instrução"), ("MODELO", "gera"), ("CONTEÚDO", "texto • imagem • áudio")]
    elif "artificial" in low:
        concepts = [("IA", "campo amplo"), ("ML", "aprende padrões"), ("GEN AI", "cria conteúdo")]
    elif "aplicação" in low or "prática" in low:
        concepts = [("ENTRADA", "problema"), ("PROCESSO", "IA adequada"), ("SAÍDA", "resultado validado")]
    else:
        concepts = [("CONCEITO", "entender"), ("EXEMPLO", "visualizar"), ("PRÁTICA", "aplicar")]

    x0, y0, card_w, gap = 92, 290, 330, 36
    for n, (head, sub) in enumerate(concepts[:3]):
        x = x0 + n * (card_w + gap)
        d.rounded_rectangle((x, y0, x+card_w, y0+190), radius=24, fill=(11, 40, 60), outline=(29, 115, 148), width=2)
        d.ellipse((x+24, y0+24, x+78, y0+78), fill=(255, 122, 0))
        d.text((x+96, y0+28), head, font=_font(27, True), fill="white")
        for li, line in enumerate(_wrap(d, sub, _font(25), card_w-48)):
            d.text((x+28, y0+104+li*34), line, font=_font(25), fill=(195, 218, 232))
        if n < 2:
            d.text((x+card_w+8, y0+72), "→", font=_font(44, True), fill=(31, 212, 244))

    # concise teaching line at bottom
    summary = (body or "").strip().split(".")[0][:140]
    if summary:
        d.rounded_rectangle((92, 522, 1188, 635), radius=18, fill=(6, 22, 36))
        for li, line in enumerate(_wrap(d, summary, _font(26), 1030)):
            d.text((120, 548+li*34), line, font=_font(26), fill=(220, 232, 240))

    img.save(out, quality=95)
    return out


def _render_support_scene(task_dir: Path, image: Path | None, avatar: Path | None, audio: Path, seconds: float, title: str, idx: int) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AcademyLessonError("FFmpeg ausente")
    base = task_dir / f"scene-{idx+1:02d}-support-base.mp4"
    if image and image.is_file():
        _render_visual_clip(image, base, seconds, 1280, 720, idx)
    else:
        base = _fallback_slide(task_dir, title, seconds, 1280, 720, idx)

    out = task_dir / f"scene-{idx+1:02d}-support.mp4"
    safe = _safe_drawtext(title, 58)
    if avatar and avatar.is_file():
        fc = (
            "[0:v]scale=1280:720[base];"
            "[2:v]crop=iw:ih-28:0:0,scale=210:210,format=rgba[av];"
            "[base][av]overlay=x=W-w-32:y=H-h-30:shortest=1[tmp];"
            f"[tmp]drawbox=x=0:y=0:w=iw:h=74:color=0x06111f@0.72:t=fill,"
            f"drawtext=text='{safe}':fontcolor=white:fontsize=32:x=42:y=22[v]"
        )
        cmd = [ffmpeg, "-y", "-i", str(base), "-i", str(audio), "-loop", "1", "-i", str(avatar),
               "-filter_complex", fc, "-map", "[v]", "-map", "1:a:0", "-t", f"{seconds:.3f}"]
    else:
        fc = f"drawbox=x=0:y=0:w=iw:h=74:color=0x06111f@0.72:t=fill,drawtext=text='{safe}':fontcolor=white:fontsize=32:x=42:y=22"
        cmd = [ffmpeg, "-y", "-i", str(base), "-i", str(audio), "-vf", fc,
               "-map", "0:v:0", "-map", "1:a:0", "-t", f"{seconds:.3f}"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=max(240, int(seconds * 5)))
    return out


def _concat_av_scenes(task_dir: Path, scenes: list[Path], output: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    listing = task_dir / "academy-scenes.txt"
    listing.write_text("".join(f"file '{scene}'\n" for scene in scenes), encoding="utf-8")
    first = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(output)]
    copy = subprocess.run(first, capture_output=True, text=True, timeout=600)
    if copy.returncode == 0 and output.is_file() and output.stat().st_size > 100_000:
        return
    subprocess.run(
        [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(output)],
        check=True, capture_output=True, text=True, timeout=900,
    )


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
    timeline = _normalize_timeline(lesson.get("sections") or [], lesson.get("script") or "")
    width, height = 1280, 720

    avatar = task_dir / "academy-avatar.jpg"
    if avatar_enabled:
        avatar_prompt = (
            "professional Brazilian AI instructor, friendly adult educator, chest-up portrait, looking directly at camera, "
            "dark navy smart casual outfit, premium futuristic education studio, cyan and warm orange rim light, "
            "clean background, realistic photography, same presenter identity, no text, no logo"
        )
        if not _pollinations_image(avatar_prompt, avatar, 768, 768, 1447):
            avatar_enabled = False

    rendered_scenes: list[Path] = []
    scene_manifest = []
    lipsync_modes = set()
    visual_seed = 9107

    for idx, scene in enumerate(timeline):
        scene_script = _clean(scene.get("script"))
        if not scene_script:
            continue
        scene_audio, scene_duration = _synthesize(scene_script, task_dir, voice_name, voice_rate)
        # _synthesize always writes the same filename; preserve each scene before next iteration.
        preserved_audio = task_dir / f"scene-{idx+1:02d}.mp3"
        shutil.copy2(scene_audio, preserved_audio)

        kind = scene.get("type", "talking_head")
        visual_path = None
        engine = ""
        if kind == "talking_head" and avatar_enabled and avatar.is_file():
            scene_video, engine = _render_talking_head_scene(
                task_dir, avatar, preserved_audio, scene_duration, scene.get("title") or "Aula", idx
            )
            lipsync_modes.add(engine)
        else:
            visual_path = _branded_slide(
                task_dir,
                scene.get("title") or f"Parte {idx+1}",
                scene_script,
                idx,
            )
            scene_video = _render_support_scene(
                task_dir, visual_path, avatar if avatar_enabled else None, preserved_audio,
                scene_duration, scene.get("title") or f"Parte {idx+1}", idx
            )
            engine = "support_visual"

        if not scene_video.is_file() or scene_video.stat().st_size < 50_000:
            raise AcademyLessonError(f"Falha ao renderizar cena {idx+1}")
        rendered_scenes.append(scene_video)
        scene_manifest.append({
            "index": idx + 1,
            "type": kind,
            "title": scene.get("title"),
            "duration": round(scene_duration, 2),
            "engine": engine,
            "visual": scene.get("visual"),
        })

    if not rendered_scenes:
        raise AcademyLessonError("Nenhuma cena da aula foi renderizada")

    final = task_dir / "xpex-academy-lesson.mp4"
    _concat_av_scenes(task_dir, rendered_scenes, final)
    if not final.is_file() or final.stat().st_size < 100_000:
        raise AcademyLessonError("MP4 final não foi criado")

    total_duration = _audio_duration(final)
    full_srt = task_dir / "lesson.srt"
    _make_srt(lesson.get("script") or "", max(total_duration, 1.0), full_srt)

    manifest = {
        "task_id": task_id,
        "title": lesson.get("title") or topic,
        "topic": topic,
        "objective": objective,
        "script": lesson.get("script") or "",
        "timeline": scene_manifest,
        "voice": voice_name,
        "audio_duration": round(total_duration, 2),
        "avatar_enabled": bool(avatar_enabled and avatar.is_file()),
        "lipsync_mode": "wav2lip" if "wav2lip" in lipsync_modes else ("presenter_motion" if avatar_enabled else "none"),
        "output": str(final),
        "engine": "xpex_instructor_engine_v3",
        "quality_profile": "academy_clean_no_gibberish",
        "support_visual_policy": "deterministic_branded_slides",
    }
    (task_dir / "lesson-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return final, manifest
