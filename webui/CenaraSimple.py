from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from uuid import uuid4
from urllib.parse import quote

import requests
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.append(str(ROOT))

from app.services.frontier_media import FrontierMediaError, generate_huggingface_video_file

STORAGE = ROOT / "storage"
TASKS = STORAGE / "tasks"
TASKS.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="Cenara", page_icon="🎬", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.stApp{background:linear-gradient(180deg,#050b12 0%,#07111b 55%,#04090f 100%);color:#f8fafc}
.block-container{max-width:1500px;padding-top:1rem;padding-bottom:3rem}
[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stSidebar"]{display:none!important}
.cz-top{display:flex;justify-content:space-between;align-items:center;padding:12px 0 18px;border-bottom:1px solid rgba(148,163,184,.16)}
.cz-brand{font-size:28px;font-weight:950;letter-spacing:.16em}
.cz-brand span{background:linear-gradient(90deg,#19d3f3,#3b82f6);-webkit-background-clip:text;background-clip:text;color:transparent}
.cz-pills{display:flex;gap:8px;flex-wrap:wrap}.cz-pill{border:1px solid rgba(148,163,184,.16);background:#0a1420;border-radius:999px;padding:8px 11px;font-size:11px;color:#cbd5e1}
.cz-hero{margin:18px 0;padding:30px;border:1px solid rgba(148,163,184,.16);border-radius:22px;background:linear-gradient(110deg,rgba(8,19,31,.96),rgba(8,19,31,.58)),url('https://images.unsplash.com/photo-1519608487953-e999c86e7455?auto=format&fit=crop&w=1600&q=85') center/cover no-repeat}
.cz-hero h1{font-size:clamp(38px,5vw,70px);line-height:.98;letter-spacing:-.05em;margin:4px 0 12px}
.cz-hero p{max-width:760px;color:#c3cfda;font-size:16px}
.cz-grid{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(360px,.8fr);gap:18px}
.cz-card{border:1px solid rgba(148,163,184,.16);border-radius:18px;background:linear-gradient(145deg,rgba(11,23,36,.94),rgba(6,14,24,.88));padding:18px}
.stTextArea textarea,.stSelectbox [data-baseweb="select"]{background:#07111b!important;border:1px solid rgba(148,163,184,.18)!important;border-radius:13px!important;color:white!important}
.stButton>button{border:0!important;border-radius:13px!important;background:linear-gradient(90deg,#0ecff1,#2563eb,#ff8a3d)!important;color:white!important;font-weight:900!important;min-height:48px}
.cz-steps{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:14px}.cz-step{border:1px solid rgba(148,163,184,.16);border-radius:12px;background:#091420;padding:11px}.cz-step b{font-size:12px}.cz-step small{display:block;color:#93a4b8;font-size:10px;margin-top:2px}
@media(max-width:900px){.cz-grid{grid-template-columns:1fr}.cz-steps{grid-template-columns:repeat(2,1fr)}.cz-top{align-items:flex-start;flex-direction:column;gap:12px}}
</style>
""", unsafe_allow_html=True)

def has(name: str) -> bool:
    return bool(str(os.getenv(name, "") or "").strip())

def director(prompt: str, style: str, seconds: int) -> dict:
    fallback = {
        "title": prompt[:72] or "Vídeo Cenara",
        "visual_prompt": prompt + ". Premium cinematic commercial, smooth camera movement, realistic lighting, no text, no watermark.",
    }
    key = str(os.getenv("OPENROUTER_API_KEY", "") or "").strip()
    if not key:
        return fallback
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            json={
                "model": os.getenv("OPENROUTER_MODEL", "openrouter/free"),
                "messages": [
                    {"role": "system", "content": "Return only a polished English text-to-video prompt. No JSON. No markdown. Make it cinematic, realistic, coherent, no text or watermark."},
                    {"role": "user", "content": "User idea: " + prompt + "\nStyle: " + style + "\nDuration: " + str(seconds) + " seconds."},
                ],
                "temperature": 0.6,
                "max_tokens": 260,
            },
            timeout=(20,120),
        )
        if response.status_code >= 400:
            return fallback
        value = str((((response.json().get("choices") or [{}])[0].get("message") or {}).get("content")) or "").strip()
        return {"title": prompt[:72] or "Vídeo Cenara", "visual_prompt": value[:2200] if value else fallback["visual_prompt"]}
    except Exception:
        return fallback

def valid_mp4(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 10_000:
        return False
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return True
    try:
        p = subprocess.run([ffprobe,"-v","error","-show_entries","format=duration","-of","json",str(path)],capture_output=True,text=True,timeout=20,check=True)
        return float((json.loads(p.stdout).get("format") or {}).get("duration") or 0) > 0.5
    except Exception:
        return False


def pollinations_image(prompt: str, target: Path, width: int, height: int, seed: int) -> bool:
    """Best-effort free public image generation used only as a visual fallback."""
    cleaned = " ".join((prompt or "").split()).strip()
    if not cleaned:
        return False
    url = "https://image.pollinations.ai/prompt/" + quote(cleaned[:1400], safe="")
    try:
        response = requests.get(
            url,
            params={
                "width": width,
                "height": height,
                "seed": seed,
                "nologo": "true",
                "enhance": "true",
                "model": "flux",
            },
            timeout=(20, 150),
        )
        ctype = str(response.headers.get("content-type", "")).lower()
        if response.status_code >= 400 or "image" not in ctype or len(response.content) < 20_000:
            return False
        target.write_bytes(response.content)
        return target.is_file() and target.stat().st_size > 20_000
    except Exception:
        return False


def _motion_kind(text: str) -> str:
    value = (text or "").lower()
    if any(x in value for x in ["carro","car ","vehicle","veículo","veiculo","moto","motorcycle","estrada","road","highway","acelerando","correndo","speed"]):
        return "vehicle"
    if any(x in value for x in ["avião","aviao","plane","drone","voando","flying","travel","viagem"]):
        return "travel"
    if any(x in value for x in ["pessoa","person","homem","mulher","walking","caminhando","running"]):
        return "people"
    return "cinematic"


def _motion_shots(visual_prompt: str, motion_kind: str):
    if motion_kind == "vehicle":
        return [
            visual_prompt + ". same black sports car, entering frame from the left on a highway, low tracking camera, wheels beginning to spin, road motion blur",
            visual_prompt + ". same black sports car accelerating fast at center frame, dynamic side tracking shot, spinning wheels, strong road motion blur, realistic reflections",
            visual_prompt + ". same black sports car passing camera at high speed toward the right, low angle dolly shot, strong directional blur, moving landscape",
            visual_prompt + ". same black sports car farther ahead on the highway, rear three-quarter view, receding into distance, dynamic road perspective",
        ]
    if motion_kind == "travel":
        return [
            visual_prompt + ". wide establishing shot, subject entering frame, cinematic movement",
            visual_prompt + ". tracking shot moving forward with the subject, realistic motion",
            visual_prompt + ". medium dynamic shot, camera panning with subject, environmental parallax",
            visual_prompt + ". closing shot, subject moving away into depth, cinematic finish",
        ]
    if motion_kind == "people":
        return [
            visual_prompt + ". same person beginning to move, wide shot, natural posture",
            visual_prompt + ". same person walking through frame, medium tracking shot, natural body motion",
            visual_prompt + ". same person continuing forward, side tracking shot, realistic movement",
            visual_prompt + ". same person arriving at destination, cinematic closing shot",
        ]
    return [
        visual_prompt + ". wide establishing shot, cinematic composition, premium commercial frame",
        visual_prompt + ". slow camera push forward, medium hero shot, realistic detail, coherent subject continuity",
        visual_prompt + ". side camera move with subtle parallax, premium commercial lighting",
        visual_prompt + ". closing hero frame, dramatic polished advertising finish",
    ]


def storyboard_video(task_dir: Path, visual_prompt: str, aspect: str, seconds: int) -> Path | None:
    """Create a motion-first MP4 from prompt-matched AI imagery and cinematic camera movement."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("CENARA_GENERATION stage=storyboard status=skip reason=ffmpeg_missing")
        return None

    sizes = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (720, 720)}
    w, h = sizes.get(aspect, (1280, 720))
    image_w, image_h = (1024, 576) if aspect == "16:9" else ((576, 1024) if aspect == "9:16" else (768, 768))
    motion_kind = _motion_kind(visual_prompt)
    shot_prompts = _motion_shots(visual_prompt, motion_kind)

    images = []
    seed_base = int(time.time()) % 100000
    # Keep a related seed family so the subject has more visual continuity.
    for idx, shot in enumerate(shot_prompts):
        target = task_dir / f"motion-{idx+1}.jpg"
        ok = pollinations_image(shot, target, image_w, image_h, seed_base + idx * 3)
        print(f"CENARA_GENERATION stage=image motion={motion_kind} index={idx+1} status={'ok' if ok else 'fail'}")
        if ok:
            images.append(target)
    if not images:
        return None

    clip_seconds = max(1.2, float(seconds) / len(images))
    clips = []
    for idx, image in enumerate(images):
        clip = task_dir / f"motion-{idx+1}.mp4"
        frames = max(36, int(clip_seconds * 30))
        # Alternate camera directions to create visible cinematic motion rather than a static zoom.
        if idx % 3 == 0:
            zoompan = f"zoompan=z='min(zoom+0.0024,1.16)':x='max(0,iw/2-(iw/zoom/2)-on*1.8)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps=30"
        elif idx % 3 == 1:
            zoompan = f"zoompan=z='min(zoom+0.0018,1.14)':x='min(iw-iw/zoom,iw/2-(iw/zoom/2)+on*1.6)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps=30"
        else:
            zoompan = f"zoompan=z='min(zoom+0.0022,1.15)':x='iw/2-(iw/zoom/2)':y='max(0,ih/2-(ih/zoom/2)-on*0.9)':d={frames}:s={w}x{h}:fps=30"
        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},"
            f"{zoompan},"
            "eq=contrast=1.04:saturation=1.06,"
            "format=yuv420p"
        )
        try:
            subprocess.run(
                [
                    ffmpeg, "-y", "-loop", "1", "-i", str(image),
                    "-vf", vf,
                    "-t", f"{clip_seconds:.2f}", "-r", "30",
                    "-an", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "21", "-movflags", "+faststart", str(clip),
                ],
                check=True, capture_output=True, text=True, timeout=180,
            )
            if valid_mp4(clip):
                clips.append(clip)
                print(f"CENARA_GENERATION stage=motion_clip index={idx+1} status=ok bytes={clip.stat().st_size}")
        except Exception as exc:
            detail = getattr(exc, "stderr", "") or str(exc)
            print(f"CENARA_GENERATION stage=motion_clip index={idx+1} status=fail detail={' '.join(detail.split())[:240]}")

    if not clips:
        return None

    # Smooth xfade between related frames. Fall back to concat if xfade is unavailable.
    out = task_dir / "cenara-motion-storyboard.mp4"
    if len(clips) > 1:
        transition = min(0.35, clip_seconds * 0.20)
        inputs = []
        for clip in clips:
            inputs += ["-i", str(clip)]
        parts = []
        prev = "[0:v]"
        offset = clip_seconds - transition
        for i in range(1, len(clips)):
            tag = f"[v{i}]"
            parts.append(f"{prev}[{i}:v]xfade=transition=fade:duration={transition:.2f}:offset={offset:.2f}{tag}")
            prev = tag
            offset += clip_seconds - transition
        try:
            subprocess.run(
                [ffmpeg, "-y", *inputs, "-filter_complex", ";".join(parts), "-map", prev,
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
                 "-r", "30", "-movflags", "+faststart", str(out)],
                check=True, capture_output=True, text=True, timeout=240,
            )
            if valid_mp4(out):
                print(f"CENARA_GENERATION stage=motion_storyboard status=pass kind={motion_kind} bytes={out.stat().st_size}")
                return out
        except Exception as exc:
            print(f"CENARA_GENERATION stage=xfade status=fail detail={' '.join(str(exc).split())[:180]}")

    listing = task_dir / "motion-storyboard.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in clips), encoding="utf-8")
    try:
        subprocess.run(
            [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
             "-movflags", "+faststart", str(out)],
            check=True, capture_output=True, text=True, timeout=240,
        )
        if valid_mp4(out):
            print(f"CENARA_GENERATION stage=motion_storyboard status=pass kind={motion_kind} mode=concat bytes={out.stat().st_size}")
            return out
    except Exception as exc:
        print(f"CENARA_GENERATION stage=motion_storyboard status=fail detail={' '.join(str(exc).split())[:260]}")
    return None

def local_video(task_dir: Path, prompt: str, aspect: str, seconds: int) -> Path:
    """Guaranteed local MP4 fallback with animated graphics; no external provider/font dependency."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg ausente")
    sizes = {"16:9": (1280,720), "9:16": (720,1280), "1:1": (720,720)}
    w,h = sizes.get(aspect,(1280,720))
    out = task_dir / "cenara-local.mp4"
    vf = (
        f"color=c=0x06111f:s={w}x{h}:r=30:d={seconds},"
        f"drawbox=x='mod(t*180,{w+360})-360':y='h*0.12':w=360:h=140:color=0x0ea5e9@0.30:t=fill,"
        f"drawbox=x='{w}-mod(t*140,{w+320})':y='h*0.68':w=320:h=120:color=0xff7a00@0.25:t=fill,"
        f"drawbox=x='w*0.08':y='h*0.20':w='w*0.84':h='h*0.58':color=0x020817@0.50:t=fill,"
        "format=yuv420p"
    )
    cmd = [
        ffmpeg, "-y", "-f", "lavfi", "-i", vf,
        "-t", str(seconds), "-r", "30", "-an",
        "-c:v", "libx264", "-preset", "veryfast",
        "-movflags", "+faststart", str(out),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=240)
    except subprocess.CalledProcessError as exc:
        detail = " ".join((exc.stderr or "").split())[:400]
        print(f"CENARA_GENERATION stage=local status=fail detail={detail}")
        raise RuntimeError("Falha no render local")
    if not valid_mp4(out):
        print(f"CENARA_GENERATION stage=local status=invalid exists={out.exists()} bytes={out.stat().st_size if out.exists() else 0}")
        raise RuntimeError("MP4 local inválido")
    print(f"CENARA_GENERATION stage=local status=pass bytes={out.stat().st_size}")
    return out

def generate(prompt: str, style: str, aspect: str, seconds: int):
    task_id = "quick-" + str(int(time.time())) + "-" + uuid4().hex[:8]
    task_dir = TASKS / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    direction = director(prompt, style, seconds)
    provider_error = ""

    # 1) Zero-cost visual path proven in production canary: AI images -> cinematic MP4.
    storyboard = storyboard_video(task_dir, direction["visual_prompt"], aspect, seconds)
    if storyboard and valid_mp4(storyboard):
        return storyboard, "motion_storyboard", provider_error

    # 2) Optional Hugging Face video path. Failure never blocks delivery.
    if has("HF_TOKEN") and os.getenv("CENARA_TRY_HF_VIDEO", "0") == "1":
        target = task_dir / "cenara-video.mp4"
        try:
            generate_huggingface_video_file(
                direction["visual_prompt"],
                str(target),
                model=os.getenv("CENARA_HF_VIDEO_MODEL","Wan-AI/Wan2.1-T2V-1.3B"),
            )
            if valid_mp4(target):
                return target, "huggingface", provider_error
        except FrontierMediaError as exc:
            provider_error = " ".join(str(exc).split())[:220]
        except Exception as exc:
            provider_error = type(exc).__name__

    # 3) Guaranteed local fallback. Always returns a validated MP4 or raises a specific render error.
    target = local_video(task_dir, prompt, aspect, seconds)
    return target, "local_motion", provider_error

def recent(limit=6):
    items=[]
    for p in TASKS.glob("quick-*/cenara-*.mp4"):
        try:
            if valid_mp4(p):
                items.append(p)
        except Exception:
            pass
    return sorted(items,key=lambda p:p.stat().st_mtime,reverse=True)[:limit]

badges = [
    "OpenRouter pronto" if has("OPENROUTER_API_KEY") else "Diretor local",
    "HF conectado" if has("HF_TOKEN") else "HF indisponível",
    "FFmpeg pronto" if shutil.which("ffmpeg") else "FFmpeg ausente",
    "Sem login · sem rotas",
]
st.markdown('<div class="cz-top"><div class="cz-brand"><span>▶</span> CENARA</div><div class="cz-pills">' + ''.join('<span class="cz-pill">● '+x+'</span>' for x in badges) + '</div></div>', unsafe_allow_html=True)
st.markdown('<div class="cz-hero"><h1>Digite a ideia.<br><span style="color:#19d3f3">A Cenara cria o vídeo.</span></h1><p>Sem chave na tela, sem menu técnico e sem rotas quebradas. Escreva o prompt e receba o MP4 no mesmo lugar.</p></div>', unsafe_allow_html=True)

left,right=st.columns([1.2,1],gap="large")
with left:
    st.markdown('<div class="cz-card"><h2>Criar vídeo</h2><p style="color:#93a4b8">Descreva exatamente o vídeo que você quer.</p></div>',unsafe_allow_html=True)
    prompt=st.text_area("Prompt do vídeo",height=220,placeholder="Ex.: Crie um vídeo cinematográfico apresentando a XPeX Academy como uma escola de IA futurista, com luz azul e laranja, câmera suave e atmosfera premium.")
    a,b,c=st.columns(3)
    with a:
        style=st.selectbox("Estilo",["Cinemático","Institucional","Comercial","Educativo","Redes Sociais"])
    with b:
        aspect=st.selectbox("Formato",["16:9","9:16","1:1"])
    with c:
        seconds=st.selectbox("Duração",[5,8,10,15],index=2,format_func=lambda x:str(x)+"s")
    go=st.button("✨ Gerar vídeo agora",use_container_width=True,type="primary",disabled=not prompt.strip())
    st.markdown('<div class="cz-steps"><div class="cz-step"><b>01 · Prompt</b><small>Você descreve</small></div><div class="cz-step"><b>02 · Diretor IA</b><small>OpenRouter organiza</small></div><div class="cz-step"><b>03 · Render</b><small>Motion Storyboard → local</small></div><div class="cz-step"><b>04 · MP4</b><small>Preview e download</small></div></div>',unsafe_allow_html=True)

with right:
    st.markdown('<div class="cz-card"><h2>Preview</h2><p style="color:#93a4b8">O resultado aparece aqui.</p></div>',unsafe_allow_html=True)

if go:
    with st.status("Cenara está criando...",expanded=True) as status:
        st.write("Direção criativa...")
        try:
            output,provider,provider_error=generate(prompt,style,aspect,seconds)
            if not valid_mp4(output):
                raise RuntimeError("MP4 inválido")
            st.session_state["cenara_video"]=str(output)
            st.session_state["cenara_provider"]=provider
            st.session_state["cenara_provider_error"]=provider_error
            status.update(label="Vídeo pronto",state="complete",expanded=False)
        except Exception as exc:
            status.update(label="Falha na geração",state="error",expanded=True)
            st.error("Falha na geração: " + (str(exc) or type(exc).__name__))
            print(f"CENARA_GENERATION stage=ui status=fail type={type(exc).__name__} detail={' '.join(str(exc).split())[:300]}")

latest=st.session_state.get("cenara_video")
if latest and Path(latest).is_file():
    with right:
        st.video(latest)
        st.caption("Motor: "+st.session_state.get("cenara_provider","-"))
        provider_error=st.session_state.get("cenara_provider_error","")
        if provider_error:
            st.info("Provider de vídeo generativo indisponível; a Cenara entregou o melhor fallback disponível.")
        data=Path(latest).read_bytes()
        st.download_button("Baixar MP4",data=data,file_name="cenara-video.mp4",mime="video/mp4",use_container_width=True)

items=recent()
if items:
    st.divider()
    st.subheader("Biblioteca recente")
    cols=st.columns(min(3,len(items)))
    for i,p in enumerate(items):
        with cols[i%len(cols)]:
            st.video(str(p))
            st.caption(p.parent.name)
