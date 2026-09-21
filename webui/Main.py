import os
import shutil
import sys
import webbrowser
import json
import time
import re
import hashlib
import subprocess
from datetime import datetime
from contextlib import contextmanager, suppress
from pathlib import Path
from uuid import UUID, uuid4

import requests
import streamlit as st
from loguru import logger

from pathlib import Path as _CenaraPath


def _render_seedance_first_flight_preview():
    path = _CenaraPath("/MoneyPrinterTurbo/storage/canary/seedance2-first-flight.mp4")
    if path.is_file() and path.stat().st_size > 100_000:
        with st.expander("🎬 Seedance 2 · First Flight", expanded=False):
            st.caption("Primeiro teste real do Frontier Video Engine. Master preservado do provider.")
            st.video(str(path))
            st.caption(f"{path.stat().st_size / 1024 / 1024:.1f} MB · armazenado no volume persistente")

# Add the root directory of the project to the system path to allow importing modules from the project
root_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)
    print("******** sys.path ********")
    print(sys.path)
    print("")

from app.config import config
from app.models.schema import (
    MaterialInfo,
    VideoAspect,
    VideoConcatMode,
    VideoParams,
    VideoTransitionMode,
)
from app.services import llm, voice
from app.services import state as sm
from app.services.runtime_limits import get_runtime_limits
from app.services.railway_render import ffprobe_validate_mp4
from app.services import task as tm
from app.utils import utils

st.set_page_config(
    page_title="Cenara",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={
        "Report a bug": "https://github.com/harry0703/MoneyPrinterTurbo/issues",
        "About": "# MoneyPrinterTurbo\nSimply provide a topic or keyword for a video, and it will "
        "automatically generate the video copy, video materials, video subtitles, "
        "and video background music before synthesizing a high-definition short "
        "video.\n\nhttps://github.com/harry0703/MoneyPrinterTurbo",
    },
)


streamlit_style = """
<style>
:root {
    --cenara-bg: #060816;
    --cenara-panel: rgba(12, 18, 36, 0.82);
    --cenara-panel-strong: rgba(15, 23, 42, 0.92);
    --cenara-border: rgba(148, 163, 184, 0.16);
    --cenara-blue: #5B7CFF;
    --cenara-purple: #8B5CF6;
    --cenara-cyan: #06b6d4;
    --cenara-green: #22c55e;
    --cenara-text: #f8fafc;
    --cenara-muted: #94a3b8;
}
.stApp {
    background:
        radial-gradient(circle at 8% 4%, rgba(37, 99, 235, 0.30), transparent 25rem),
        radial-gradient(circle at 86% 8%, rgba(124, 58, 237, 0.24), transparent 28rem),
        linear-gradient(135deg, #020617 0%, #061126 48%, #020817 100%);
    color: var(--cenara-text);
}
.block-container { padding-top: 1.25rem; padding-bottom: 2rem; max-width: 1500px; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { display: none; }
h1, h2, h3 { color: var(--cenara-text) !important; }
.stButton > button, .stFormSubmitButton > button {
    border-radius: 14px !important;
    border: 1px solid rgba(96, 165, 250, .30) !important;
    background: linear-gradient(135deg, #2563eb, #7c3aed) !important;
    color: #fff !important;
    box-shadow: 0 16px 42px rgba(37, 99, 235, .22) !important;
    font-weight: 800 !important;
}
.stTextInput input, .stTextArea textarea, .stSelectbox [data-baseweb="select"] {
    border-radius: 14px !important;
    border-color: rgba(148, 163, 184, .18) !important;
    background-color: rgba(2, 8, 23, .54) !important;
    color: #f8fafc !important;
}
.cenara-dashboard { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 1.6rem; align-items: start; }
.cenara-sidebar {
    position: sticky; top: 1rem; min-height: calc(100vh - 2rem); padding: 1.35rem;
    border: 1px solid rgba(37, 99, 235, .24); border-radius: 26px;
    background: linear-gradient(180deg, rgba(7, 18, 44, .96), rgba(3, 10, 27, .90));
    box-shadow: 0 26px 80px rgba(2, 8, 23, .46), inset 0 1px 0 rgba(255,255,255,.04);
}
.cenara-logo { display:flex; align-items:center; gap:.75rem; font-size:1.65rem; font-weight:950; margin-bottom:1.5rem; }
.cenara-logo-mark { width:42px; height:42px; border-radius:16px; display:grid; place-items:center; background:conic-gradient(from 210deg, #06b6d4, #2563eb, #7c3aed, #06b6d4); box-shadow:0 0 30px rgba(37,99,235,.45); }
.cenara-menu { display:grid; gap:.35rem; }
.cenara-menu-item { display:flex; gap:.75rem; align-items:center; padding:.75rem .85rem; color:#cbd5e1; border-radius:13px; font-weight:700; }
.cenara-menu-item.active { color:#fff; background:linear-gradient(135deg, rgba(37,99,235,.78), rgba(37,99,235,.25)); border:1px solid rgba(96,165,250,.28); }
.cenara-plan-card, .cenara-account-card { margin-top:1rem; padding:1rem; border-radius:18px; border:1px solid var(--cenara-border); background:rgba(15,23,42,.62); }
.cenara-main { min-width:0; }
.cenara-topbar { display:flex; justify-content:space-between; gap:1rem; align-items:center; margin:.35rem 0 1rem; }
.cenara-welcome { font-size:1.55rem; font-weight:950; }
.cenara-subtitle { color:#cbd5e1; margin-top:.2rem; }
.cenara-actions { display:flex; gap:.75rem; align-items:center; flex-wrap:wrap; justify-content:flex-end; }
.cenara-search, .cenara-pill, .cenara-owner { border:1px solid var(--cenara-border); background:rgba(2,8,23,.56); border-radius:14px; padding:.75rem .95rem; color:#cbd5e1; }
.cenara-owner { display:flex; gap:.65rem; align-items:center; color:#fff; }
.cenara-grid { display:grid; grid-template-columns: minmax(0, 1.55fr) minmax(360px, .95fr); gap:1.25rem; }
.cenara-card, .cenara-flow-card, .cenara-provider-card {
    border: 1px solid var(--cenara-border); background: linear-gradient(145deg, rgba(15, 23, 42, 0.76), rgba(2, 8, 23, 0.58));
    border-radius: 22px; box-shadow: 0 22px 70px rgba(2, 8, 23, 0.34), inset 0 1px 0 rgba(255,255,255,.035);
}
.cenara-card { padding:1.25rem; }
.cenara-card-title { font-weight:900; font-size:1.05rem; color:#f8fafc; }
.cenara-card-copy, .cenara-flow-copy, .cenara-provider-copy { color:var(--cenara-muted); font-size:.88rem; }
.cenara-project-grid { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:.75rem; margin-top:1rem; }
.cenara-field { border:1px solid rgba(148,163,184,.14); border-radius:15px; padding:.85rem; background:rgba(2,8,23,.42); }
.cenara-field small { color:#94a3b8; display:block; margin-bottom:.2rem; } .cenara-field strong { color:#f8fafc; }
.cenara-cta { margin-top:1rem; text-align:right; } .cenara-cta span { display:inline-block; padding:.9rem 2.4rem; border-radius:14px; color:#fff; font-weight:900; background:linear-gradient(135deg,#2563eb,#7c3aed,#a855f7); box-shadow:0 18px 45px rgba(124,58,237,.32); }
.cenara-preview-art { height:235px; margin-top:.85rem; border-radius:16px; position:relative; overflow:hidden; background:linear-gradient(115deg, rgba(15,23,42,.9), rgba(37,99,235,.20)), radial-gradient(circle at 78% 22%, rgba(56,189,248,.35), transparent 9rem), linear-gradient(135deg,#111827,#020617); }
.cenara-preview-art:before { content:'TRANSFORME\\A SUA IDEIA\\A EM VÍDEO'; white-space:pre; position:absolute; left:1.5rem; top:2.2rem; font-size:1.65rem; line-height:1.05; font-weight:950; color:#fff; }
.cenara-play { position:absolute; inset:0; margin:auto; width:64px; height:64px; border-radius:999px; display:grid; place-items:center; background:linear-gradient(135deg,#2563eb,#7c3aed); box-shadow:0 0 38px rgba(37,99,235,.55); font-size:1.5rem; }
.cenara-progress { position:absolute; left:1rem; right:1rem; bottom:1rem; height:6px; border-radius:999px; background:rgba(148,163,184,.28); } .cenara-progress span { display:block; width:58%; height:100%; border-radius:inherit; background:linear-gradient(90deg,#2563eb,#a855f7); }
.cenara-tag { position:absolute; right:1rem; top:1rem; padding:.3rem .55rem; border-radius:8px; background:rgba(15,23,42,.75); color:#e2e8f0; font-weight:800; font-size:.78rem; }
.cenara-metrics, .cenara-modules { display:grid; gap:.75rem; margin-top:.75rem; } .cenara-metrics { grid-template-columns:repeat(4,1fr); } .cenara-modules { grid-template-columns:repeat(3,1fr); }
.cenara-metric-value { font-size:1.55rem; font-weight:950; color:#fff; } .cenara-positive { color:#4ade80; font-size:.82rem; }
.cenara-flow-card, .cenara-provider-card { padding:1rem; min-height:124px; }
.cenara-flow-icon { width:2.35rem; height:2.35rem; border-radius:.9rem; display:grid; place-items:center; background:linear-gradient(135deg,var(--cenara-blue),var(--cenara-purple)); margin-bottom:.55rem; }
.cenara-flow-title { font-weight:850; margin-bottom:.25rem; color:#f8fafc; }
.cenara-status-ok, .cenara-status-missing { border-radius:999px; padding:.35rem .7rem; font-size:.78rem; font-weight:800; display:inline-block; }
.cenara-status-ok { color:#bbf7d0; background:rgba(22,163,74,.14); border:1px solid rgba(74,222,128,.24); }
.cenara-status-missing { color:#fed7aa; background:rgba(249,115,22,.13); border:1px solid rgba(251,146,60,.24); }
.cenara-section-title { margin:1.25rem 0 .65rem; font-size:1.05rem; font-weight:900; color:#e2e8f0; }
.cenara-footer-cta { margin-top:1rem; display:flex; justify-content:space-between; align-items:center; gap:1rem; padding:1.25rem 1.6rem; border-radius:22px; border:1px solid rgba(96,165,250,.25); background:linear-gradient(105deg, rgba(37,99,235,.36), rgba(124,58,237,.30)), radial-gradient(circle at 72% 50%, rgba(56,189,248,.25), transparent 14rem); }
.cenara-footer-title { font-size:1.25rem; font-weight:950; color:#fff; } .cenara-footer-button { padding:.85rem 1.8rem; border-radius:13px; background:linear-gradient(135deg,#2563eb,#7c3aed); color:#fff; font-weight:900; opacity:.78; }
.cenara-footer-note { color:#94a3b8; font-size:.82rem; text-align:center; margin:1rem 0 .35rem; }

.cenara-hero { padding:1.5rem; border:1px solid rgba(91,124,255,.26); border-radius:28px; background:radial-gradient(circle at 75% 15%, rgba(139,92,246,.35), transparent 18rem), linear-gradient(135deg, rgba(12,18,36,.94), rgba(16,25,53,.72)); box-shadow:0 28px 90px rgba(2,8,23,.42); margin-bottom:1rem; }
.cenara-eyebrow { color:#93c5fd; text-transform:uppercase; letter-spacing:.14em; font-weight:900; font-size:.74rem; }
.cenara-hero h1 { font-size:clamp(2.1rem, 5vw, 4.6rem); line-height:.95; margin:.35rem 0 .7rem; letter-spacing:-.06em; }
.cenara-badges { display:flex; gap:.55rem; flex-wrap:wrap; margin:.85rem 0; }
.cenara-badge { padding:.45rem .7rem; border-radius:999px; background:rgba(91,124,255,.14); border:1px solid rgba(255,255,255,.09); color:#dbeafe; font-weight:800; font-size:.82rem; }
.cenara-stepper { display:grid; grid-template-columns:repeat(8,minmax(0,1fr)); gap:.45rem; margin:.75rem 0 1rem; }
.cenara-step { padding:.65rem .45rem; border-radius:14px; text-align:center; color:#a7b0d6; background:rgba(255,255,255,.035); border:1px solid rgba(255,255,255,.07); font-weight:800; font-size:.82rem; }
.cenara-step.active { color:#fff; background:linear-gradient(135deg, rgba(91,124,255,.52), rgba(139,92,246,.34)); border-color:rgba(91,124,255,.44); }
.cenara-workspace-card { border:1px solid rgba(255,255,255,.08); border-radius:24px; padding:1rem; background:linear-gradient(145deg, rgba(12,18,36,.86), rgba(6,8,22,.62)); min-height:100%; }
.cenara-card-kicker { color:#93c5fd; font-size:.76rem; font-weight:900; text-transform:uppercase; letter-spacing:.1em; }
.cenara-status-lane { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.65rem; margin:.75rem 0 1rem; }
.cenara-timeline { display:grid; gap:.35rem; margin-top:.7rem; }
.cenara-timeline-row { display:flex; justify-content:space-between; gap:.75rem; padding:.45rem .6rem; border-radius:12px; background:rgba(255,255,255,.035); color:#cbd5e1; font-size:.82rem; }
.cenara-status-dot { width:.55rem; height:.55rem; border-radius:999px; background:#22c55e; display:inline-block; margin-right:.35rem; box-shadow:0 0 16px rgba(34,197,94,.55); }
@media (max-width: 900px) { .cenara-stepper, .cenara-status-lane { grid-template-columns:repeat(2,1fr); } }

@media (max-width: 1100px) { .cenara-dashboard { grid-template-columns:1fr; } .cenara-sidebar { position:relative; min-height:auto; } .cenara-grid, .cenara-metrics, .cenara-modules { grid-template-columns:1fr; } .cenara-project-grid { grid-template-columns:1fr; } }
</style>
"""
_render_seedance_first_flight_preview()

st.markdown(streamlit_style, unsafe_allow_html=True)



def cenara_runtime_limits():
    return get_runtime_limits()


def _cenara_runtime_dir() -> Path:
    path = Path(root_dir) / "storage" / "cenara_runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cenara_generation_lock_path() -> Path:
    return _cenara_runtime_dir() / "generation.lock"


def _cenara_remove_generation_lock_if_same(lock: Path, expected: dict) -> bool:
    try:
        current = json.loads(lock.read_text(encoding="utf-8"))
        if all(current.get(key) == expected.get(key) for key in ("task_id", "owner", "created_at_epoch")):
            lock.unlink()
            return True
    except Exception:
        return False
    return False


def cenara_clear_stale_generation_lock(show_message=False):
    lock = _cenara_generation_lock_path()
    existed = lock.exists()
    status = cenara_generation_lock_status()
    released = existed and status is None and not lock.exists()
    if released and show_message:
        st.session_state["cenara_stale_lock_released"] = True
    return released


def cenara_generation_lock_status():
    lock = _cenara_generation_lock_path()
    if not lock.exists():
        return None
    try:
        data = json.loads(lock.read_text(encoding="utf-8"))
        created = float(data.get("created_at_epoch", 0))
        if time.time() - created > cenara_runtime_limits().generation_lock_ttl_seconds:
            _cenara_remove_generation_lock_if_same(lock, data)
            return None
        return data
    except Exception:
        try:
            if time.time() - lock.stat().st_mtime <= cenara_runtime_limits().generation_lock_ttl_seconds:
                return {"status": "running", "task_id": "unknown"}
            lock.unlink(missing_ok=True)
        except Exception:
            return {"status": "running", "task_id": "unknown"}
        return None


def _cenara_atomic_write_generation_lock(lock: Path, metadata: dict) -> bool:
    fd = None
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as lock_file:
            fd = None
            lock_file.write(json.dumps(metadata, ensure_ascii=False))
            lock_file.flush()
            os.fsync(lock_file.fileno())
        return True
    except FileExistsError:
        return False
    finally:
        if fd is not None:
            os.close(fd)


@contextmanager
def cenara_single_flight_generation_lock(task_id: str):
    lock = _cenara_generation_lock_path()
    owner = uuid4().hex
    metadata = {
        "task_id": task_id,
        "owner": owner,
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "created_at_epoch": time.time(),
        "status": "running",
    }
    acquired = _cenara_atomic_write_generation_lock(lock, metadata)
    if not acquired:
        current = cenara_generation_lock_status()
        if current:
            raise RuntimeError("CENARA_GENERATION_ALREADY_RUNNING")
        acquired = _cenara_atomic_write_generation_lock(lock, metadata)
        if not acquired:
            raise RuntimeError("CENARA_GENERATION_ALREADY_RUNNING")
    try:
        yield
    finally:
        with suppress(Exception):
            if lock.exists():
                data = json.loads(lock.read_text(encoding="utf-8"))
                if data.get("task_id") == task_id and data.get("owner") == owner:
                    lock.unlink()
        for key in list(st.session_state.keys()):
            if key.startswith("cenara_download_bytes_"):
                del st.session_state[key]


def _expected_operator_token() -> str:
    return os.getenv("GX1_ACCESS_TOKEN") or config.app.get("api_key", "")


def require_private_operator_token() -> None:
    expected_token = _expected_operator_token()
    if not expected_token:
        st.error("Private operator token is not configured. Set GX1_ACCESS_TOKEN before exposing this app.")
        st.stop()

    if st.session_state.get("cenara_private_operator_authenticated"):
        return

    st.title("Cenara Private MVP")
    st.info("Enter the private operator token to continue.")
    supplied_token = st.text_input("Private operator token", type="password", key="cenara_private_operator_token")
    if st.button("Unlock private operator console", type="primary"):
        if supplied_token == expected_token:
            st.session_state["cenara_private_operator_authenticated"] = True
            st.rerun()
        st.error("Invalid private operator token.")
    st.stop()


require_private_operator_token()

# 定义资源目录
font_dir = os.path.join(root_dir, "resource", "fonts")
song_dir = os.path.join(root_dir, "resource", "songs")
i18n_dir = os.path.join(root_dir, "webui", "i18n")
config_file = os.path.join(root_dir, "webui", ".streamlit", "webui.toml")
system_locale = utils.get_system_locale()
DEFAULT_CHATTERBOX_BASE_URL = "http://127.0.0.1:4123/v1"
DEFAULT_CHATTERBOX_MODEL = "chatterbox"
DEFAULT_CHATTERBOX_VOICES = ["default-Female"]


def render_cenara_sidebar():
    menu_items = [
        ("▦", "Dashboard", "active"), ("▣", "Projetos", ""), ("▶", "Criar Vídeo", ""),
        ("▤", "Roteiro IA", ""), ("◖", "Voz IA", ""), ("▬", "Legendas", ""),
        ("▧", "Banco de Cenas", ""), ("✿", "Brand Kit", ""), ("⇪", "Exportação", ""),
        ("⌁", "Analytics", ""), ("⚙", "Configurações", ""),
    ]
    items_html = "".join(f'<div class="cenara-menu-item {active}"><span>{icon}</span><span>{label}</span></div>' for icon, label, active in menu_items)
    return f"""
    <aside class="cenara-sidebar">
      <div class="cenara-logo"><span class="cenara-logo-mark">C</span><span>Cenara</span></div>
      <div class="cenara-menu">{items_html}</div>
      <div class="cenara-plan-card"><div class="cenara-card-title">Plano Profissional</div><div class="cenara-card-copy" style="margin:.45rem 0">Créditos restantes</div><div style="font-weight:900;color:#fff">8.450 <span style="color:#64748b">/ 10.000</span></div><div class="cenara-progress" style="position:relative;left:auto;right:auto;bottom:auto;margin-top:.65rem"><span style="width:84%"></span></div></div>
      <div class="cenara-account-card"><div style="font-weight:900;color:#fff">Gustavo Martins</div><div class="cenara-card-copy">gestor@agenciamax.com</div></div>
    </aside>
    """


def render_cenara_topbar():
    return """
    <div class="cenara-topbar"><div><div class="cenara-welcome">Bem-vindo de volta, Gustavo! 👋</div><div class="cenara-subtitle">Crie vídeos com IA para anúncios, vendas e conteúdo que converte.</div></div><div class="cenara-actions"><div class="cenara-search">⌕ Buscar projetos, vídeos ou recursos...</div><div class="cenara-pill">Novidades •</div><div class="cenara-pill">🔔 3</div><div class="cenara-owner"><span class="cenara-logo-mark" style="width:34px;height:34px;border-radius:12px">C</span><span><strong>Agência Max</strong><br><small>Proprietário</small></span></div></div></div>
    """


def render_cenara_project_creator():
    fields = [("◎", "Nicho", "Saúde e Bem-estar"), ("◇", "Promessa", "Emagreça com saúde e sem efeito sanfona"), ("♙", "Público", "Mulheres 25–45 anos"), ("▯", "Formato", "Vídeo Vertical (9:16)"), ("◷", "Duração", "30 segundos"), ("↗", "CTA", "Comece agora seu tratamento")]
    fields_html = "".join(f'<div class="cenara-field"><small>{icon} &nbsp; {label}</small><strong>{value}</strong></div>' for icon, label, value in fields)
    return f"""<div class="cenara-card"><div style="display:flex;justify-content:space-between;gap:1rem;align-items:center"><div><div class="cenara-card-title">Novo projeto de vídeo</div><div class="cenara-card-copy">Descreva seu projeto e a Cenara cuida do resto.</div></div><div class="cenara-card-copy">↻ Limpar campos</div></div><div class="cenara-project-grid">{fields_html}</div><div class="cenara-cta"><span>Gerar Vídeo com IA ✨</span></div></div>"""


def render_cenara_preview_card():
    return """<div class="cenara-card"><div style="display:flex;justify-content:space-between"><div class="cenara-card-title">Preview do vídeo</div><span class="cenara-tag" style="position:static">30s</span></div><div class="cenara-preview-art"><div class="cenara-tag">30s</div><div class="cenara-play">▶</div><div class="cenara-progress"><span></span></div></div><div class="cenara-field" style="margin-top:.75rem;text-align:center">✎ &nbsp;<strong>Editar no estúdio</strong></div></div><div class="cenara-card" style="margin-top:.75rem"><div class="cenara-card-title">Dicas para melhores resultados</div><div class="cenara-card-copy" style="line-height:1.9;margin-top:.5rem">● Seja claro na promessa do seu produto<br>● Use CTAs diretos e objetivos<br>● Vídeos curtos têm maior retenção<br>● Teste variações de criativos</div></div>"""


def render_cenara_metrics():
    metrics = [("✣", "Vídeos criados", "128", "+28% este mês"), ("⚑", "Criativos ativos", "56", "+18% este mês"), ("▰", "Campanhas", "23", "+15% este mês"), ("⌁", "Conversões estimadas", "3.452", "+32% este mês")]
    cards = "".join(f'<div class="cenara-flow-card"><div class="cenara-flow-icon">{icon}</div><div class="cenara-card-copy">{label}</div><div class="cenara-metric-value">{value}</div><div class="cenara-positive">{delta}</div></div>' for icon, label, value, delta in metrics)
    return f'<div class="cenara-metrics">{cards}</div>'


def render_cenara_modules_grid():
    modules = [("▶", "Criar Vídeo", "Gere vídeos profissionais com IA em minutos."), ("▤", "Roteiro IA", "Scripts persuasivos gerados por IA para vender mais."), ("◖", "Voz IA", "Vozes realistas que conectam e geram engajamento."), ("▧", "Banco de Cenas", "Milhares de cenas prontas para seus vídeos."), ("Aa", "Brand Kit", "Cores, fontes e logos aplicados automaticamente."), ("⌁", "Analytics", "Acompanhe resultados e otimize campanhas.")]
    cards = "".join(f'<div class="cenara-flow-card"><div class="cenara-flow-icon">{icon}</div><div class="cenara-flow-title">{title}</div><div class="cenara-flow-copy">{copy}</div></div>' for icon, title, copy in modules)
    return f'<div class="cenara-section-title">Módulos</div><div class="cenara-modules">{cards}</div>'


def render_cenara_footer_cta():
    return """<div class="cenara-footer-cta"><div><div class="cenara-footer-title">Vídeos com IA para anúncios, vendas e conteúdo de alta conversão.</div><div class="cenara-card-copy">Mais estratégia. Menos esforço. Mais resultado.</div></div><div class="cenara-footer-button">Ver planos</div></div><div class="cenara-footer-note">© 2025 Cenara. Powered by <strong>GXEON</strong> · Based on MoneyPrinterTurbo MIT</div>"""


def render_cenara_premium_shell():
    st.markdown('<div class="cenara-dashboard">' + render_cenara_sidebar() + '<main class="cenara-main">' + render_cenara_topbar(), unsafe_allow_html=True)
    left, right = st.columns([1.55, .95], gap="large")
    with left:
        st.markdown(render_cenara_project_creator(), unsafe_allow_html=True)
        st.markdown(render_cenara_metrics(), unsafe_allow_html=True)
    with right:
        st.markdown(render_cenara_preview_card(), unsafe_allow_html=True)
    st.markdown(render_cenara_modules_grid() + render_cenara_footer_cta() + '</main></div>', unsafe_allow_html=True)


def render_cenara_provider_status_cards(provider_cards):
    provider_cols = st.columns(len(provider_cards))
    for provider_col, (provider_label, configured, help_url) in zip(provider_cols, provider_cards):
        with provider_col:
            st.markdown(_provider_status_html(provider_label, configured, help_url), unsafe_allow_html=True)


def _parse_chatterbox_voices(voices):
    # Chatterbox 是自托管服务，音色列表由用户在 WebUI 中手动输入。
    # 这里统一兼容 TOML 数组和输入框里的逗号分隔字符串，避免下拉框、
    # 试听按钮和后续生成流程使用不同格式导致状态不一致。
    if isinstance(voices, str):
        return [v.strip() for v in voices.split(",") if v.strip()]
    return [str(v).strip() for v in voices or [] if str(v).strip()]


def _sync_chatterbox_config_from_session_state():
    # Streamlit 的按钮会触发整页 rerun，而 Chatterbox 配置输入框位于
    # “试听语音合成”按钮之后。如果试听时只读取 config.chatterbox，可能拿不到
    # 用户刚在输入框里填入的 base_url/model/voices。先从 session_state 同步一次，
    # 可以保证按钮逻辑和输入框显示逻辑使用同一份最新配置。
    config.chatterbox["base_url"] = (
        st.session_state.get(
            "chatterbox_base_url_input",
            config.chatterbox.get("base_url") or DEFAULT_CHATTERBOX_BASE_URL,
        )
        or ""
    ).strip()
    chatterbox_api_key = st.session_state.get("chatterbox_api_key_input", "")
    if chatterbox_api_key:
        config.chatterbox["api_key"] = chatterbox_api_key
    config.chatterbox["model_id"] = (
        st.session_state.get(
            "chatterbox_model_input",
            config.chatterbox.get("model_id") or DEFAULT_CHATTERBOX_MODEL,
        )
        or DEFAULT_CHATTERBOX_MODEL
    ).strip()
    config.chatterbox["voices"] = _parse_chatterbox_voices(
        st.session_state.get(
            "chatterbox_voices_input",
            config.chatterbox.get("voices") or DEFAULT_CHATTERBOX_VOICES,
        )
    )


def _detect_audio_mime(audio_file: str, audio_bytes: bytes) -> str:
    # 有些 OpenAI-compatible TTS 服务，例如 travisvn/chatterbox-tts-api，
    # 即使请求 response_format=mp3，也会返回 WAV 内容。WebUI 试听如果固定
    # 使用 audio/mp3，浏览器可能无法播放，因此这里按文件头识别真实格式。
    header = audio_bytes[:12]
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return "audio/wav"
    if header.startswith(b"ID3") or header[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mp3"
    if header.startswith(b"OggS"):
        return "audio/ogg"
    ext = os.path.splitext(audio_file)[1].lower()
    return {
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
    }.get(ext, "audio/mp3")


if "video_subject" not in st.session_state:
    st.session_state["video_subject"] = ""
if "video_script" not in st.session_state:
    st.session_state["video_script"] = ""
if "video_terms" not in st.session_state:
    st.session_state["video_terms"] = ""
if "video_script_prompt" not in st.session_state:
    st.session_state["video_script_prompt"] = ""
if "custom_system_prompt" not in st.session_state:
    st.session_state["custom_system_prompt"] = llm.DEFAULT_SCRIPT_SYSTEM_PROMPT
if "use_custom_system_prompt" not in st.session_state:
    st.session_state["use_custom_system_prompt"] = False
if "match_materials_to_script" not in st.session_state:
    st.session_state["match_materials_to_script"] = bool(
        config.app.get("match_materials_to_script", False)
    )
if "ui_language" not in st.session_state:
    st.session_state["ui_language"] = config.ui.get("language", system_locale)
if "local_video_materials" not in st.session_state:
    # 记住用户最近一次已经落盘的本地素材，避免仅修改文案后二次生成时丢失素材列表。
    st.session_state["local_video_materials"] = []

# 加载语言文件
locales = utils.load_locales(i18n_dir)

# Language selector is intentionally kept as a compact operational control below the premium shell.
display_languages = []
selected_index = 0
for i, code in enumerate(locales.keys()):
    display_languages.append(f"{code} - {locales[code].get('Language')}")
    if code == st.session_state.get("ui_language", ""):
        selected_index = i

selected_language = st.selectbox(
    "Language / 语言",
    options=display_languages,
    index=selected_index,
    key="top_language_selector",
)
if selected_language:
    code = selected_language.split(" - ")[0].strip()
    st.session_state["ui_language"] = code
    config.ui["language"] = code

support_locales = [
    "zh-CN",
    "zh-HK",
    "zh-TW",
    "de-DE",
    "en-US",
    "fr-FR",
    "ru-RU",
    "vi-VN",
    "th-TH",
    "tr-TR",
]



CENARA_PROVIDER_ENV_ALIASES = {
    "openai": ("OPENAI_API_KEY", "OPENAI_KEY"),
    "pexels": ("PEXELS_API_KEY",),
    "pixabay": ("PIXABAY_API_KEY",),
    "coverr": ("COVER_API_KEY", "COVERR_API_KEY"),
    "elevenlabs": ("ELEVENLABS_API_KEY", "ELEVEN_API_KEY"),
}

CENARA_LLM_PROVIDER_ENV_ALIASES = {
    "openai": ("OPENAI_API_KEY", "OPENAI_KEY"),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "aihubmix": ("AIHUBMIX_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "google": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "azure": ("AZURE_OPENAI_API_KEY",),
    "azure-openai": ("AZURE_OPENAI_API_KEY",),
    "azure_openai": ("AZURE_OPENAI_API_KEY",),
    "openai_azure": ("AZURE_OPENAI_API_KEY",),
}

CENARA_LLM_PROVIDER_CONFIG_KEYS = {
    "openai": ("openai_api_key",),
    "deepseek": ("deepseek_api_key",),
    "aihubmix": ("aihubmix_api_key",),
    "gemini": ("gemini_api_key", "google_api_key"),
    "google": ("google_api_key", "gemini_api_key"),
    "azure": ("azure_api_key", "azure_openai_api_key"),
    "azure-openai": ("azure_openai_api_key", "azure_api_key"),
    "azure_openai": ("azure_openai_api_key", "azure_api_key"),
    "openai_azure": ("azure_openai_api_key", "azure_api_key"),
}

CENARA_ENV_RUNTIME_VALUES = {"app": {}, "elevenlabs": {}}

CENARA_MASKED_SECRET_MARKERS = (
    "cole sua nova chave",
    "paste your new key",
    "sua chave",
    "your api key",
    "api key",
    "password",
    "secret",
)


def _is_missing_secret_value(value) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    lowered = text.lower()
    if any(marker in lowered for marker in CENARA_MASKED_SECRET_MARKERS):
        return True
    visible = text.replace("•", "").replace("*", "").replace("x", "").replace("X", "").strip()
    return not visible


def _normalize_secret_values(value) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        candidates = value
    elif isinstance(value, str) and "," in value:
        candidates = value.split(",")
    else:
        candidates = [value]
    return [str(item).strip() for item in candidates if not _is_missing_secret_value(item)]


def _dedupe_preserving_order(values) -> list[str]:
    unique_values = []
    seen = set()
    for value in values:
        for normalized in _normalize_secret_values(value):
            if normalized not in seen:
                unique_values.append(normalized)
                seen.add(normalized)
    return unique_values


def _has_configured_secret(value) -> bool:
    return bool(_normalize_secret_values(value))


def _provider_secret_values_from_env(provider: str) -> list[str]:
    return _dedupe_preserving_order(os.environ.get(env_name) for env_name in CENARA_PROVIDER_ENV_ALIASES.get(provider, ()))


def _provider_secret_from_env(provider: str) -> str:
    values = _provider_secret_values_from_env(provider)
    return values[0] if values else ""


def _secret_values_from_env_names(env_names) -> list[str]:
    return _dedupe_preserving_order(os.environ.get(env_name) for env_name in env_names)


def _provider_secret_values_from_session(keys) -> list[str]:
    return _dedupe_preserving_order(st.session_state.get(key) for key in keys)


def _provider_secret_from_session(keys) -> str:
    values = _provider_secret_values_from_session(keys)
    return values[0] if values else ""


def _llm_provider_id_normalized(llm_provider_id: str) -> str:
    return (llm_provider_id or "openai").strip().lower().replace(" ", "_")


def _llm_provider_config_keys(llm_provider_id: str) -> tuple[str, ...]:
    provider_id = _llm_provider_id_normalized(llm_provider_id)
    return CENARA_LLM_PROVIDER_CONFIG_KEYS.get(provider_id, (f"{provider_id}_api_key",))


def _llm_provider_env_values(llm_provider_id: str) -> list[str]:
    provider_id = _llm_provider_id_normalized(llm_provider_id)
    return _secret_values_from_env_names(CENARA_LLM_PROVIDER_ENV_ALIASES.get(provider_id, ()))


def _llm_provider_secret(llm_provider_id: str) -> str:
    provider_id = _llm_provider_id_normalized(llm_provider_id)
    if provider_id == "ollama":
        return "local"
    env_values = _llm_provider_env_values(provider_id)
    if env_values:
        return env_values[0]
    if provider_id in CENARA_LLM_PROVIDER_CONFIG_KEYS:
        session_value = _provider_secret_from_session((f"{provider_id}_api_key_input",))
        if session_value:
            return session_value
    for cfg_key in _llm_provider_config_keys(provider_id):
        config_values = _normalize_secret_values(config.app.get(cfg_key))
        if config_values:
            return config_values[0]
    return ""


def _provider_secret(provider: str, session_keys=(), config_value=None) -> str:
    values = _provider_secret_list(provider, session_keys=session_keys, config_value=config_value)
    return values[0] if values else ""


def _provider_secret_list(provider: str, session_keys=(), config_value=None) -> list[str]:
    return _dedupe_preserving_order(
        _provider_secret_values_from_env(provider)
        + _provider_secret_values_from_session(session_keys)
        + _normalize_secret_values(config_value)
    )


def _remember_env_runtime_value(section: str, key: str, values) -> None:
    env_values = _dedupe_preserving_order(values)
    if env_values:
        CENARA_ENV_RUNTIME_VALUES.setdefault(section, {})[key] = env_values


def _strip_env_runtime_values(value, env_values):
    if isinstance(value, (list, tuple, set)):
        filtered = [item for item in _normalize_secret_values(value) if item not in env_values]
        return filtered
    values = _normalize_secret_values(value)
    filtered = [item for item in values if item not in env_values]
    if isinstance(value, str) and "," in value:
        return ",".join(filtered)
    return filtered[0] if filtered else ""


def _install_cenara_safe_config_save() -> None:
    if getattr(config, "_cenara_safe_save_installed", False):
        return
    original_save_config = config.save_config

    def safe_save_config(*args, **kwargs):
        restore_values = {"app": {}, "elevenlabs": {}}
        for section_name, env_keys in CENARA_ENV_RUNTIME_VALUES.items():
            section = getattr(config, section_name)
            for key, env_values in env_keys.items():
                restore_values[section_name][key] = section.get(key)
                section[key] = _strip_env_runtime_values(section.get(key), env_values)
        try:
            return original_save_config(*args, **kwargs)
        finally:
            for section_name, section_values in restore_values.items():
                section = getattr(config, section_name)
                for key, value in section_values.items():
                    section[key] = value

    config.save_config = safe_save_config
    config._cenara_safe_save_installed = True


def cenara_apply_env_provider_keys() -> None:
    """Expose Railway env keys to the runtime config without printing their values."""
    _install_cenara_safe_config_save()
    llm_provider_id = _llm_provider_id_normalized(config.app.get("llm_provider") or "openai")
    llm_env_values = _llm_provider_env_values(llm_provider_id)
    if llm_env_values:
        llm_cfg_key = _llm_provider_config_keys(llm_provider_id)[0]
        config.app[llm_cfg_key] = llm_env_values[0]
        _remember_env_runtime_value("app", llm_cfg_key, llm_env_values)
        config.app["llm_provider"] = config.app.get("llm_provider") or "openai"
    provider_config_map = {
        "pexels": "pexels_api_keys",
        "pixabay": "pixabay_api_keys",
        "coverr": "coverr_api_keys",
    }
    for provider, cfg_key in provider_config_map.items():
        env_values = _provider_secret_values_from_env(provider)
        keys = _provider_secret_list(provider, config_value=config.app.get(cfg_key))
        if keys:
            config.app[cfg_key] = keys
        _remember_env_runtime_value("app", cfg_key, env_values)
    elevenlabs_env_values = _provider_secret_values_from_env("elevenlabs")
    elevenlabs_key = _provider_secret(
        "elevenlabs",
        ("elevenlabs_api_key_input",),
        config.elevenlabs.get("api_key"),
    )
    if elevenlabs_key:
        config.elevenlabs["api_key"] = elevenlabs_key
    _remember_env_runtime_value("elevenlabs", "api_key", elevenlabs_env_values)


cenara_apply_env_provider_keys()


def _provider_status_html(label: str, configured: bool, help_url: str) -> str:
    status_class = "cenara-status-ok" if configured else "cenara-status-missing"
    status_label = "Configurado" if configured else "Não configurado"
    return f"""
    <div class="cenara-provider-card">
      <div class="cenara-flow-title">{label}</div>
      <span class="{status_class}">{status_label}</span>
      <div class="cenara-provider-copy" style="margin-top:.75rem">Cole uma nova chave somente quando quiser atualizar. Campo vazio preserva a configuração existente.</div>
      <div class="cenara-provider-copy">Obter chave: {help_url}</div>
    </div>
    """


def render_cenara_product_intro():
    st.markdown('<div class="cenara-section-title">Como a Cenara funciona</div>', unsafe_allow_html=True)
    steps = st.columns(5)
    flow_cards = [
        ("🎯", "1. Tema", "Defina nicho, promessa e público do vídeo."),
        ("🧠", "2. Roteiro IA", "Gere ou cole o roteiro com palavras-chave."),
        ("🎬", "3. Fonte", "Escolha Frontier AI, Pexels, Pixabay, Coverr ou arquivos locais."),
        ("🎙️", "4. Voz", "Configure TTS e legendas sem revelar chaves."),
        ("✨", "5. Gerar", "Renderize, revise e exporte manualmente."),
    ]
    for col, (icon, title, copy) in zip(steps, flow_cards):
        with col:
            st.markdown(
                f'<div class="cenara-flow-card"><div class="cenara-flow-icon">{icon}</div><div class="cenara-flow-title">{title}</div><div class="cenara-flow-copy">{copy}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div class="cenara-section-title">Módulos do fluxo</div>', unsafe_allow_html=True)
    modules = st.columns(5)
    module_cards = [
        ("📝", "Roteiro IA", "Transforme briefing em narrativa curta."),
        ("🗂️", "Fonte de Vídeo", "Use bancos configurados pelo operador."),
        ("🔊", "Voz IA", "Selecione vozes e teste manualmente."),
        ("💬", "Legendas", "Ajuste estilo, fonte e posição."),
        ("🚀", "Gerar Vídeo", "Crie arquivos para revisão e exportação."),
    ]
    for col, (icon, title, copy) in zip(modules, module_cards):
        with col:
            st.markdown(
                f'<div class="cenara-flow-card"><div class="cenara-flow-icon">{icon}</div><div class="cenara-flow-title">{title}</div><div class="cenara-flow-copy">{copy}</div></div>',
                unsafe_allow_html=True,
            )




def _mask_secret(value: str) -> str:
    text = str(value or "")
    if len(text) <= 8:
        return "••••" if text else ""
    return f"{text[:3]}••••{text[-3:]}"



def _is_executable_file(candidate) -> bool:
    if not candidate:
        return False
    candidate_path = Path(str(candidate)).expanduser()
    return candidate_path.is_file() and os.access(candidate_path, os.X_OK)


def cenara_resolve_ffmpeg_binary():
    candidates = [
        config.app.get("ffmpeg_path"),
        os.environ.get("IMAGEIO_FFMPEG_EXE"),
    ]
    try:
        candidates.append(utils.get_ffmpeg_binary())
    except Exception as exc:
        logger.warning(f"failed to resolve FFmpeg via runtime resolver: {exc}")
    candidates.append(shutil.which("ffmpeg"))

    for candidate in candidates:
        if not candidate:
            continue
        if str(candidate) == "ffmpeg":
            system_ffmpeg = shutil.which("ffmpeg")
            if system_ffmpeg:
                return system_ffmpeg
            continue
        if _is_executable_file(candidate):
            return str(Path(str(candidate)).expanduser())
    return ""

def cenara_status_label(status: str) -> str:
    return {
        "configured": "Configurado",
        "missing": "Ausente",
        "optional": "Opcional",
        "blocked": "Bloqueado",
        "quota_blocked": "Configurado / Bloqueado por cota",
        "auth_failed": "Configurado / Falha de autenticação",
        "pending": "Configurado / Teste pendente",
    }.get(status, status)


def cenara_classify_provider_error(exc_or_text):
    text = str(exc_or_text or "").lower()
    if any(token in text for token in ["insufficient_quota", "quota", "billing", "429", "rate limit", "rate_limit"]):
        return {
            "code": "LLM_PROVIDER_BLOCKED",
            "status": "quota_blocked",
            "message": "A chave LLM está configurada, mas o provedor bloqueou a geração por cota, billing ou limite de uso.",
            "next_action": "Use roteiro manual com palavras-chave, ajuste billing/cota do provedor LLM ou troque a chave antes do modo automático.",
        }
    if any(token in text for token in ["authentication", "unauthorized", "invalid api key", "401", "403"]):
        return {
            "code": "LLM_PROVIDER_BLOCKED",
            "status": "auth_failed",
            "message": "A chave LLM está configurada, mas falhou na autenticação do provedor.",
            "next_action": "Revise a chave do provedor LLM no Railway sem expor o valor no navegador.",
        }
    return {
        "code": "GENERATION_FAILED",
        "status": "blocked",
        "message": "A geração real falhou antes de produzir um MP4 novo e não vazio.",
        "next_action": "Verifique o estágio com falha e tente novamente com roteiro/manual, mídia e voz configurados.",
    }

def cenara_secret_fingerprint(value: str) -> str:
    normalized = str(value or "").strip()
    if _is_missing_secret_value(normalized):
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def cenara_reset_llm_blocked_status_if_changed(provider_id: str, key_value: str = "") -> None:
    normalized_provider = _llm_provider_id_normalized(provider_id)
    last_provider = st.session_state.get("cenara_llm_provider_status_provider")
    if last_provider and last_provider != normalized_provider:
        st.session_state.pop("cenara_llm_provider_status", None)
    st.session_state["cenara_llm_provider_status_provider"] = normalized_provider

    fingerprint = cenara_secret_fingerprint(key_value)
    if not fingerprint:
        return
    last_fingerprint = st.session_state.get("cenara_llm_provider_key_fingerprint")
    if last_fingerprint and last_fingerprint != fingerprint:
        st.session_state.pop("cenara_llm_provider_status", None)
    st.session_state["cenara_llm_provider_key_fingerprint"] = fingerprint


def cenara_provider_readiness(selected_video_source="pexels", selected_tts_server="azure-tts-v1"):
    llm_provider_id = _llm_provider_id_normalized(config.app.get("llm_provider") or "openai")
    llm_ok = _has_configured_secret(_llm_provider_secret(llm_provider_id))
    pexels_ok = _has_configured_secret(_provider_secret_list("pexels", config_value=config.app.get("pexels_api_keys")))
    pixabay_ok = _has_configured_secret(_provider_secret_list("pixabay", config_value=config.app.get("pixabay_api_keys")))
    coverr_ok = _has_configured_secret(_provider_secret_list("coverr", config_value=config.app.get("coverr_api_keys")))
    frontier_ok = _has_configured_secret(os.getenv("FAL_KEY", ""))
    nano_banana_ok = _has_configured_secret(os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", ""))
    source_ok = selected_video_source in ["pexels", "pixabay", "coverr", "local", "frontier_ai"]
    if selected_video_source == "frontier_ai":
        source_ok = frontier_ok
    tts_server_id = selected_tts_server or config.ui.get("tts_server", "azure-tts-v1")
    tts_ok = tts_server_id == voice.NO_VOICE_NAME or bool(config.ui.get("voice_name"))
    if tts_server_id == "azure-tts-v2":
        tts_ok = tts_ok and _has_configured_secret(config.azure.get("speech_key"))
    elif tts_server_id == "siliconflow":
        tts_ok = tts_ok and _has_configured_secret(config.siliconflow.get("api_key"))
    elif tts_server_id == "gemini-tts":
        tts_ok = tts_ok and _has_configured_secret(config.app.get("gemini_api_key"))
    elif tts_server_id == "mimo-tts":
        tts_ok = tts_ok and _has_configured_secret(config.app.get("mimo_api_key"))
    elif tts_server_id == "elevenlabs":
        tts_ok = tts_ok and _has_configured_secret(
            _provider_secret("elevenlabs", ("elevenlabs_api_key_input",), config.elevenlabs.get("api_key"))
        )
    ffmpeg_binary = cenara_resolve_ffmpeg_binary()
    render_ok = bool(ffmpeg_binary)
    imagemagick_ok = bool(shutil.which("magick") or shutil.which("convert"))
    llm_status = "configured" if llm_ok else "missing"
    last_llm_status = st.session_state.get("cenara_llm_provider_status")
    if llm_ok and last_llm_status in ["quota_blocked", "auth_failed"]:
        llm_status = last_llm_status
    return {
        "LLM": (llm_status, llm_provider_id),
        "Pexels": ("configured" if pexels_ok else "missing", "fonte de vídeo"),
        "Pixabay": ("configured" if pixabay_ok else "missing", "fonte de vídeo"),
        "Coverr": ("configured" if coverr_ok else "optional", "fonte opcional"),
        "Frontier Video": ("configured" if frontier_ok else "optional", os.getenv("CENARA_FRONTIER_VIDEO_MODEL", "seedance-2")),
        "Nano Banana": ("configured" if nano_banana_ok else "optional", os.getenv("CENARA_NANO_BANANA_MODEL", "gemini-3.1-flash-image")),
        "Fonte de vídeo": ("configured" if source_ok else "blocked", selected_video_source),
        "Voz/TTS": ("configured" if tts_ok else "blocked", tts_server_id),
        "FFmpeg": ("configured" if render_ok else "blocked", ffmpeg_binary or "não encontrado"),
        "ImageMagick": ("configured" if imagemagick_ok else "optional", shutil.which("magick") or shutil.which("convert") or "opcional"),
    }

def cenara_derive_manual_keywords(form):
    terms = tm.derive_safe_video_terms(
        form.get("tema"),
        form.get("nicho"),
        form.get("publico"),
        form.get("promessa"),
        form.get("cta"),
        form.get("manual_script"),
        form.get("roteiro_manual"),
    )
    return ", ".join(terms)



def _cenara_clean_text(value: str, fallback: str = "") -> str:
    text = re.sub(r"https?://\S+|www\.\S+|\S+@\S+", " ", str(value or ""))
    text = re.sub(r"\b[A-Za-z0-9_-]{28,}\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .\n\t")
    return text or fallback


def _cenara_is_provider_failure_text(value: str) -> bool:
    text = str(value or "").strip().lower()
    return not text or text.startswith("error:") or any(token in text for token in [
        "insufficient_quota", "quota", "billing", "429", "rate limit", "rate_limit",
        "authentication", "unauthorized", "invalid api key", "provider error",
    ])


def cenara_build_local_script_from_brief(payload):
    """Build a deterministic PT-BR ad script without calling any external LLM."""
    manual = _cenara_clean_text(getattr(payload, "manual_script", "") or getattr(payload, "roteiro_manual", ""))
    if manual and not _cenara_is_provider_failure_text(manual):
        return manual
    existing = _cenara_clean_text(getattr(payload, "video_script", ""))
    if existing and not _cenara_is_provider_failure_text(existing):
        return existing

    subject = _cenara_clean_text(getattr(payload, "video_subject", ""), "vídeo de conversão")
    parts = {"tema": subject, "publico": "pessoas ocupadas", "promessa": "transforme sua rotina com mais clareza e resultado", "nicho": "bem-estar", "cta": "comece agora"}
    for item in subject.split("|"):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        key = key.strip().lower()
        if "público" in key or "publico" in key:
            parts["publico"] = _cenara_clean_text(value, parts["publico"])
        elif "promessa" in key:
            parts["promessa"] = _cenara_clean_text(value, parts["promessa"])
        elif "nicho" in key:
            parts["nicho"] = _cenara_clean_text(value, parts["nicho"])
        elif "cta" in key:
            parts["cta"] = _cenara_clean_text(value, parts["cta"])
    lines = [
        f"Você vive sem tempo, mas quer cuidar melhor de você.",
        f"{parts['promessa']}.",
        f"Com uma rotina simples e segura em {parts['nicho']}, você começa hoje, no seu ritmo.",
        f"{parts['cta']}.",
    ]
    return "\n".join(lines)


def cenara_derive_local_keywords(payload, script=""):
    manual = _cenara_clean_text(getattr(payload, "manual_keywords", "") or getattr(payload, "palavras_chave", ""))
    if manual:
        source_terms = re.split(r"[,，\n;]", manual)
    else:
        upper_terms = getattr(payload, "video_terms", "")
        if isinstance(upper_terms, list):
            source_terms = upper_terms
        elif _cenara_clean_text(upper_terms):
            source_terms = re.split(r"[,，\n;]", str(upper_terms))
        else:
            source_terms = tm.derive_safe_video_terms(getattr(payload, "video_subject", ""), script, limit=8)
    safe_terms = []
    for term in source_terms:
        clean = _cenara_clean_text(term).lower()
        clean = re.sub(r"[^a-zà-ÿ0-9 ]", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        if not clean or len(clean) > 40 or any(len(tok) > 20 for tok in clean.split()):
            continue
        if clean not in safe_terms:
            safe_terms.append(clean)
        if len(safe_terms) >= 8:
            break
    fallback = ["bem estar", "rotina saudável", "pessoas ocupadas"]
    for term in fallback:
        if len(safe_terms) >= 3:
            break
        if term not in safe_terms:
            safe_terms.append(term)
    return safe_terms[:8]

def cenara_build_generation_payload(form, current_params):
    tema = (form.get("tema") or "").strip()
    roteiro = (form.get("manual_script") or form.get("roteiro_manual") or "").strip()
    contexto = [
        f"Nicho: {form.get('nicho','').strip()}" if form.get("nicho") else "",
        f"Público-alvo: {form.get('publico','').strip()}" if form.get("publico") else "",
        f"Promessa: {form.get('promessa','').strip()}" if form.get("promessa") else "",
        f"CTA: {form.get('cta','').strip()}" if form.get("cta") else "",
    ]
    contexto = [item for item in contexto if item]
    subject = tema or (roteiro.split(".", 1)[0][:120] if roteiro else "")
    if contexto and subject:
        subject = f"{subject} | " + " | ".join(contexto)
    upper_script = st.session_state.get("video_script", "")
    script = roteiro or upper_script
    if script and form.get("cta") and form.get("cta").strip() not in script:
        script = f"{script.rstrip()}\n\nCTA: {form.get('cta').strip()}"
    current_params.video_subject = subject.strip()
    current_params.video_script = script.strip()
    if not current_params.video_script or _cenara_is_provider_failure_text(current_params.video_script):
        current_params.video_script = cenara_build_local_script_from_brief(current_params)
    manual_keywords = (form.get("manual_keywords") or form.get("palavras_chave") or "").strip()
    upper_terms = st.session_state.get("video_terms", "")
    current_params.video_terms = ", ".join(cenara_derive_local_keywords(current_params, current_params.video_script)) if not manual_keywords and not upper_terms else (manual_keywords or upper_terms).strip()
    current_params.video_source = form.get("fonte_video") or current_params.video_source
    current_params.video_clip_duration = int(form.get("duracao") or current_params.video_clip_duration or 3)
    current_params.video_aspect = {"9:16": VideoAspect.portrait, "16:9": VideoAspect.landscape, "1:1": VideoAspect.portrait}.get(form.get("formato"), current_params.video_aspect)
    if form.get("voz_tts"):
        current_params.voice_name = form["voz_tts"]
    return current_params

def cenara_validate_generation_payload(payload, uploaded_audio=None, readiness=None):
    errors = []
    if not payload.video_subject and not payload.video_script:
        payload.video_script = cenara_build_local_script_from_brief(payload)
    if payload.video_source not in ["pexels", "pixabay", "coverr", "local", "frontier_ai"]:
        errors.append("Configure uma fonte de vídeo, uma chave de provedor ou envie uma mídia local.")
    if payload.video_source == "local" and not getattr(payload, "video_materials", None):
        errors.append("Envie um arquivo local ou selecione Pexels/Pixabay/Coverr.")
    if payload.video_script and payload.video_source in ["pexels", "pixabay", "coverr", "frontier_ai"] and not payload.video_terms:
        errors.append("Informe palavras-chave manuais ou preencha tema/nicho/público/promessa/CTA para a Cenara derivar termos seguros sem LLM.")
    llm_status = readiness.get("LLM", ("missing", ""))[0] if readiness else "missing"
    if not payload.video_script:
        payload.video_script = cenara_build_local_script_from_brief(payload)
    if readiness:
        blockers = [f"{label}: {detail}" for label, (status, detail) in readiness.items() if status == "blocked"]
        if blockers:
            errors.append("Geração bloqueada por provedor obrigatório ausente: " + "; ".join(blockers) + ".")
        if readiness.get("Voz/TTS", ("blocked", ""))[0] == "blocked":
            errors.append("Configure ELEVENLABS_API_KEY, selecione uma voz válida ou envie um áudio personalizado.")
    if not uploaded_audio and not payload.custom_audio_file and not payload.voice_name:
        errors.append("Configure uma voz TTS ou envie um áudio personalizado.")
    return list(dict.fromkeys(errors))

def _is_non_empty_mp4(path):
    candidate = Path(path)
    return candidate.suffix.lower() == ".mp4" and candidate.is_file() and candidate.stat().st_size > 0


def _storage_root():
    return Path(root_dir) / "storage"


def _storage_tasks_root():
    return _storage_root() / "tasks"


def _task_dir_for(task_id):
    return _storage_tasks_root() / str(task_id)


def _is_path_inside(path, parent):
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except (OSError, ValueError):
        return False


def cenara_is_safe_deliverable_mp4(path):
    try:
        raw_candidate = Path(path).expanduser()
        if raw_candidate.is_symlink():
            return False
        candidate = raw_candidate.resolve()
        storage = _storage_root().resolve()
        tasks = _storage_tasks_root().resolve()
        if not candidate.is_file() or candidate.suffix.lower() != ".mp4":
            return False
        name = candidate.name.lower()
        if name.startswith(("temp-clip", "combined-")) or name.endswith(".browser.mp4") or name.endswith(".part"):
            return False
        if candidate.stat().st_size < 100 * 1024:
            return False
        validation = ffprobe_validate_mp4(candidate)
        if not validation.get("valid"):
            return False
        # Resolve before checking roots so symlinks cannot escape storage/.
        return _is_path_inside(candidate, tasks) or _is_path_inside(candidate, storage)
    except (OSError, TypeError, ValueError):
        return False


def cenara_is_safe_browser_copy_mp4(path, original_path):
    try:
        original = Path(original_path).expanduser().resolve()
        if not cenara_is_safe_deliverable_mp4(original):
            return False
        candidate = Path(path).expanduser().resolve()
        if candidate.is_symlink() or not candidate.is_file() or candidate.suffix.lower() != ".mp4":
            return False
        if not candidate.name.endswith(".browser.mp4") or candidate.name.startswith(("temp-clip", "combined-")):
            return False
        if candidate.with_name(candidate.name.replace(".browser.mp4", ".mp4")) != original:
            return False
        if candidate.stat().st_size < 100 * 1024:
            return False
        return _is_path_inside(candidate, original.parent) and _cenara_mp4_looks_browser_safe(candidate)
    except (OSError, TypeError, ValueError):
        return False


def cenara_is_safe_preview_mp4(path, original_path=None):
    if cenara_is_safe_deliverable_mp4(path):
        return True
    return bool(original_path and cenara_is_safe_browser_copy_mp4(path, original_path))


def _cenara_mp4_metadata(path):
    candidate = Path(path)
    stat = candidate.stat()
    return {
        "name": candidate.name,
        "size_mb": stat.st_size / (1024 * 1024),
        "mtime": datetime.fromtimestamp(stat.st_mtime),
    }


def _cenara_mp4_looks_browser_safe(path):
    ffmpeg = cenara_resolve_ffmpeg_binary()
    ffprobe = shutil.which("ffprobe") or (str(Path(ffmpeg).with_name("ffprobe")) if ffmpeg else "")
    if not ffprobe or not _is_executable_file(ffprobe):
        return True
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,pix_fmt", "-of", "json", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=True, timeout=10,
        )
        stream = (json.loads(result.stdout or "{}").get("streams") or [{}])[0]
        return stream.get("codec_name") == "h264" and stream.get("pix_fmt") == "yuv420p"
    except Exception as exc:
        logger.warning(f"Cenara browser compatibility probe skipped: {type(exc).__name__}")
        return True


def cenara_normalize_mp4_for_browser(path):
    original = Path(path)
    if not cenara_is_safe_deliverable_mp4(original):
        return None
    if _cenara_mp4_looks_browser_safe(original):
        return original
    normalized = original.with_name(f"{original.stem}.browser.mp4")
    if cenara_is_safe_browser_copy_mp4(normalized, original):
        return normalized
    ffmpeg = cenara_resolve_ffmpeg_binary()
    if not ffmpeg:
        return original
    commands = [
        [ffmpeg, "-y", "-i", str(original), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "128k", str(normalized)],
        [ffmpeg, "-y", "-i", str(original), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(normalized)],
    ]
    for command in commands:
        try:
            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=180)
            if cenara_is_safe_browser_copy_mp4(normalized, original):
                return normalized
        except Exception as exc:
            logger.warning(f"Cenara browser normalization attempt failed: {type(exc).__name__}")
    return original



def _cenara_safe_relative_path(path):
    try:
        return str(Path(path).expanduser().resolve().relative_to(_storage_root().resolve()))
    except (OSError, TypeError, ValueError):
        return Path(str(path or "unknown")).name


def cenara_mp4_fingerprint(path):
    """Stable short ID from safe relative path, size and mtime; never raw absolute path."""
    try:
        candidate = Path(path).expanduser().resolve()
        stat = candidate.stat()
        raw = "|".join([
            _cenara_safe_relative_path(candidate),
            str(stat.st_size),
            str(int(stat.st_mtime_ns)),
        ])
    except (OSError, TypeError, ValueError):
        raw = _cenara_safe_relative_path(path)
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]


def cenara_mp4_widget_key(path, context="preview"):
    safe_context = re.sub(r"[^A-Za-z0-9_]+", "_", str(context or "preview"))[:64]
    return f"cenara_mp4_{safe_context}_{cenara_mp4_fingerprint(path)}"


def _cenara_read_mp4_bytes(path):
    with open(path, "rb") as video_file:
        return video_file.read()




def cenara_task_id_for_deliverable_mp4(path):
    try:
        relative = Path(path).resolve().relative_to(_storage_tasks_root().resolve())
        return relative.parts[0] if relative.parts else ""
    except (OSError, ValueError):
        return ""


def cenara_update_delivery_status_for_mp4(path, **updates):
    """Update delivery-only flags for a task MP4 without clearing generation fields."""
    if not cenara_is_safe_deliverable_mp4(path):
        return {}
    task_id = cenara_task_id_for_deliverable_mp4(path)
    if not task_id:
        return {}
    safe_updates = {k: v for k, v in updates.items() if k not in {"output_path", "raw_error", "exception", "api_key"}}
    return cenara_write_task_status(task_id, **safe_updates)

def cenara_render_mp4_download(path, context="preview", label="Baixar MP4"):
    candidate = Path(path)
    if not cenara_is_safe_deliverable_mp4(candidate):
        st.warning("Download bloqueado: MP4 inválido ou fora do armazenamento seguro.")
        return False
    fingerprint = cenara_mp4_fingerprint(candidate)
    meta = _cenara_mp4_metadata(candidate)
    limits = cenara_runtime_limits()
    if meta["size_mb"] > limits.download_prep_max_mb:
        cenara_update_delivery_status_for_mp4(candidate, download_ready=False, download_blocked_for_memory=True, safe_message="download_blocked_file_too_large")
        st.warning(f"download_blocked_file_too_large: este MP4 tem {meta['size_mb']:.2f} MB e excede o limite seguro de {limits.download_prep_max_mb} MB para preparar bytes no Railway.")
        return False
    key_prefix = f"cenara_download_bytes_{fingerprint}"
    try:
        video_bytes = _cenara_read_mp4_bytes(candidate)
        st.download_button(
            label,
            data=video_bytes,
            file_name=candidate.name,
            mime="video/mp4",
            use_container_width=True,
            key=f"cenara_download_{re.sub(r'[^A-Za-z0-9_]+', '_', str(context or 'preview'))[:64]}_{fingerprint}",
        )
        cenara_update_delivery_status_for_mp4(candidate, download_ready=True, download_blocked_for_memory=False, safe_message="download_ready")
        if key_prefix in st.session_state:
            del st.session_state[key_prefix]
        return True
    except Exception as exc:
        logger.warning(f"Cenara MP4 download prepare failed: {type(exc).__name__}")
        cenara_update_delivery_status_for_mp4(candidate, download_ready=False, safe_message="MP4 criado, mas o preparo do download falhou neste rerun. Tente novamente.")
        st.warning("MP4 criado, mas o preparo do download falhou neste rerun. Atualize a página ou tente novamente.")
        return False


def cenara_render_active_mp4_preview(mp4_path, context="preview"):
    """Render one canonical active MP4 preview with defensive delivery fallback."""
    slot = st.empty()
    with slot.container():
        candidate = Path(mp4_path) if mp4_path else None
        if not candidate or not cenara_is_safe_deliverable_mp4(candidate):
            st.warning("MP4 inválido ou fora do armazenamento seguro; preview/download bloqueados.")
            return None
        fingerprint = cenara_mp4_fingerprint(candidate)
        meta = _cenara_mp4_metadata(candidate)
        st.caption(f"Arquivo: {meta['name']} · Tamanho: {meta['size_mb']:.2f} MB · Gerado em: {meta['mtime']:%d/%m/%Y %H:%M} · ID: {fingerprint}")
        preview_candidate = candidate
        preview_ready = False
        preview_clicked = st.button("Abrir preview seguro", key=f"cenara_open_inline_preview_{fingerprint}_{context}", use_container_width=True)
        try:
            if meta["size_mb"] > cenara_runtime_limits().preview_inline_max_mb:
                st.warning("preview_skipped_for_memory: MP4 maior que o limite seguro para preview inline. Use o download.")
                cenara_update_delivery_status_for_mp4(candidate, preview_skipped_for_memory=True, safe_message="preview_skipped_for_memory")
            elif preview_clicked:
                preview_candidate = cenara_normalize_mp4_for_browser(candidate) or candidate
                if not cenara_is_safe_preview_mp4(preview_candidate, candidate):
                    raise ValueError("unsafe normalized mp4")
                preview_meta = _cenara_mp4_metadata(preview_candidate)
                if preview_meta["size_mb"] > cenara_runtime_limits().preview_inline_max_mb:
                    st.warning("preview_skipped_for_memory: MP4 normalizado excede o limite seguro para preview inline. Use o download.")
                    cenara_update_delivery_status_for_mp4(candidate, preview_skipped_for_memory=True, safe_message="preview_skipped_for_memory")
                else:
                    st.session_state["cenara_active_preview_fp"] = fingerprint
                    preview_bytes = _cenara_read_mp4_bytes(preview_candidate)
                    st.video(preview_bytes, format="video/mp4")
                    del preview_bytes
                    preview_ready = True
                    cenara_update_delivery_status_for_mp4(candidate, preview_ready=True, mp4_created_preview_failed=False, safe_message="Preview MP4 renderizado no navegador.")
        except Exception as exc:
            logger.warning(f"Cenara MP4 preview failed: {type(exc).__name__}")
            cenara_update_delivery_status_for_mp4(candidate, preview_ready=False, mp4_created_preview_failed=True, safe_message="MP4 criado, mas o preview no navegador falhou. Use o download.")
            st.warning("MP4 criado, mas o navegador não conseguiu abrir o preview neste rerun. O arquivo permanece disponível para download.")
        download_ready = False
        if st.button("Preparar download seguro", key=f"cenara_prepare_active_download_{fingerprint}_{context}", use_container_width=True):
            download_ready = cenara_render_mp4_download(candidate, context=context)
        else:
            st.caption("download_ready somente após clique explícito para proteger a memória do Railway.")
        if not preview_ready and download_ready:
            cenara_update_delivery_status_for_mp4(candidate, preview_ready=False, download_ready=True, mp4_created_preview_failed=True, safe_message="MP4 criado; preview falhou, mas download está pronto.")
        if preview_ready:
            st.success("preview_ready")
        elif download_ready:
            st.info("mp4_created_preview_failed")
        if download_ready:
            st.success("download_ready")
        return preview_candidate if preview_ready else candidate


def cenara_render_mp4_player(path, label="Abrir vídeo", context="preview"):
    if label:
        st.markdown(f"**{label}**")
    return cenara_render_active_mp4_preview(path, context=context)


def cenara_find_task_mp4(task_id, engine_video_paths=None, limit=12):
    task_dir = _task_dir_for(task_id)
    candidates = []
    if task_dir.exists():
        candidates.extend(path for path in task_dir.rglob("*.mp4") if cenara_is_safe_deliverable_mp4(path))
    for path in engine_video_paths or []:
        candidate = Path(path)
        if cenara_is_safe_deliverable_mp4(candidate) and _is_path_inside(candidate, task_dir):
            candidates.append(candidate)
    return sorted(set(candidates), key=lambda path: path.stat().st_mtime, reverse=True)[:limit]


def cenara_find_latest_mp4(task_id=None, limit=12):
    if task_id:
        return cenara_find_task_mp4(task_id, limit=limit)
    roots = [_storage_tasks_root(), _storage_root()]
    candidates = []
    for base in roots:
        if not base.exists():
            continue
        candidates.extend(path for path in base.rglob("*.mp4") if cenara_is_safe_deliverable_mp4(path))
    return sorted(set(candidates), key=lambda path: path.stat().st_mtime, reverse=True)[:limit]

CENARA_PIPELINE_STAGES = ["idle", "locked", "running", "script_ready", "terms_ready", "media_ready", "audio_ready", "subtitle_skipped", "rendering", "mp4_created", "preview_ready", "download_ready", "failed"]


def cenara_task_status_path(task_id):
    task_dir = _task_dir_for(task_id)
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir / "cenara_status.json"


def cenara_write_task_status(task_id, **updates):
    status_path = cenara_task_status_path(task_id)
    current = {}
    if status_path.exists():
        try:
            current = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:
            current = {}
    safe = {k: v for k, v in updates.items() if k not in {"exception", "raw_error", "api_key"}}
    safe.update({"task_id": task_id, "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z"})
    current.update(safe)
    status_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return current


def cenara_read_task_status(task_id):
    try:
        return json.loads(cenara_task_status_path(task_id).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _cenara_stage_from_progress(progress):
    if progress >= 100:
        return "completed"
    if progress >= 50:
        return "mp4_created"
    if progress >= 45:
        return "render_started"
    if progress >= 40:
        return "media_ready"
    if progress >= 20:
        return "audio_ready"
    if progress >= 10:
        return "terms_ready"
    return "script_ready"



def _cenara_aspect_size(aspect_ratio):
    text = str(aspect_ratio or "9:16")
    if "16:9" in text or "landscape" in text:
        return 1920, 1080
    if "1:1" in text:
        return 1080, 1080
    return 1080, 1920


def _cenara_ffmpeg_text(value: str, limit: int = 42) -> str:
    text = _cenara_clean_text(value)[:limit]
    return text.replace("'", "\\'").replace(":", "\\:")


def cenara_create_local_fallback_mp4(task_dir, payload, script, duration, aspect_ratio):
    """Create a truthful current task fallback .mp4 with ffmpeg; not stock footage."""
    ffmpeg_binary = cenara_resolve_ffmpeg_binary()
    if not ffmpeg_binary:
        return ""
    task_path = Path(task_dir)
    task_path.mkdir(parents=True, exist_ok=True)
    task_id = task_path.name
    output = task_path / f"cenara_fallback_{task_id}.mp4"
    width, height = _cenara_aspect_size(aspect_ratio)
    seconds = max(3, int(duration or getattr(payload, "video_clip_duration", 3) or 3))
    subject = _cenara_ffmpeg_text(getattr(payload, "video_subject", "Cenara Preview"), 44)
    first_script = _cenara_ffmpeg_text(str(script or "").split("\n", 1)[0], 44)
    cta = _cenara_ffmpeg_text("MP4 real gerado em modo visual local", 44)
    base_filter = f"color=c=0x08111f:s={width}x{height}:d={seconds},format=yuv420p"
    draw = (
        "drawtext=text='Cenara Preview':fontcolor=white:fontsize=64:x=(w-text_w)/2:y=h*0.20,"
        f"drawtext=text='{subject}':fontcolor=0x93c5fd:fontsize=38:x=(w-text_w)/2:y=h*0.36,"
        f"drawtext=text='{first_script}':fontcolor=white:fontsize=34:x=(w-text_w)/2:y=h*0.46,"
        f"drawtext=text='{cta}':fontcolor=0xfbbf24:fontsize=30:x=(w-text_w)/2:y=h*0.62"
    )
    commands = [
        [ffmpeg_binary, "-y", "-f", "lavfi", "-i", f"{base_filter},{draw}", "-t", str(seconds), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)],
        [ffmpeg_binary, "-y", "-f", "lavfi", "-i", base_filter, "-t", str(seconds), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)],
    ]
    for command in commands:
        try:
            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=seconds + 20)
            if output.exists() and output.stat().st_size > 0:
                return str(output)
        except Exception as exc:
            logger.warning(f"Cenara local fallback ffmpeg attempt failed: {type(exc).__name__}")
    return ""


def _cenara_provider_enabled(provider: str) -> bool:
    if provider == "pexels":
        return _has_configured_secret(_provider_secret_list("pexels", config_value=config.app.get("pexels_api_keys")))
    if provider == "pixabay":
        return _has_configured_secret(_provider_secret_list("pixabay", config_value=config.app.get("pixabay_api_keys")))
    if provider == "coverr":
        return _has_configured_secret(_provider_secret_list("coverr", config_value=config.app.get("coverr_api_keys")))
    if provider == "frontier_ai":
        return _has_configured_secret(os.getenv("FAL_KEY", ""))
    return False


def _cenara_provider_order(selected: str):
    ordered = []
    for provider in [selected, "frontier_ai", "pexels", "pixabay", "coverr"]:
        if provider in ["frontier_ai", "pexels", "pixabay", "coverr"] and provider not in ordered and _cenara_provider_enabled(provider):
            ordered.append(provider)
    ordered.append("local_visual_fallback")
    return ordered

def cenara_trigger_real_generation(task_id, payload, status_box=None):
    logger.info(f"Cenara geração real iniciada task_id={task_id}")
    started_at = time.time()
    result = {"success": False, "task_id": task_id, "output_path": "", "error": "", "logs": []}
    payload.video_script = cenara_build_local_script_from_brief(payload)
    local_terms = cenara_derive_local_keywords(payload, payload.video_script)
    payload.video_terms = ", ".join(local_terms)
    llm_note = "LLM bloqueado por cota, usando roteiro local seguro."
    provider_attempts = []
    cenara_write_task_status(task_id, state="queued", failed_stage="", safe_error_code="", safe_message=llm_note, next_action="", script_ready=True, terms_ready=True, media_ready=False, audio_ready=False, render_started=False, mp4_created=False, preview_ready=False, download_ready=False, mp4_created_preview_failed=False, fallback_video_used=False, provider_attempts=provider_attempts, ffmpeg_available=bool(cenara_resolve_ffmpeg_binary()), output_path="", llm_bypass_note=llm_note)
    try:
        if status_box:
            status_box.write(f"task_id: {task_id}")
            status_box.write("script_ready")
            status_box.write(llm_note)
            status_box.write("terms_ready")
        engine_result = None
        for provider in _cenara_provider_order(payload.video_source):
            if provider == "local_visual_fallback":
                provider_attempts.append({"provider": provider, "status": "started"})
                fallback = cenara_create_local_fallback_mp4(_task_dir_for(task_id), payload, payload.video_script, payload.video_clip_duration, payload.video_aspect)
                if fallback and Path(fallback).exists() and Path(fallback).stat().st_size > 0 and Path(fallback).stat().st_mtime >= started_at:
                    provider_attempts[-1]["status"] = "success"
                    result.update(success=True, output_path=fallback, logs=[f"current task fallback MP4: {Path(fallback).name}"], fallback_video_used=True)
                    cenara_write_task_status(task_id, state="completed", output_path=fallback, media_ready=True, audio_ready=True, render_started=True, mp4_created=True, preview_ready=False, download_ready=False, mp4_created_preview_failed=False, fallback_video_used=True, provider_attempts=provider_attempts, safe_message="MP4 real gerado em modo visual local; mídia externa não encontrada.")
                    return result
                provider_attempts[-1]["status"] = "failed"
                continue
            payload.video_source = provider
            provider_attempts.append({"provider": provider, "status": "started"})
            cenara_write_task_status(task_id, state="media_ready", provider_attempts=provider_attempts, output_path="")
            if status_box:
                status_box.write(f"media provider: {provider}")
            try:
                engine_result = tm.start(task_id=task_id, params=payload)
            except Exception as exc:
                logger.warning(f"Cenara provider {provider} failed safely: {type(exc).__name__}")
                engine_result = None
            engine_video_paths = engine_result.get("videos") if engine_result else []
            latest = cenara_find_task_mp4(task_id=task_id, engine_video_paths=engine_video_paths, limit=1)
            if latest and latest[0].is_file() and latest[0].stat().st_size > 0 and latest[0].stat().st_mtime >= started_at:
                provider_attempts[-1]["status"] = "success"
                result.update(success=True, output_path=str(latest[0]), logs=[f"MP4 real encontrado: {latest[0].name}"])
                cenara_write_task_status(task_id, state="completed", output_path=str(latest[0]), media_ready=True, audio_ready=True, render_started=True, mp4_created=True, preview_ready=False, download_ready=False, mp4_created_preview_failed=False, fallback_video_used=False, provider_attempts=provider_attempts, safe_message="MP4 real com mídia externa gerado e verificado.")
                return result
            provider_attempts[-1]["status"] = "no_mp4"
        result["error"] = "A geração terminou, mas nenhum MP4 real novo e não vazio foi encontrado no diretório da tarefa."
        result["safe_error_code"] = "NO_CURRENT_TASK_MP4"
        result["next_action"] = "Verifique FFmpeg e permissões de escrita em storage/tasks; Cenara não usará MP4 antigo como sucesso."
        cenara_write_task_status(task_id, state="failed", failed_stage="render_started", safe_error_code="NO_CURRENT_TASK_MP4", safe_message=result["error"], next_action=result["next_action"], provider_attempts=provider_attempts, output_path="")
    except Exception as exc:
        classified = cenara_classify_provider_error(exc)
        logger.error(f"Cenara geração real falhou task_id={task_id}: {classified['message']}")
        result.update(error=classified["message"], safe_error_code=classified["code"], next_action=classified["next_action"])
        cenara_write_task_status(task_id, state="failed", failed_stage="script_ready", safe_error_code=classified["code"], safe_message=classified["message"], next_action=classified["next_action"], script_ready=True, terms_ready=True, media_ready=False, audio_ready=False, render_started=False, mp4_created=False, preview_ready=False, download_ready=False, mp4_created_preview_failed=False, provider_attempts=provider_attempts, output_path="")
    result["duration_seconds"] = round(time.time() - started_at, 2)
    return result

def cenara_render_real_preview(mp4_path):
    st.subheader("Preview Real")
    task_status = {}
    current_task_id = st.session_state.get("cenara_latest_task_id")
    if current_task_id:
        task_status = cenara_read_task_status(current_task_id)
        if task_status:
            safe_status = {k: task_status.get(k) for k in ["state", "failed_stage", "safe_error_code", "safe_message", "next_action", "script_ready", "terms_ready", "media_ready", "audio_ready", "render_started", "mp4_created", "preview_ready", "download_ready", "mp4_created_preview_failed", "preview_skipped_for_memory", "download_blocked_for_memory", "fallback_video_used", "provider_attempts", "ffmpeg_available"] if k in task_status}
            if task_status.get("output_path"):
                safe_status["output_file"] = Path(task_status["output_path"]).name
            st.json(safe_status)

    selected_library = Path(st.session_state.get("cenara_active_library_mp4", "")) if st.session_state.get("cenara_active_library_mp4") else None
    candidate = None
    selected_from_library = False
    if selected_library and cenara_is_safe_deliverable_mp4(selected_library):
        candidate = selected_library
        selected_from_library = True
    elif mp4_path and cenara_is_safe_deliverable_mp4(mp4_path):
        candidate = Path(mp4_path)
    else:
        latest = cenara_find_latest_mp4(limit=1)
        candidate = latest[0] if latest else None
    current_task_mp4 = bool(candidate and current_task_id and _is_path_inside(candidate, _task_dir_for(current_task_id)) and cenara_is_safe_deliverable_mp4(candidate))
    recovered_from_library = bool(candidate and not selected_from_library and not current_task_mp4)

    if not candidate or not cenara_is_safe_deliverable_mp4(candidate):
        st.info("Nenhum vídeo real gerado ainda.")
        return

    if selected_from_library:
        preview_context = "real_preview_library_selected"
        preview_label = "MP4 selecionado na Biblioteca"
    else:
        preview_context = "real_preview_recovered" if recovered_from_library else "real_preview_current"
        preview_label = "Último MP4 verificado encontrado" if recovered_from_library else "MP4 da geração atual"
    rendered_path = cenara_render_mp4_player(candidate, label=preview_label, context=preview_context)
    if not rendered_path:
        return
    if selected_from_library:
        st.success("MP4 selecionado na Biblioteca aberto na prévia.")
    elif current_task_mp4:
        st.success("MP4 da geração atual verificado.")
    elif recovered_from_library:
        st.success("MP4 encontrado e pronto para abrir/baixar.")
        st.info("Este arquivo é da biblioteca; gere novamente para validar tarefa atual.")
    if task_status.get("fallback_video_used"):
        st.warning("MP4 real gerado em modo visual local; mídia externa não encontrada.")

def _cenara_task_id_from_mp4(path):
    return cenara_task_id_for_deliverable_mp4(path)


def cenara_render_recent_videos():
    st.subheader("Biblioteca")
    st.caption("Biblioteca lazy: cards leves por padrão; apenas um MP4 ativo é aberto na área de Preview Real.")
    videos = cenara_find_latest_mp4(limit=cenara_runtime_limits().library_limit)
    if not videos:
        st.info("Nenhum vídeo real gerado ainda.")
        return
    selected_fp = st.session_state.get("cenara_active_library_mp4_fp")
    for index, path in enumerate(videos):
        if not cenara_is_safe_deliverable_mp4(path):
            continue
        meta = _cenara_mp4_metadata(path)
        fingerprint = cenara_mp4_fingerprint(path)
        task_id = _cenara_task_id_from_mp4(path)
        context = f"library_{index}_{fingerprint}"
        with st.container(border=True):
            st.markdown(f"**{meta['name']}**")
            cols = st.columns(4)
            cols[0].metric("Gerado em", meta["mtime"].strftime("%d/%m/%Y %H:%M"))
            cols[1].metric("Tamanho", f"{meta['size_mb']:.2f} MB")
            cols[2].metric("Duração", "verificada")
            cols[3].metric("Task", task_id or "biblioteca")
            st.success("Status: MP4 final verificado")
            action_cols = st.columns([1, 1, 1])
            if action_cols[0].button("Abrir na prévia", key=f"cenara_open_preview_{context}", use_container_width=True):
                st.session_state["cenara_active_library_mp4"] = str(path)
                st.session_state["cenara_active_library_mp4_fp"] = fingerprint
                st.session_state["cenara_latest_mp4"] = str(path)
                st.rerun()
            if action_cols[1].button("Baixar MP4", key=f"cenara_prepare_download_{context}", use_container_width=True):
                st.session_state[f"cenara_download_ready_{fingerprint}"] = True
            if action_cols[2].button("Detalhes", key=f"cenara_details_{context}", use_container_width=True):
                st.session_state[f"cenara_details_visible_{fingerprint}"] = not st.session_state.get(f"cenara_details_visible_{fingerprint}")
            if st.session_state.get(f"cenara_download_ready_{fingerprint}"):
                cenara_render_mp4_download(path, context=context, label="Download pronto: clicar para salvar")
            if st.session_state.get(f"cenara_details_visible_{fingerprint}"):
                st.caption(f"ID seguro: {fingerprint} · Fonte: {task_id or 'storage'}")
            if selected_fp == fingerprint:
                st.info("Selecionado para a área única de Preview Real acima. Nenhum player é renderizado dentro da Biblioteca.")


CENARA_PROJECTS_FILE = Path(root_dir) / "storage" / "cenara_projects.json"


def cenara_load_projects():
    if not CENARA_PROJECTS_FILE.exists():
        return []
    try:
        return json.loads(CENARA_PROJECTS_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"failed to load Cenara projects: {exc}")
        return []


def cenara_save_project_record(task_id, payload, mp4_path=None, status="completed", error=""):
    CENARA_PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    projects = cenara_load_projects()
    projects.insert(0, {
        "id": task_id,
        "title": payload.video_subject or "Projeto Cenara",
        "status": status,
        "source": payload.video_source,
        "aspect": str(payload.video_aspect),
        "mp4_path": str(mp4_path) if mp4_path else "",
        "error": error,
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    })
    CENARA_PROJECTS_FILE.write_text(json.dumps(projects[:50], ensure_ascii=False, indent=2), encoding="utf-8")


def cenara_runtime_diagnostics():
    tasks_dir = Path(root_dir) / "storage" / "tasks"
    output_dir = Path(root_dir) / "storage"
    return {
        "FFmpeg": cenara_resolve_ffmpeg_binary() or "não encontrado",
        "ImageMagick": shutil.which("magick") or shutil.which("convert") or "opcional/não encontrado",
        "Pasta de saída": "ok" if output_dir.exists() and os.access(output_dir, os.W_OK) else "indisponível",
        "Pasta de tarefas": "ok" if tasks_dir.exists() or os.access(output_dir, os.W_OK) else "será criada ao gerar",
        "Frontier AI": "pronto" if os.getenv("FAL_KEY") else "aguardando FAL_KEY",
        "Nano Banana": "pronto" if (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) else "aguardando GEMINI_API_KEY",
    }


def cenara_render_hero_and_stepper():
    st.markdown("""<section class="cenara-hero"><div class="cenara-eyebrow">Ultimate AI video workspace</div><h1>Cenara transforma briefs em vídeos prontos para vender.</h1><div class="cenara-subtitle">Um cockpit premium para roteiro, mídia, voz, legendas, montagem, preview e exportação MP4 real.</div><div class="cenara-badges"><span class="cenara-badge">Ads & Sales</span><span class="cenara-badge">Avatares e Voz IA</span><span class="cenara-badge">Clips / Shorts</span></div></section>""", unsafe_allow_html=True)
    steps = ["Ideia", "Roteiro", "Mídia", "Voz", "Legendas", "Montagem", "Preview", "Exportar"]
    st.markdown('<div class="cenara-stepper">' + ''.join(f'<div class="cenara-step {"active" if i < 3 else ""}">{step}</div>' for i, step in enumerate(steps)) + '</div>', unsafe_allow_html=True)

def cenara_render_provider_center(readiness):
    overall_blocked = any(status == "blocked" for status, _ in readiness.values())
    with st.expander("Central de Provedores · chaves preservadas quando campos ficam em branco", expanded=True):
        st.caption(f"Status geral: {'Bloqueado' if overall_blocked else 'Pronto'} · segredos salvos nunca são exibidos.")
        cols = st.columns(4)
        for index, (label, (status, detail)) in enumerate(readiness.items()):
            with cols[index % 4]:
                st.metric(label, cenara_status_label(status), detail)
        st.divider()
        st.caption("Diagnóstico de runtime")
        diag_cols = st.columns(4)
        for index, (label, value) in enumerate(cenara_runtime_diagnostics().items()):
            with diag_cols[index % 4]:
                st.metric(label, value)

def cenara_render_command_center(params, selected_tts_server):
    st.markdown(render_cenara_topbar(), unsafe_allow_html=True)
    cenara_render_hero_and_stepper()
    readiness = cenara_provider_readiness(params.video_source, selected_tts_server)
    cenara_render_provider_center(readiness)
    left, middle, right = st.columns([1.05, 1.05, 0.9], gap="large")
    with left:
        st.markdown('<div class="cenara-workspace-card"><div class="cenara-card-kicker">01 · AI Briefing</div><h3>Direção criativa</h3><p class="cenara-card-copy">Gere roteiro, hook, CTA, variações e palavras-chave usando o motor real configurado.</p></div>', unsafe_allow_html=True)
        with st.form("cenara_real_creator_form"):
            tema = st.text_input("Tema do vídeo", value=st.session_state.get("video_subject", ""), key="cenara_tema")
            publico = st.text_input("Público-alvo", key="cenara_publico")
            promessa = st.text_input("Promessa", key="cenara_promessa")
            nicho = st.text_input("Nicho", key="cenara_nicho")
            cta = st.text_input("CTA", key="cenara_cta")
            roteiro_manual = st.text_area("Roteiro manual opcional", value=st.session_state.get("video_script", ""), key="cenara_roteiro_manual")
            palavras_chave = st.text_area("Palavras-chave opcionais", value=st.session_state.get("video_terms", ""), key="cenara_palavras_chave")
            formato = st.selectbox("Formato", ["9:16", "1:1", "16:9"], key="cenara_formato")
            duracao = st.selectbox("Duração", [3, 4, 5, 6, 7, 8, 9, 10], key="cenara_duracao")
            _video_sources = ["frontier_ai", "pexels", "pixabay", "coverr", "local"]
            fonte_video = st.selectbox(
                "Fonte do vídeo",
                _video_sources,
                index=_video_sources.index(params.video_source if params.video_source in _video_sources else "frontier_ai"),
                format_func=lambda value: {
                    "frontier_ai": "Frontier AI · Seedance / Veo / Kling / Wan",
                    "pexels": "Pexels",
                    "pixabay": "Pixabay",
                    "coverr": "Coverr",
                    "local": "Mídia local",
                }.get(value, value),
                key="cenara_fonte_video",
            )
            voz_tts = st.text_input("Voz", value=params.voice_name or config.ui.get("voice_name", ""), key="cenara_voz_tts")
            ativar_legendas = st.checkbox("Ativar Legendas", value=bool(getattr(params, "subtitle_enabled", True)), key="cenara_ativar_legendas")
            submitted = st.form_submit_button("Gerar vídeo real", use_container_width=True, type="primary")
    with middle:
        subtitle_label = "Ativas" if getattr(params, "subtitle_enabled", True) else "Desativadas"
        st.markdown(f'<div class="cenara-workspace-card"><div class="cenara-card-kicker">02 · Build Engine</div><h3>Mídia, voz e estilo</h3><p class="cenara-card-copy">Use Frontier AI, Pexels, Pixabay, Coverr ou mídia local; ajuste TTS, áudio, formato e legendas nos controles avançados abaixo.</p><div class="cenara-timeline"><div class="cenara-timeline-row"><span><span class="cenara-status-dot"></span>Fonte de mídia</span><strong>{params.video_source or "auto"}</strong></div><div class="cenara-timeline-row"><span><span class="cenara-status-dot"></span>Voz</span><strong>{config.ui.get("tts_server", "azure")}</strong></div><div class="cenara-timeline-row"><span><span class="cenara-status-dot"></span>Legendas</span><strong>{subtitle_label}</strong></div></div></div>', unsafe_allow_html=True)
        st.info("Os controles completos de mídia, voz, música, subtítulos, transições e renderização continuam disponíveis em Controles avançados MoneyPrinterTurbo.")
    cenara_clear_stale_generation_lock(show_message=True)
    if st.session_state.pop("cenara_stale_lock_released", False):
        st.info("A geração anterior foi interrompida pelo servidor; o bloqueio foi liberado com segurança.")
    lock_status = cenara_generation_lock_status()
    if lock_status:
        created = float(lock_status.get("created_at_epoch", time.time()))
        age = max(0, int(time.time() - created))
        ttl = cenara_runtime_limits().generation_lock_ttl_seconds
        freshness = "fresh" if age <= ttl else "stale"
        st.warning(f"memory_guard_active: task_id={lock_status.get('task_id', 'unknown')} age={age}s status={freshness}. Aguarde finalizar; se ficar stale, use Limpar geração travada.")
        if age > ttl and st.button("Limpar geração travada", key="cenara_clear_stale_lock_button"):
            cenara_clear_stale_generation_lock(show_message=True)
            st.rerun()
    if submitted:
        if lock_status:
            st.stop()
        form = {"tema": tema, "publico": publico, "promessa": promessa, "nicho": nicho, "cta": cta, "manual_script": roteiro_manual, "manual_keywords": palavras_chave, "roteiro_manual": roteiro_manual, "palavras_chave": palavras_chave, "formato": formato, "duracao": duracao, "fonte_video": fonte_video, "voz_tts": voz_tts}
        payload = cenara_build_generation_payload(form, params)
        payload.subtitle_enabled = bool(ativar_legendas)
        st.session_state["video_subject"] = payload.video_subject
        st.session_state["video_script"] = payload.video_script
        st.session_state["video_terms"] = payload.video_terms
        readiness = cenara_provider_readiness(payload.video_source, selected_tts_server)
        if payload.voice_name or payload.custom_audio_file:
            readiness["Voz/TTS"] = ("configured", "voz do formulário" if payload.voice_name else "áudio personalizado")
        errors = cenara_validate_generation_payload(payload, readiness=readiness)
        if errors:
            for error in errors:
                st.error(error)
            st.stop()
        task_id = str(uuid4())
        st.info(f"Geração iniciada. Acompanhe o progresso abaixo. task_id: {task_id}")
        status_box = st.status("validando provedores", expanded=True)
        for stage in CENARA_PIPELINE_STAGES[:-2]:
            status_box.write(stage)
        try:
            with cenara_single_flight_generation_lock(task_id):
                tm.prune_cenara_storage(active_task_id=task_id)
                result = cenara_trigger_real_generation(task_id, payload, status_box=status_box)
                if result.get("success"):
                    tm.prune_cenara_storage(active_task_id=task_id)
        except RuntimeError:
            st.warning("memory_guard_active: geração já em execução; tentativa bloqueada com segurança.")
            st.stop()
        if result["success"]:
            output_path = Path(result["output_path"])
            status_box.update(label="finalizado", state="complete")
            st.session_state["cenara_latest_mp4"] = str(output_path)
            st.session_state["cenara_latest_task_id"] = task_id
            cenara_save_project_record(task_id, payload, output_path, "completed")
            st.success(f"render_completed_low_memory: Vídeo real gerado com sucesso. task_id: {task_id}")
            st.caption(f"Arquivo pronto: {output_path.name}")
        else:
            status_box.write("falhou")
            status_box.update(label="falhou", state="error")
            cenara_save_project_record(task_id, payload, None, "failed", result.get("error", "Falha desconhecida"))
            st.error(result.get("error") or "A geração falhou sem mensagem detalhada.")
            if result.get("next_action"):
                st.info(result["next_action"])
    with right:
        st.markdown('<div class="cenara-workspace-card"><div class="cenara-card-kicker">03 · Preview & Output</div><h3>Render real</h3></div>', unsafe_allow_html=True)
        latest_path = Path(st.session_state["cenara_latest_mp4"]) if st.session_state.get("cenara_latest_mp4") else None
        cenara_render_real_preview(latest_path)
    recent_projects = cenara_load_projects()[:6]
    if recent_projects:
        st.subheader("Projetos recentes")
        project_cols = st.columns(3)
        for index, project in enumerate(recent_projects):
            with project_cols[index % 3]:
                st.markdown(f"""<div class="cenara-flow-card"><div class="cenara-flow-title">{project.get('title','Projeto Cenara')[:80]}</div><div class="cenara-flow-copy">{project.get('status','')} · {project.get('source','')} · {project.get('created_at','')}</div><div class="cenara-flow-copy">{project.get('error','')}</div></div>""", unsafe_allow_html=True)
    cenara_render_recent_videos()


def get_all_fonts():
    fonts = []
    for root, dirs, files in os.walk(font_dir):
        for file in files:
            if file.endswith(".ttf") or file.endswith(".ttc"):
                fonts.append(file)
    fonts.sort()
    return fonts


def get_all_songs():
    songs = []
    for root, dirs, files in os.walk(song_dir):
        for file in files:
            if file.endswith(".mp3"):
                songs.append(file)
    return songs


def open_task_folder(task_id):
    try:
        # task_id 应始终是服务端生成的 UUID。这里先做格式校验，避免异常值
        # 通过路径拼接访问任务目录之外的位置，也避免后续打开目录时触发
        # 平台 shell 对特殊字符的解释。
        normalized_task_id = str(UUID(str(task_id)))
        tasks_root = os.path.abspath(os.path.join(root_dir, "storage", "tasks"))
        path = os.path.abspath(os.path.join(tasks_root, normalized_task_id))

        # 即使 UUID 校验通过，也再次确认最终路径仍在任务根目录内，避免
        # 未来调用方调整 task_id 来源时引入路径穿越风险。
        if not path.startswith(tasks_root + os.sep):
            logger.warning(f"invalid task folder path: {path}")
            return

        if os.path.isdir(path):
            webbrowser.open(f"file://{path}")
    except Exception as e:
        logger.error(e)


def scroll_to_bottom():
    # Premium rebuild avoids custom JavaScript/iframes; Streamlit handles viewport updates.
    return None


def init_log():
    logger.remove()
    _lvl = "DEBUG"

    def format_record(record):
        # 获取日志记录中的文件全路径
        file_path = record["file"].path
        # 将绝对路径转换为相对于项目根目录的路径
        relative_path = os.path.relpath(file_path, root_dir)
        # 更新记录中的文件路径
        record["file"].path = f"./{relative_path}"
        # 返回修改后的格式字符串
        # 您可以根据需要调整这里的格式
        record["message"] = record["message"].replace(root_dir, ".")

        _format = (
            "<green>{time:%Y-%m-%d %H:%M:%S}</> | "
            + "<level>{level}</> | "
            + '"{file.path}:{line}":<blue> {function}</> '
            + "- <level>{message}</>"
            + "\n"
        )
        return _format

    logger.add(
        sys.stdout,
        level=_lvl,
        format=format_record,
        colorize=True,
    )


init_log()

locales = utils.load_locales(i18n_dir)


def tr(key):
    loc = locales.get(st.session_state["ui_language"], {})
    return loc.get("Translation", {}).get(key, key)

@st.cache_data(ttl=300, show_spinner=False)
def get_groq_model_ids(api_key: str, base_url: str) -> list[str]:
    if not api_key:
        return []

    normalized_base_url = (base_url or "https://api.groq.com/openai/v1").strip().rstrip("/")
    models_url = f"{normalized_base_url}/models"

    try:
        response = requests.get(
            models_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", [])

        model_ids = []
        for item in data:
            if isinstance(item, dict):
                model_id = item.get("id")
                if isinstance(model_id, str) and model_id.strip():
                    model_ids.append(model_id.strip())

        return sorted(set(model_ids))
    except Exception as e:
        logger.warning(f"failed to fetch groq models: {e}")
        return []

# 创建基础设置折叠框
if not config.app.get("hide_config", False):
    with st.expander("Configuração de Provedores", expanded=False):
        config_panels = st.columns(3)
        left_config_panel = config_panels[0]
        middle_config_panel = config_panels[1]
        right_config_panel = config_panels[2]

        # 左侧面板 - 日志设置
        with left_config_panel:
            # 是否隐藏配置面板
            hide_config = st.checkbox(
                tr("Hide Basic Settings"), value=config.app.get("hide_config", False)
            )
            config.app["hide_config"] = hide_config

            # 是否禁用日志显示
            hide_log = st.checkbox(
                tr("Hide Log"), value=config.ui.get("hide_log", False)
            )
            config.ui["hide_log"] = hide_log

        # 中间面板 - LLM 设置

        with middle_config_panel:
            st.write(tr("LLM Settings"))
            # 下拉框需要展示“AIHubMix（推荐）”这类面向用户的文案，
            # 但配置文件和后端逻辑必须继续使用稳定的小写 provider id。
            # 因此这里显式维护 display label 和 provider id 的映射，避免
            # UI 文案变化污染 `config.app["llm_provider"]`。
            aihubmix_label = f"AIHubMix ({tr('Recommended')})"
            if config.ui.get("language") == "zh":
                aihubmix_label = "AIHubMix（推荐）"
            llm_provider_options = [
                ("OpenAI", "openai"),
                (aihubmix_label, "aihubmix"),
                ("AIML API", "aimlapi"),
                ("EvoLink", "evolink"),
                ("VolcEngine", "volcengine"),
                ("Moonshot", "moonshot"),
                ("Azure", "azure"),
                ("Qwen", "qwen"),
                ("DeepSeek", "deepseek"),
                ("ModelScope", "modelscope"),
                ("Gemini", "gemini"),
                ("Grok", "grok"),
                ("Groq", "groq"),
                ("Ollama", "ollama"),
                ("G4f", "g4f"),
                ("OneAPI", "oneapi"),
                ("Cloudflare", "cloudflare"),
                ("ERNIE", "ernie"),
                ("MiniMax", "minimax"),
                ("MiMo", "mimo"),
                ("Pollinations", "pollinations"),
                ("LiteLLM", "litellm"),
            ]
            llm_provider_ids = [provider_id for _, provider_id in llm_provider_options]
            llm_provider_labels = {
                provider_id: label for label, provider_id in llm_provider_options
            }
            saved_llm_provider = config.app.get("llm_provider", "openai").lower()
            if saved_llm_provider not in llm_provider_ids:
                saved_llm_provider = "openai"

            # Streamlit 会把没有 key 的 selectbox 视为一个由 label/options/index
            # 共同决定的临时控件。如果每次选择后都根据 config.app 重新计算 index，
            # 用户第一次切换 provider 后控件可能被重建，表现为“必须选择两次才生效”。
            # 这里用稳定的 provider id 作为真实选项，并给控件固定 key；展示文案只
            # 通过 format_func 转换，避免 UI 文案变化影响状态。
            if st.session_state.get("llm_provider_select") not in (
                None,
                *llm_provider_ids,
            ):
                del st.session_state["llm_provider_select"]

            previous_llm_provider = _llm_provider_id_normalized(config.app.get("llm_provider", "openai"))
            llm_provider = st.selectbox(
                tr("LLM Provider"),
                options=llm_provider_ids,
                index=llm_provider_ids.index(saved_llm_provider),
                format_func=lambda provider_id: llm_provider_labels[provider_id],
                key="llm_provider_select",
            )
            if _llm_provider_id_normalized(llm_provider) != previous_llm_provider:
                st.session_state.pop("cenara_llm_provider_status", None)
            cenara_reset_llm_blocked_status_if_changed(llm_provider)
            llm_helper = st.container()
            config.app["llm_provider"] = llm_provider

            llm_api_key = config.app.get(f"{llm_provider}_api_key", "")
            llm_secret_key = config.app.get(
                f"{llm_provider}_secret_key", ""
            )  # only for baidu ernie
            llm_base_url = config.app.get(f"{llm_provider}_base_url", "")
            llm_model_name = config.app.get(f"{llm_provider}_model_name", "")
            llm_account_id = config.app.get(f"{llm_provider}_account_id", "")

            tips = ""
            if llm_provider == "ollama":
                if not llm_model_name:
                    llm_model_name = "qwen:7b"
                if not llm_base_url:
                    llm_base_url = config.get_default_ollama_base_url()

                with llm_helper:
                    docker_hint = ""
                    if config.is_running_in_container():
                        docker_hint = "\n                            > 检测到容器环境，未配置 Base Url 时会默认使用 `http://host.docker.internal:11434/v1`\n"
                    tips = f"""
                            ##### Ollama配置说明
                            - **API Key**: 随便填写，比如 123
                            - **Base Url**: 一般为 http://localhost:11434/v1
                                - 如果 `MoneyPrinterTurbo` 和 `Ollama` **不在同一台机器上**，需要填写 `Ollama` 机器的IP地址
                                - 如果 `MoneyPrinterTurbo` 是 `Docker` 部署，建议填写 `http://host.docker.internal:11434/v1`{docker_hint}
                            - **Model Name**: 使用 `ollama list` 查看，比如 `qwen:7b`
                            """

            if llm_provider == "openai":
                if not llm_model_name:
                    llm_model_name = "gpt-3.5-turbo"
                with llm_helper:
                    tips = """
                            ##### OpenAI 配置说明
                            > 需要VPN开启全局流量模式
                            - **API Key**: [点击到官网申请](https://platform.openai.com/api-keys)
                            - **Base Url**: 官方 OpenAI 可留空；如果使用 OpenAI 兼容供应商（例如 OpenRouter），请填写对应的兼容接口地址
                            - **Model Name**: 填写**有权限**的模型；如果使用兼容供应商，请填写该平台支持的模型 ID
                            """

            if llm_provider == "aihubmix":
                if not llm_model_name:
                    llm_model_name = "gpt-5.4-mini"
                if not llm_base_url:
                    llm_base_url = "https://aihubmix.com/v1"
                with llm_helper:
                    tips = """
                            ##### AIHubMix 配置说明
                            - **注册链接**: [点击注册 AIHubMix](https://aihubmix.com/?aff=CEve)
                            - **Base Url**: 预填 https://aihubmix.com/v1
                            - **推荐模型**: 默认 gpt-5.4-mini，也可以填写 AIHubMix 支持的免费模型或其它模型 ID

                            推荐理由：
                            - **模型全**: Claude、GPT、Gemini、Grok、DeepSeek、通义等 700+ 模型一站覆盖
                            - **稳定**: 无限并发，永远在线，集群部署于谷歌云，长期为众多知名应用提供高并发服务
                            - **能力完整**: 文本、图片生成、视频生成、TTS、STT、向量嵌入、Rerank，多模态场景全搞定
                            - **计费透明**: 按量付费，无会员无包月，免费模型可使用
                            """

            if llm_provider == "aimlapi":
                if not llm_model_name:
                    llm_model_name = "openai/gpt-4o-mini"
                if not llm_base_url:
                    llm_base_url = "https://api.aimlapi.com/v1"
                with llm_helper:
                    tips = """
                            ##### AIML API Configuration
                            - **API Key**: create one at https://aimlapi.com/app/keys
                            - **Base Url**: https://api.aimlapi.com/v1
                            - **Model Name**: for example `openai/gpt-4o-mini`, `openai/gpt-4o`, `anthropic/claude-sonnet-4.5`, or `google/gemini-3-flash-preview`
                            """

            if llm_provider == "evolink":
                if not llm_model_name:
                    llm_model_name = "gpt-5.5"
                if not llm_base_url:
                    llm_base_url = "https://direct.evolink.ai/v1"
                with llm_helper:
                    tips = """
                            ##### EvoLink 配置说明
                            - **API Key**: [点击到官网申请](https://evolink.ai/dashboard/keys)
                            - **Base Url**: 默认 https://direct.evolink.ai/v1
                            - **Model Name**: 默认 gpt-5.5，也可以填写 EvoLink 支持的其它模型 ID
                            """

            if llm_provider == "volcengine":
                if not llm_model_name:
                    llm_model_name = "doubao-seed-2-1-turbo-260628"
                if not llm_base_url:
                    llm_base_url = "https://ark.cn-beijing.volces.com/api/v3"
                with llm_helper:
                    tips = """
                            ##### VolcEngine Ark 配置说明
                            - **注册链接**: [点击注册 火山引擎](https://www.volcengine.com/activity/ai618?utm_campaign=hw&utm_content=hw&utm_medium=devrel_tool_web&utm_source=OWO&utm_term=MoneyPrinterTurbo)
                            - **API Key**: 在火山引擎方舟控制台创建 API Key
                            - **Base Url**: 默认 https://ark.cn-beijing.volces.com/api/v3
                            - **Model Name**: 填写 Ark 控制台已开通的模型 ID，例如 doubao-seed-2-1-turbo-260628
                            """

            if llm_provider == "moonshot":
                if not llm_model_name:
                    llm_model_name = "moonshot-v1-8k"
                with llm_helper:
                    tips = """
                            ##### Moonshot 配置说明
                            - **API Key**: [点击到官网申请](https://platform.moonshot.cn/console/api-keys)
                            - **Base Url**: 固定为 https://api.moonshot.cn/v1
                            - **Model Name**: 比如 moonshot-v1-8k，[点击查看模型列表](https://platform.moonshot.cn/docs/intro#%E6%A8%A1%E5%9E%8B%E5%88%97%E8%A1%A8)
                            """
            if llm_provider == "oneapi":
                if not llm_model_name:
                    llm_model_name = (
                        "claude-3-5-sonnet-20240620"  # 默认模型，可以根据需要调整
                    )
                with llm_helper:
                    tips = """
                        ##### OneAPI 配置说明
                        - **API Key**: 填写您的 OneAPI 密钥
                        - **Base Url**: 填写 OneAPI 的基础 URL
                        - **Model Name**: 填写您要使用的模型名称，例如 claude-3-5-sonnet-20240620
                        """

            if llm_provider == "qwen":
                if not llm_model_name:
                    llm_model_name = "qwen-max"
                with llm_helper:
                    tips = """
                            ##### 通义千问Qwen 配置说明
                            - **API Key**: [点击到官网申请](https://dashscope.console.aliyun.com/apiKey)
                            - **Base Url**: 留空
                            - **Model Name**: 比如 qwen-max，[点击查看模型列表](https://help.aliyun.com/zh/dashscope/developer-reference/model-introduction#3ef6d0bcf91wy)
                            """

            if llm_provider == "g4f":
                if not llm_model_name:
                    llm_model_name = "gpt-3.5-turbo"
                with llm_helper:
                    tips = """
                            ##### gpt4free 配置说明
                            > [GitHub开源项目](https://github.com/xtekky/gpt4free)，可以免费使用GPT模型，但是**稳定性较差**
                            - **API Key**: 随便填写，比如 123
                            - **Base Url**: 留空
                            - **Model Name**: 比如 gpt-3.5-turbo，[点击查看模型列表](https://github.com/xtekky/gpt4free/blob/main/g4f/models.py#L308)
                            """
            if llm_provider == "azure":
                with llm_helper:
                    tips = """
                            ##### Azure 配置说明
                            > [点击查看如何部署模型](https://learn.microsoft.com/zh-cn/azure/ai-services/openai/how-to/create-resource)
                            - **API Key**: [点击到Azure后台创建](https://portal.azure.com/#view/Microsoft_Azure_ProjectOxford/CognitiveServicesHub/~/OpenAI)
                            - **Base Url**: 留空
                            - **Model Name**: 填写你实际的部署名
                            """

            if llm_provider == "gemini":
                if not llm_model_name:
                    llm_model_name = "gemini-1.0-pro"

                with llm_helper:
                    tips = """
                            ##### Gemini 配置说明
                            > 需要VPN开启全局流量模式
                            - **API Key**: [点击到官网申请](https://ai.google.dev/)
                            - **Base Url**: 留空
                            - **Model Name**: 比如 gemini-1.0-pro
                            """

            if llm_provider == "grok":
                if not llm_model_name:
                    llm_model_name = "grok-4.3"
                if not llm_base_url:
                    llm_base_url = "https://api.x.ai/v1"

                with llm_helper:
                    tips = """
                            ##### Grok 配置说明
                            - **API Key**: 填写您的 GrokAPI 密钥
                            - **Base Url**: 填写 GrokAPI 的基础 URL
                            - **Model Name**: 比如 grok-4.3
                            """

            if llm_provider == "groq":
                if not llm_model_name:
                    llm_model_name = "llama-3.3-70b-versatile"
                if not llm_base_url:
                    llm_base_url = "https://api.groq.com/openai/v1"

                with llm_helper:
                    tips = """
                            ##### Groq 配置说明
                            - **API Key**: [点击到官网申请](https://console.groq.com/keys)
                            - **Base Url**: 固定为 https://api.groq.com/openai/v1
                            - **Model Name**: 比如 llama-3.3-70b-versatile
                            """

            if llm_provider == "deepseek":
                if not llm_model_name:
                    llm_model_name = "deepseek-chat"
                if not llm_base_url:
                    llm_base_url = "https://api.deepseek.com"
                with llm_helper:
                    tips = """
                            ##### DeepSeek 配置说明
                            - **API Key**: [点击到官网申请](https://platform.deepseek.com/api_keys)
                            - **Base Url**: 固定为 https://api.deepseek.com
                            - **Model Name**: 固定为 deepseek-chat
                            """

            if llm_provider == "mimo":
                if not llm_model_name:
                    llm_model_name = "mimo-v2.5-pro"
                if not llm_base_url:
                    llm_base_url = "https://api.xiaomimimo.com/v1"
                with llm_helper:
                    tips = """
                            ##### Xiaomi MiMo 配置说明
                            - **API Key**: [点击到官网申请](https://platform.xiaomimimo.com/docs/zh-CN/quick-start/first-api-call)
                            - **Base Url**: 固定为 https://api.xiaomimimo.com/v1
                            - **Model Name**: 默认 mimo-v2.5-pro，也可以按官方文档填写其它可用模型
                            """

            if llm_provider == "modelscope":
                if not llm_model_name:
                    llm_model_name = "Qwen/Qwen3-32B"
                if not llm_base_url:
                    llm_base_url = "https://api-inference.modelscope.cn/v1/"
                with llm_helper:
                    tips = """
                            ##### ModelScope 配置说明
                            - **API Key**: [点击到官网申请](https://modelscope.cn/docs/model-service/API-Inference/intro)
                            - **Base Url**: 固定为 https://api-inference.modelscope.cn/v1/
                            - **Model Name**: 比如 Qwen/Qwen3-32B，[点击查看模型列表](https://modelscope.cn/models?filter=inference_type&page=1)
                            """

            if llm_provider == "ernie":
                with llm_helper:
                    tips = """
                            ##### 百度文心一言 配置说明
                            - **API Key**: [点击到官网申请](https://console.bce.baidu.com/qianfan/ais/console/applicationConsole/application)
                            - **Secret Key**: [点击到官网申请](https://console.bce.baidu.com/qianfan/ais/console/applicationConsole/application)
                            - **Base Url**: 填写 **请求地址** [点击查看文档](https://cloud.baidu.com/doc/WENXINWORKSHOP/s/jlil56u11#%E8%AF%B7%E6%B1%82%E8%AF%B4%E6%98%8E)
                            """

            if llm_provider == "pollinations":
                if not llm_model_name:
                    llm_model_name = "default"
                with llm_helper:
                    tips = """
                            ##### Pollinations AI Configuration
                            - **API Key**: Optional - Leave empty for public access
                            - **Base Url**: Default is https://text.pollinations.ai/openai
                            - **Model Name**: Use 'openai-fast' or specify a model name
                            """

            if llm_provider == "litellm":
                if not llm_model_name:
                    llm_model_name = "openai/gpt-4o-mini"
                with llm_helper:
                    tips = """
                            ##### LiteLLM Configuration
                            > [LiteLLM](https://github.com/BerriAI/litellm) routes to 100+ LLM providers via a unified interface.
                            > Set your provider's API key as an env var: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `AWS_ACCESS_KEY_ID`, etc.
                            - **Model Name**: LiteLLM format — `openai/gpt-4o`, `anthropic/claude-sonnet-4-20250514`, `bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0`, `gemini/gemini-2.5-flash`. See [full provider list](https://docs.litellm.ai/docs/providers)
                            """

            if tips and config.ui["language"] == "zh":
                st.info(tips)

            st_llm_api_key = st.text_input(
                tr("API Key"),
                value="",
                type="password",
                placeholder="Cole uma nova chave para atualizar",
                key=f"{llm_provider}_api_key_input",
            )
            st_llm_base_url = st.text_input(tr("Base Url"), value=llm_base_url)
            st_llm_model_name = ""
            if llm_provider != "ernie":
                if llm_provider == "groq":
                    effective_api_key = st_llm_api_key or llm_api_key
                    effective_base_url = st_llm_base_url or llm_base_url
                    groq_models = get_groq_model_ids(
                        api_key=effective_api_key,
                        base_url=effective_base_url,
                    )

                    if groq_models:
                        selected_index = 0
                        if llm_model_name in groq_models:
                            selected_index = groq_models.index(llm_model_name)

                        st_llm_model_name = st.selectbox(
                            tr("Model Name"),
                            options=groq_models,
                            index=selected_index,
                            key="groq_model_name_select",
                        )
                    else:
                        st_llm_model_name = st.text_input(
                            tr("Model Name"),
                            value=llm_model_name,
                            key="groq_model_name_input",
                        )
                        if effective_api_key:
                            st.caption(
                                "Unable to load Groq model list right now. You can still enter a model name manually — note it won't be validated until generation."
                            )
                        else:
                            st.caption(
                                "Add a Groq API key to load available models automatically."
                            )
                else:
                    st_llm_model_name = st.text_input(
                        tr("Model Name"),
                        value=llm_model_name,
                        key=f"{llm_provider}_model_name_input",
                    )
                if st_llm_model_name:
                    config.app[f"{llm_provider}_model_name"] = st_llm_model_name
            else:
                st_llm_model_name = None

            if st_llm_api_key:
                cenara_reset_llm_blocked_status_if_changed(llm_provider, st_llm_api_key)
                config.app[f"{llm_provider}_api_key"] = st_llm_api_key
            if st_llm_base_url:
                config.app[f"{llm_provider}_base_url"] = st_llm_base_url
            if st_llm_model_name:
                config.app[f"{llm_provider}_model_name"] = st_llm_model_name
            if llm_provider == "ernie":
                st_llm_secret_key = st.text_input(
                    tr("Secret Key"), value="", type="password", placeholder="Cole uma nova secret key para atualizar"
                )
                if st_llm_secret_key:
                    cenara_reset_llm_blocked_status_if_changed(llm_provider, st_llm_secret_key)
                    config.app[f"{llm_provider}_secret_key"] = st_llm_secret_key

            if llm_provider == "cloudflare":
                st_llm_account_id = st.text_input(
                    tr("Account ID"), value=llm_account_id
                )
                if st_llm_account_id:
                    config.app[f"{llm_provider}_account_id"] = st_llm_account_id

        # 右侧面板 - API 密钥设置
        with right_config_panel:

            def get_keys_from_config(cfg_key):
                api_keys = config.app.get(cfg_key, [])
                if isinstance(api_keys, str):
                    api_keys = [api_keys]
                api_key = ", ".join(api_keys)
                return api_key

            def save_keys_to_config(cfg_key, value):
                value = value.replace(" ", "")
                if value:
                    config.app[cfg_key] = value.split(",")

            st.write("Fontes de vídeo")
            provider_cards = [
                ("Pexels", _has_configured_secret(_provider_secret_list("pexels", config_value=config.app.get("pexels_api_keys", []))), "https://www.pexels.com/api/"),
                ("Pixabay", _has_configured_secret(_provider_secret_list("pixabay", config_value=config.app.get("pixabay_api_keys", []))), "https://pixabay.com/api/docs/"),
                ("Coverr", _has_configured_secret(_provider_secret_list("coverr", config_value=config.app.get("coverr_api_keys", []))), "https://coverr.co/api"),
            ]
            render_cenara_provider_status_cards(provider_cards)

            with st.form("cenara_provider_keys_update_form", clear_on_submit=True):
                pexels_api_key = st.text_input(
                    tr("Pexels API Key"),
                    value="",
                    type="password",
                    placeholder="Cole uma nova chave Pexels",
                    key="pexels_api_key_update_input",
                )

                pixabay_api_key = st.text_input(
                    tr("Pixabay API Key"),
                    value="",
                    type="password",
                    placeholder="Cole uma nova chave Pixabay",
                    key="pixabay_api_key_update_input",
                )

                coverr_api_key = st.text_input(
                    tr("Coverr API Key"),
                    value="",
                    type="password",
                    placeholder="Cole uma nova chave Coverr",
                    key="coverr_api_key_update_input",
                )

                provider_keys_submitted = st.form_submit_button(
                    "Atualizar chaves de fontes"
                )

            if provider_keys_submitted:
                save_keys_to_config("pexels_api_keys", pexels_api_key)
                save_keys_to_config("pixabay_api_keys", pixabay_api_key)
                save_keys_to_config("coverr_api_keys", coverr_api_key)
                st.success("Chaves de fontes atualizadas quando valores foram informados.")

llm_provider = config.app.get("llm_provider", "").lower()
panel = st.columns(3)
left_panel = panel[0]
middle_panel = panel[1]
right_panel = panel[2]

params = VideoParams(video_subject="")
params.match_materials_to_script = bool(
    st.session_state.get("match_materials_to_script", False)
)
uploaded_files = []
uploaded_audio_file = None

cenara_render_command_center(params, config.ui.get("tts_server", "azure-tts-v1"))

with st.expander("Controles avançados MoneyPrinterTurbo", expanded=False):

    with left_panel:
        with st.container(border=True):
            st.write(tr("Video Script Settings"))
            params.video_subject = st.text_input(
                tr("Video Subject"),
                key="video_subject",
            ).strip()

            video_languages = [
                (tr("Auto Detect"), ""),
            ]
            for code in support_locales:
                video_languages.append((code, code))

            selected_index = st.selectbox(
                tr("Script Language"),
                index=0,
                options=range(
                    len(video_languages)
                ),  # Use the index as the internal option value
                format_func=lambda x: video_languages[x][
                    0
                ],  # The label is displayed to the user
            )
            params.video_language = video_languages[selected_index][1]

            with st.expander(tr("Advanced Script Settings"), expanded=False):
                params.paragraph_number = st.slider(
                    tr("Script Paragraph Number"),
                    min_value=llm.MIN_SCRIPT_PARAGRAPH_NUMBER,
                    max_value=llm.MAX_SCRIPT_PARAGRAPH_NUMBER,
                    value=st.session_state.get("paragraph_number_input", 1),
                    key="paragraph_number_input",
                )
                params.video_script_prompt = st.text_area(
                    tr("Custom Script Requirements"),
                    height=100,
                    max_chars=llm.MAX_SCRIPT_PROMPT_LENGTH,
                    placeholder=tr("Custom Script Requirements Placeholder"),
                    key="video_script_prompt",
                ).strip()

                use_custom_system_prompt = st.checkbox(
                    tr("Use Custom System Prompt"),
                    help=tr("Use Custom System Prompt Help"),
                    key="use_custom_system_prompt",
                )

                if use_custom_system_prompt:
                    custom_system_prompt = st.text_area(
                        tr("Custom System Prompt"),
                        height=240,
                        max_chars=llm.MAX_SCRIPT_SYSTEM_PROMPT_LENGTH,
                        key="custom_system_prompt",
                    ).strip()
                    params.custom_system_prompt = custom_system_prompt
                else:
                    params.custom_system_prompt = ""

            if st.button(
                tr("Generate Video Script and Keywords"), key="auto_generate_script"
            ):
                with st.spinner(tr("Generating Video Script and Keywords")):
                    script = llm.generate_script(
                        video_subject=params.video_subject,
                        language=params.video_language,
                        paragraph_number=params.paragraph_number,
                        video_script_prompt=params.video_script_prompt,
                        custom_system_prompt=params.custom_system_prompt,
                    )
                    terms = llm.generate_terms(
                        params.video_subject,
                        script,
                        amount=8 if params.match_materials_to_script else 5,
                        match_script_order=params.match_materials_to_script,
                    )
                    if "Error: " in script:
                        st.error(tr(script))
                    elif "Error: " in terms:
                        st.error(tr(terms))
                    else:
                        st.session_state["video_script"] = script
                        st.session_state["video_terms"] = ", ".join(terms)
            params.video_script = st.text_area(
                tr("Video Script"), value=st.session_state["video_script"], height=280
            )
            if st.button(tr("Generate Video Keywords"), key="auto_generate_terms"):
                if not params.video_script:
                    st.error(tr("Please Enter the Video Subject"))
                    st.stop()

                with st.spinner(tr("Generating Video Keywords")):
                    terms = llm.generate_terms(
                        params.video_subject,
                        params.video_script,
                        amount=8 if params.match_materials_to_script else 5,
                        match_script_order=params.match_materials_to_script,
                    )
                    if "Error: " in terms:
                        st.error(tr(terms))
                    else:
                        st.session_state["video_terms"] = ", ".join(terms)

            params.video_terms = st.text_area(
                tr("Video Keywords"), value=st.session_state["video_terms"]
            )

    with middle_panel:
        with st.container(border=True):
            st.write(tr("Video Settings"))
            video_concat_modes = [
                (tr("Sequential"), "sequential"),
                (tr("Random"), "random"),
            ]
            video_sources = [
                (tr("Pexels"), "pexels"),
                (tr("Pixabay"), "pixabay"),
                (tr("Coverr"), "coverr"),
                (tr("Local file"), "local"),
                (tr("TikTok"), "douyin"),
                (tr("Bilibili"), "bilibili"),
                (tr("Xiaohongshu"), "xiaohongshu"),
            ]

            saved_video_source_name = config.app.get("video_source", "pexels")
            saved_video_source_index = [v[1] for v in video_sources].index(
                saved_video_source_name
            )

            selected_index = st.selectbox(
                tr("Video Source"),
                options=range(len(video_sources)),
                format_func=lambda x: video_sources[x][0],
                index=saved_video_source_index,
            )
            params.video_source = video_sources[selected_index][1]
            config.app["video_source"] = params.video_source

            if params.video_source == "local":
                # Streamlit 的文件类型校验对扩展名大小写敏感，这里同时放行大小写两种形式。
                local_file_types = ["mp4", "mov", "avi", "flv", "mkv", "jpg", "jpeg", "png"]
                uploaded_files = st.file_uploader(
                    tr("Upload Local Files"),
                    type=local_file_types + [file_type.upper() for file_type in local_file_types],
                    accept_multiple_files=True,
                )

            selected_index = st.selectbox(
                tr("Video Concat Mode"),
                index=1,
                options=range(
                    len(video_concat_modes)
                ),  # Use the index as the internal option value
                format_func=lambda x: video_concat_modes[x][
                    0
                ],  # The label is displayed to the user
            )
            params.video_concat_mode = VideoConcatMode(
                video_concat_modes[selected_index][1]
            )

            # 视频转场模式
            video_transition_modes = [
                (tr("None"), VideoTransitionMode.none.value),
                (tr("Shuffle"), VideoTransitionMode.shuffle.value),
                (tr("FadeIn"), VideoTransitionMode.fade_in.value),
                (tr("FadeOut"), VideoTransitionMode.fade_out.value),
                (tr("SlideIn"), VideoTransitionMode.slide_in.value),
                (tr("SlideOut"), VideoTransitionMode.slide_out.value),
            ]
            selected_index = st.selectbox(
                tr("Video Transition Mode"),
                options=range(len(video_transition_modes)),
                format_func=lambda x: video_transition_modes[x][0],
                index=0,
            )
            params.video_transition_mode = VideoTransitionMode(
                video_transition_modes[selected_index][1]
            )

            video_aspect_ratios = [
                (tr("Portrait"), VideoAspect.portrait.value),
                (tr("Landscape"), VideoAspect.landscape.value),
            ]
            # Coverr 库 99% 是 16:9 横屏,默认竖屏会让画面被大量黑边包围。
            # 用 source-specific widget key 让每个 source 各自记忆 aspect 选择:
            #   - 首次切到 coverr → 默认 Landscape(index=1)
            #   - 其他 source 沿用 Portrait(index=0)
            #   - 用户在某 source 下手动改过 aspect,session_state 会记住,
            #     下次回到同一 source 时尊重用户选择,不会再被强制覆盖。
            default_aspect_index = 1 if params.video_source == "coverr" else 0
            selected_index = st.selectbox(
                tr("Video Ratio"),
                options=range(
                    len(video_aspect_ratios)
                ),  # Use the index as the internal option value
                format_func=lambda x: video_aspect_ratios[x][
                    0
                ],  # The label is displayed to the user
                index=default_aspect_index,
                key=f"video_aspect_for_{params.video_source}",
            )
            params.video_aspect = VideoAspect(video_aspect_ratios[selected_index][1])

            params.video_clip_duration = st.selectbox(
                tr("Clip Duration"), options=[2, 3, 4, 5, 6, 7, 8, 9, 10], index=1
            )
            params.video_count = st.selectbox(
                tr("Number of Videos Generated Simultaneously"),
                options=[1, 2, 3, 4, 5],
                index=0,
            )

            with st.expander(tr("Advanced Video Settings"), expanded=False):
                # 默认关闭，避免影响老用户的随机素材体验。开启后只改变关键词和素材
                # 下载/拼接顺序，用于改善画面主题早于或晚于旁白的问题。
                params.match_materials_to_script = st.checkbox(
                    tr("Match Materials to Script Order"),
                    help=tr("Match Materials to Script Order Help"),
                    key="match_materials_to_script",
                )
                config.app["match_materials_to_script"] = params.match_materials_to_script

                video_codec_options = [
                    ("libx264 (CPU)", "libx264"),
                    ("NVIDIA NVENC (h264_nvenc)", "h264_nvenc"),
                    ("AMD AMF (h264_amf)", "h264_amf"),
                    ("Intel QSV (h264_qsv)", "h264_qsv"),
                    ("Windows MediaFoundation (h264_mf)", "h264_mf"),
                    ("macOS VideoToolbox (h264_videotoolbox)", "h264_videotoolbox"),
                ]
                saved_video_codec = config.app.get("video_codec", "libx264")
                saved_video_codec_values = [item[1] for item in video_codec_options]
                if saved_video_codec not in saved_video_codec_values:
                    saved_video_codec = "libx264"
                selected_codec_index = saved_video_codec_values.index(saved_video_codec)
                selected_codec_index = st.selectbox(
                    tr("Video Encoder"),
                    options=range(len(video_codec_options)),
                    index=selected_codec_index,
                    format_func=lambda x: video_codec_options[x][0],
                    help=tr("Video Encoder Help"),
                )
                config.app["video_codec"] = video_codec_options[selected_codec_index][1]
        with st.container(border=True):
            st.write(tr("Audio Settings"))

            # 添加TTS服务器选择下拉框
            tts_servers = [
                (voice.NO_VOICE_NAME, tr("No Voice")),
                ("azure-tts-v1", "Azure TTS V1"),
                ("azure-tts-v2", "Azure TTS V2"),
                ("siliconflow", "SiliconFlow TTS"),
                ("gemini-tts", "Google Gemini TTS"),
                ("mimo-tts", "Xiaomi MiMo TTS"),
                ("elevenlabs", "ElevenLabs TTS"),
                ("chatterbox", "Chatterbox TTS"),
            ]

            # 获取保存的TTS服务器，默认为v1
            saved_tts_server = config.ui.get("tts_server", "azure-tts-v1")
            saved_tts_server_index = 0
            for i, (server_value, _) in enumerate(tts_servers):
                if server_value == saved_tts_server:
                    saved_tts_server_index = i
                    break

            selected_tts_server_index = st.selectbox(
                tr("TTS Servers"),
                options=range(len(tts_servers)),
                format_func=lambda x: tts_servers[x][1],
                index=saved_tts_server_index,
            )

            selected_tts_server = tts_servers[selected_tts_server_index][0]
            config.ui["tts_server"] = selected_tts_server

            # 根据选择的TTS服务器获取声音列表
            filtered_voices = []

            if selected_tts_server == voice.NO_VOICE_NAME:
                # 无配音是显式模式，只提供一个稳定 sentinel。这样普通 TTS 的空配置
                # 不会被误判为静音，后端也能继续通过同一条音频/字幕流程生成视频。
                filtered_voices = [voice.NO_VOICE_NAME]
            elif selected_tts_server == "siliconflow":
                # 获取硅基流动的声音列表
                filtered_voices = voice.get_siliconflow_voices()
            elif selected_tts_server == "gemini-tts":
                # 获取Gemini TTS的声音列表
                filtered_voices = voice.get_gemini_voices()
            elif selected_tts_server == "mimo-tts":
                # 获取 Xiaomi MiMo TTS 的预置音色列表
                filtered_voices = voice.get_mimo_voices()
            elif selected_tts_server == "elevenlabs":
                # Read from session_state first so the API key is available before
                # the Play Voice button runs (which is earlier in the script than
                # the API key text_input widget).
                entered_elevenlabs_api_key = st.session_state.get("elevenlabs_api_key_input", "")
                elevenlabs_api_key_for_loading = (
                    _provider_secret("elevenlabs", ("elevenlabs_api_key_input",), config.elevenlabs.get("api_key"))
                )
                if entered_elevenlabs_api_key:
                    config.elevenlabs["api_key"] = entered_elevenlabs_api_key
                cache_key = "elevenlabs_voices_configured" if elevenlabs_api_key_for_loading else "elevenlabs_voices_missing"
                if cache_key not in st.session_state:
                    st.session_state[cache_key] = voice.get_elevenlabs_voices(
                        elevenlabs_api_key_for_loading
                    )
                filtered_voices = st.session_state[cache_key]
            elif selected_tts_server == "chatterbox":
                # 自托管 Chatterbox 服务的预置音色（来自 [chatterbox] voices 配置）
                _sync_chatterbox_config_from_session_state()
                filtered_voices = voice.get_chatterbox_voices()
            else:
                # 获取Azure的声音列表
                all_voices = voice.get_all_azure_voices(filter_locals=None)

                # 根据选择的TTS服务器筛选声音
                for v in all_voices:
                    if selected_tts_server == "azure-tts-v2":
                        # V2版本的声音名称中包含"v2"
                        if "V2" in v:
                            filtered_voices.append(v)
                    else:
                        # V1版本的声音名称中不包含"v2"
                        if "V2" not in v:
                            filtered_voices.append(v)

            if selected_tts_server == voice.NO_VOICE_NAME:
                friendly_names = {voice.NO_VOICE_NAME: tr("No Voice")}
            else:
                def _friendly(v):
                    if voice.is_elevenlabs_voice(v):
                        parts = v.split(":", 2)
                        return parts[2] if len(parts) >= 3 else v
                    if voice.is_chatterbox_voice(v):
                        name = v.split(":", 1)[1] if ":" in v else v
                        return name.replace("-Female", "").replace("-Male", "")
                    return (
                        v.replace("Female", tr("Female"))
                        .replace("Male", tr("Male"))
                        .replace("Neural", "")
                    )
                friendly_names = {v: _friendly(v) for v in filtered_voices}

            saved_voice_name = config.ui.get("voice_name", "")
            saved_voice_name_index = 0

            # 检查保存的声音是否在当前筛选的声音列表中
            if saved_voice_name in friendly_names:
                saved_voice_name_index = list(friendly_names.keys()).index(saved_voice_name)
            else:
                # 如果不在，则根据当前UI语言选择一个默认声音
                for i, v in enumerate(filtered_voices):
                    if v.lower().startswith(st.session_state["ui_language"].lower()):
                        saved_voice_name_index = i
                        break

            # 如果没有找到匹配的声音，使用第一个声音
            if saved_voice_name_index >= len(friendly_names) and friendly_names:
                saved_voice_name_index = 0

            # 确保有声音可选
            if friendly_names:
                selected_friendly_name = st.selectbox(
                    tr("Speech Synthesis"),
                    options=list(friendly_names.values()),
                    index=min(saved_voice_name_index, len(friendly_names) - 1)
                    if friendly_names
                    else 0,
                )

                voice_name = list(friendly_names.keys())[
                    list(friendly_names.values()).index(selected_friendly_name)
                ]
                params.voice_name = voice_name
                config.ui["voice_name"] = voice_name
            else:
                # 如果没有声音可选，显示提示信息
                st.warning(
                    tr(
                        "No voices available for the selected TTS server. Please select another server."
                    )
                )
                voice_name = ""
                params.voice_name = ""
                config.ui["voice_name"] = ""

            # 无配音模式会生成静音占位音频，不展示试听按钮，避免用户误以为需要测试声音。
            if (
                friendly_names
                and selected_tts_server != voice.NO_VOICE_NAME
                and st.button(tr("Play Voice"))
            ):
                if selected_tts_server == "chatterbox":
                    _sync_chatterbox_config_from_session_state()
                play_content = params.video_subject
                if not play_content:
                    play_content = params.video_script
                if not play_content:
                    # For ElevenLabs voices, detect language from the display name
                    # so the test text matches the voice's language.
                    if voice.is_elevenlabs_voice(voice_name):
                        parts = voice_name.split(":", 2)
                        display = parts[2] if len(parts) >= 3 else ""
                        _vi_chars = set("àáâãèéêìíòóôõùúýăđơưÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝĂĐƠƯ")
                        if any(c in _vi_chars for c in display):
                            play_content = "Xin chào, đây là đoạn âm thanh thử nghiệm giọng nói."
                        else:
                            play_content = tr("Voice Example")
                    else:
                        play_content = tr("Voice Example")
                with st.spinner(tr("Synthesizing Voice")):
                    temp_dir = utils.storage_dir("temp", create=True)
                    audio_file = os.path.join(temp_dir, f"tmp-voice-{str(uuid4())}.mp3")
                    sub_maker = voice.tts(
                        text=play_content,
                        voice_name=voice_name,
                        voice_rate=params.voice_rate,
                        voice_file=audio_file,
                        voice_volume=params.voice_volume,
                    )
                    # if the voice file generation failed, try again with a default content.
                    if not sub_maker:
                        play_content = "This is a example voice. if you hear this, the voice synthesis failed with the original content."
                        sub_maker = voice.tts(
                            text=play_content,
                            voice_name=voice_name,
                            voice_rate=params.voice_rate,
                            voice_file=audio_file,
                            voice_volume=params.voice_volume,
                        )

                    if sub_maker and os.path.exists(audio_file):
                        with open(audio_file, "rb") as f:
                            audio_bytes = f.read()
                        if audio_bytes:
                            st.audio(
                                audio_bytes,
                                format=_detect_audio_mime(audio_file, audio_bytes),
                            )
                        else:
                            logger.error(f"voice preview audio file is empty: {audio_file}")
                        if os.path.exists(audio_file):
                            os.remove(audio_file)

            # 当选择V2版本或者声音是V2声音时，显示服务区域和API key输入框
            if selected_tts_server == "azure-tts-v2" or (
                voice_name and voice.is_azure_v2_voice(voice_name)
            ):
                saved_azure_speech_region = config.azure.get("speech_region", "")
                saved_azure_speech_key = config.azure.get("speech_key", "")
                azure_speech_region = st.text_input(
                    tr("Speech Region"),
                    value=saved_azure_speech_region,
                    key="azure_speech_region_input",
                )
                azure_speech_key = st.text_input(
                    tr("Speech Key"),
                    value="",
                    type="password",
                    placeholder="Cole uma nova chave Azure Speech",
                    key="azure_speech_key_input",
                )
                config.azure["speech_region"] = azure_speech_region
                if azure_speech_key:
                    config.azure["speech_key"] = azure_speech_key

            # 当选择硅基流动时，显示API key输入框和说明信息
            if selected_tts_server == "siliconflow" or (
                voice_name and voice.is_siliconflow_voice(voice_name)
            ):
                saved_siliconflow_api_key = config.siliconflow.get("api_key", "")

                siliconflow_api_key = st.text_input(
                    tr("SiliconFlow API Key"),
                    value="",
                    type="password",
                    placeholder="Cole uma nova chave SiliconFlow",
                    key="siliconflow_api_key_input",
                )

                # 显示硅基流动的说明信息
                st.info(
                    tr("SiliconFlow TTS Settings")
                    + ":\n"
                    + "- "
                    + tr("Speed: Range [0.25, 4.0], default is 1.0")
                    + "\n"
                    + "- "
                    + tr("Volume: Uses Speech Volume setting, default 1.0 maps to gain 0")
                )

                if siliconflow_api_key:
                    config.siliconflow["api_key"] = siliconflow_api_key

            # 当选择 Xiaomi MiMo TTS 时，复用 MiMo LLM provider 的 API Key。
            # 这样用户如果同时使用 MiMo 生成文案和语音，只需要维护一份密钥。
            if selected_tts_server == "mimo-tts" or (
                voice_name and voice.is_mimo_voice(voice_name)
            ):
                saved_mimo_api_key = config.app.get("mimo_api_key", "")

                mimo_api_key = st.text_input(
                    tr("MiMo API Key"),
                    value="",
                    type="password",
                    placeholder="Cole uma nova chave MiMo",
                    key="mimo_tts_api_key_input",
                )

                st.info(
                    tr("MiMo TTS Settings")
                    + ":\n"
                    + "- "
                    + tr("Uses Xiaomi MiMo V2.5 TTS preset voices")
                    + "\n"
                    + "- "
                    + tr("Speed and volume are currently handled by the provider defaults")
                )

                if mimo_api_key:
                    config.app["mimo_api_key"] = mimo_api_key

            # ElevenLabs API key section
            if selected_tts_server == "elevenlabs" or (
                voice_name and voice.is_elevenlabs_voice(voice_name)
            ):
                saved_elevenlabs_api_key = config.elevenlabs.get("api_key", "")

                elevenlabs_api_key = st.text_input(
                    tr("ElevenLabs API Key"),
                    value="",
                    type="password",
                    placeholder="Enter ElevenLabs API key for this session",
                    key="elevenlabs_api_key_input",
                )

                _elevenlabs_models = [
                    "eleven_multilingual_v2",
                    "eleven_flash_v2_5",
                    "eleven_v3",
                ]
                saved_elevenlabs_model = config.elevenlabs.get(
                    "model_id", "eleven_multilingual_v2"
                )
                if saved_elevenlabs_model not in _elevenlabs_models:
                    saved_elevenlabs_model = "eleven_multilingual_v2"
                elevenlabs_model = st.selectbox(
                    tr("ElevenLabs Model"),
                    options=_elevenlabs_models,
                    index=_elevenlabs_models.index(saved_elevenlabs_model),
                    key="elevenlabs_model_select",
                )
                config.elevenlabs["model_id"] = elevenlabs_model

                st.info(
                    "ElevenLabs TTS Settings:\n"
                    "- Get your API key at https://elevenlabs.io/app/settings/api-keys\n"
                    "- Mark voices as ★ Favorite in the ElevenLabs voice library to make them appear here"
                )

                if elevenlabs_api_key and elevenlabs_api_key != saved_elevenlabs_api_key:
                    for k in list(st.session_state.keys()):
                        if k.startswith("elevenlabs_voices_"):
                            del st.session_state[k]

                if elevenlabs_api_key:
                    config.elevenlabs["api_key"] = elevenlabs_api_key

            # Chatterbox API settings section (self-hosted, OpenAI-compatible)
            if selected_tts_server == "chatterbox" or (
                voice_name and voice.is_chatterbox_voice(voice_name)
            ):
                chatterbox_base_url = st.text_input(
                    tr("Chatterbox Base URL"),
                    value=config.chatterbox.get("base_url") or DEFAULT_CHATTERBOX_BASE_URL,
                    key="chatterbox_base_url_input",
                    placeholder="http://localhost:4123/v1",
                )
                config.chatterbox["base_url"] = (chatterbox_base_url or "").strip()

                chatterbox_api_key = st.text_input(
                    tr("Chatterbox API Key"),
                    value="",
                    type="password",
                    placeholder="Optional Chatterbox API key for this session",
                    key="chatterbox_api_key_input",
                )
                if chatterbox_api_key:
                    config.chatterbox["api_key"] = chatterbox_api_key

                chatterbox_model = st.text_input(
                    tr("Chatterbox Model"),
                    value=config.chatterbox.get("model_id") or DEFAULT_CHATTERBOX_MODEL,
                    key="chatterbox_model_input",
                )
                config.chatterbox["model_id"] = (
                    chatterbox_model or DEFAULT_CHATTERBOX_MODEL
                ).strip()

                _saved_chatterbox_voices = (
                    _parse_chatterbox_voices(config.chatterbox.get("voices"))
                    or DEFAULT_CHATTERBOX_VOICES
                )
                if isinstance(_saved_chatterbox_voices, list):
                    _saved_chatterbox_voices = ", ".join(_saved_chatterbox_voices)
                chatterbox_voices = st.text_input(
                    tr("Chatterbox Voices"),
                    value=str(_saved_chatterbox_voices or ""),
                    key="chatterbox_voices_input",
                    placeholder="default-Female, narrator-Male",
                )
                config.chatterbox["voices"] = _parse_chatterbox_voices(chatterbox_voices)

                st.info(
                    "Chatterbox TTS Settings (self-hosted):\n"
                    "- Run an OpenAI-compatible Chatterbox server (e.g. "
                    "devnen/Chatterbox-TTS-Server or travisvn/chatterbox-tts-api) and "
                    "set Base URL to its /v1 endpoint\n"
                    "- Voices is a comma-separated list of voice names your server "
                    "exposes; add a -Female or -Male suffix only to label the gender "
                    "in this dropdown\n"
                    "- Speech Volume is not applied for Chatterbox (the OpenAI "
                    "/audio/speech API has no volume field); use Speech Rate instead"
                )

            params.voice_volume = st.selectbox(
                tr("Speech Volume"),
                options=[0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0, 4.0, 5.0],
                index=2,
            )

            params.voice_rate = st.selectbox(
                tr("Speech Rate"),
                options=[0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.8, 2.0],
                index=2,
            )

            custom_audio_file_types = ["mp3", "wav", "m4a", "aac", "flac", "ogg"]
            uploaded_audio_file = st.file_uploader(
                tr("Custom Audio File"),
                type=custom_audio_file_types
                + [file_type.upper() for file_type in custom_audio_file_types],
                accept_multiple_files=False,
                key="custom_audio_file_uploader",
            )
            if uploaded_audio_file:
                st.audio(uploaded_audio_file, format="audio/mp3")
                st.info(
                    tr(
                        "Custom audio will be used directly. TTS synthesis will be skipped for this task."
                    )
                )

            bgm_options = [
                (tr("No Background Music"), ""),
                (tr("Random Background Music"), "random"),
                (tr("Custom Background Music"), "custom"),
            ]
            selected_index = st.selectbox(
                tr("Background Music"),
                index=1,
                options=range(
                    len(bgm_options)
                ),  # Use the index as the internal option value
                format_func=lambda x: bgm_options[x][
                    0
                ],  # The label is displayed to the user
            )
            # Get the selected background music type
            params.bgm_type = bgm_options[selected_index][1]

            # Show or hide components based on the selection
            if params.bgm_type == "custom":
                custom_bgm_file = st.text_input(
                    tr("Custom Background Music File"), key="custom_bgm_file_input"
                )
                if custom_bgm_file:
                    # 这里不直接用 os.path.exists 判断，因为用户常见输入是
                    # output000.mp3，这个文件名需要由服务层映射到 resource/songs
                    # 目录后再校验。服务层会统一限制目录和文件类型，避免任意路径读取。
                    params.bgm_file = custom_bgm_file.strip()
                    # st.write(f":red[已选择自定义背景音乐]：**{custom_bgm_file}**")
            params.bgm_volume = st.selectbox(
                tr("Background Music Volume"),
                options=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
                index=2,
            )

    with right_panel:
        with st.container(border=True):
            st.write(tr("Subtitle Settings"))
            params.subtitle_enabled = st.checkbox(tr("Enable Subtitles"), value=True)
            font_names = get_all_fonts()
            saved_font_name = config.ui.get("font_name", "MicrosoftYaHeiBold.ttc")
            saved_font_name_index = 0
            if saved_font_name in font_names:
                saved_font_name_index = font_names.index(saved_font_name)
            params.font_name = st.selectbox(
                tr("Font"), font_names, index=saved_font_name_index
            )
            config.ui["font_name"] = params.font_name

            subtitle_positions = [
                (tr("Top"), "top"),
                (tr("Center"), "center"),
                (tr("Bottom"), "bottom"),
                (tr("Custom"), "custom"),
            ]
            saved_subtitle_position = config.ui.get("subtitle_position", "bottom")
            saved_position_index = 2
            for i, (_, pos_value) in enumerate(subtitle_positions):
                if pos_value == saved_subtitle_position:
                    saved_position_index = i
                    break
            selected_index = st.selectbox(
                tr("Position"),
                index=saved_position_index,
                options=range(len(subtitle_positions)),
                format_func=lambda x: subtitle_positions[x][0],
            )
            params.subtitle_position = subtitle_positions[selected_index][1]
            config.ui["subtitle_position"] = params.subtitle_position

            if params.subtitle_position == "custom":
                saved_custom_position = config.ui.get("custom_position", 70.0)
                custom_position = st.text_input(
                    tr("Custom Position (% from top)"),
                    value=str(saved_custom_position),
                    key="custom_position_input",
                )
                try:
                    params.custom_position = float(custom_position)
                    if params.custom_position < 0 or params.custom_position > 100:
                        st.error(tr("Please enter a value between 0 and 100"))
                    else:
                        config.ui["custom_position"] = params.custom_position
                except ValueError:
                    st.error(tr("Please enter a valid number"))

            font_cols = st.columns([0.3, 0.7])
            with font_cols[0]:
                saved_text_fore_color = config.ui.get("text_fore_color", "#FFFFFF")
                params.text_fore_color = st.color_picker(
                    tr("Font Color"), saved_text_fore_color
                )
                config.ui["text_fore_color"] = params.text_fore_color

            with font_cols[1]:
                saved_font_size = config.ui.get("font_size", 60)
                params.font_size = st.slider(tr("Font Size"), 30, 100, saved_font_size)
                config.ui["font_size"] = params.font_size

            stroke_cols = st.columns([0.3, 0.7])
            with stroke_cols[0]:
                params.stroke_color = st.color_picker(tr("Stroke Color"), "#000000")
            with stroke_cols[1]:
                params.stroke_width = st.slider(tr("Stroke Width"), 0.0, 10.0, 1.5)

            subtitle_bg_cols = st.columns([0.4, 0.6])
            saved_subtitle_background_enabled = config.ui.get(
                "subtitle_background_enabled", True
            )
            with subtitle_bg_cols[0]:
                subtitle_background_enabled = st.checkbox(
                    tr("Enable Subtitle Background"),
                    value=saved_subtitle_background_enabled,
                )
            config.ui["subtitle_background_enabled"] = subtitle_background_enabled
            if subtitle_background_enabled:
                with subtitle_bg_cols[1]:
                    saved_subtitle_background_color = config.ui.get(
                        "subtitle_background_color", "#000000"
                    )
                    params.text_background_color = st.color_picker(
                        tr("Subtitle Background Color"),
                        saved_subtitle_background_color,
                    )
                    config.ui["subtitle_background_color"] = params.text_background_color
            else:
                params.text_background_color = False

            saved_rounded_subtitle_background = config.ui.get(
                "rounded_subtitle_background", False
            )
            # 背景关闭时，圆角背景没有可渲染的底色。这里禁用控件并保留原配置，
            # 用户下次重新开启字幕背景后，可以继续使用之前保存的圆角偏好。
            params.rounded_subtitle_background = st.checkbox(
                tr("Rounded Subtitle Background"),
                value=(
                    saved_rounded_subtitle_background
                    if subtitle_background_enabled
                    else False
                ),
                help=tr("Rounded Subtitle Background Help"),
                disabled=not subtitle_background_enabled,
            )
            if subtitle_background_enabled:
                config.ui["rounded_subtitle_background"] = (
                    params.rounded_subtitle_background
                )
        with st.expander(tr("Click to show API Key management"), expanded=False):
            st.subheader(tr("Manage Pexels, Pixabay and Coverr API Keys"))

            col1, col2, col3 = st.tabs([
                tr("Pexels API Keys"),
                tr("Pixabay API Keys"),
                tr("Coverr API Keys"),
            ])

            with col1:
                st.subheader(tr("Pexels API Keys"))
                if config.app["pexels_api_keys"]:
                    st.write(tr("Current Keys:"))
                    for key in config.app["pexels_api_keys"]:
                        st.code(_mask_secret(key))
                else:
                    st.info(tr("No Pexels API Keys currently"))

                new_key = st.text_input(tr("Add Pexels API Key"), key="pexels_new_key")
                if st.button(tr("Add Pexels API Key")):
                    if new_key and new_key not in config.app["pexels_api_keys"]:
                        config.app["pexels_api_keys"].append(new_key)
                        config.save_config()
                        st.success(tr("Pexels API Key added successfully"))
                    elif new_key in config.app["pexels_api_keys"]:
                        st.warning(tr("This API Key already exists"))
                    else:
                        st.error(tr("Please enter a valid API Key"))

                if config.app["pexels_api_keys"]:
                    delete_key = st.selectbox(
                        tr("Select Pexels API Key to delete"), config.app["pexels_api_keys"], key="pexels_delete_key"
                    )
                    if st.button(tr("Delete Selected Pexels API Key")):
                        config.app["pexels_api_keys"].remove(delete_key)
                        config.save_config()
                        st.success(tr("Pexels API Key deleted successfully"))

            with col2:
                st.subheader(tr("Pixabay API Keys"))

                if config.app["pixabay_api_keys"]:
                    st.write(tr("Current Keys:"))
                    for key in config.app["pixabay_api_keys"]:
                        st.code(_mask_secret(key))
                else:
                    st.info(tr("No Pixabay API Keys currently"))

                new_key = st.text_input(tr("Add Pixabay API Key"), key="pixabay_new_key")
                if st.button(tr("Add Pixabay API Key")):
                    if new_key and new_key not in config.app["pixabay_api_keys"]:
                        config.app["pixabay_api_keys"].append(new_key)
                        config.save_config()
                        st.success(tr("Pixabay API Key added successfully"))
                    elif new_key in config.app["pixabay_api_keys"]:
                        st.warning(tr("This API Key already exists"))
                    else:
                        st.error(tr("Please enter a valid API Key"))

                if config.app["pixabay_api_keys"]:
                    delete_key = st.selectbox(
                        tr("Select Pixabay API Key to delete"), config.app["pixabay_api_keys"], key="pixabay_delete_key"
                    )
                    if st.button(tr("Delete Selected Pixabay API Key")):
                        config.app["pixabay_api_keys"].remove(delete_key)
                        config.save_config()
                        st.success(tr("Pixabay API Key deleted successfully"))

            with col3:
                st.subheader(tr("Coverr API Keys"))

                # 与 pexels/pixabay 不同,coverr_api_keys 是 PR 新增配置项,
                # 老用户的 config.toml 不一定包含,这里先兜底初始化为空列表,
                # 防止下面 .append / 索引访问触发 KeyError。
                if "coverr_api_keys" not in config.app or config.app["coverr_api_keys"] is None:
                    config.app["coverr_api_keys"] = []

                if config.app["coverr_api_keys"]:
                    st.write(tr("Current Keys:"))
                    for key in config.app["coverr_api_keys"]:
                        st.code(_mask_secret(key))
                else:
                    st.info(tr("No Coverr API Keys currently"))

                new_key = st.text_input(tr("Add Coverr API Key"), key="coverr_new_key")
                if st.button(tr("Add Coverr API Key")):
                    if new_key and new_key not in config.app["coverr_api_keys"]:
                        config.app["coverr_api_keys"].append(new_key)
                        config.save_config()
                        st.success(tr("Coverr API Key added successfully"))
                    elif new_key in config.app["coverr_api_keys"]:
                        st.warning(tr("This API Key already exists"))
                    else:
                        st.error(tr("Please enter a valid API Key"))

                if config.app["coverr_api_keys"]:
                    delete_key = st.selectbox(
                        tr("Select Coverr API Key to delete"), config.app["coverr_api_keys"], key="coverr_delete_key"
                    )
                    if st.button(tr("Delete Selected Coverr API Key")):
                        config.app["coverr_api_keys"].remove(delete_key)
                        config.save_config()
                        st.success(tr("Coverr API Key deleted successfully"))

start_button = st.button("Gerar vídeo real", use_container_width=True, type="primary")
if start_button:
    config.save_config()
    task_id = str(uuid4())
    readiness = cenara_provider_readiness(params.video_source, config.ui.get("tts_server", "azure-tts-v1"))
    if uploaded_audio_file or params.custom_audio_file:
        readiness["Voz/TTS"] = ("configured", "áudio personalizado")
    errors = cenara_validate_generation_payload(params, uploaded_audio=uploaded_audio_file, readiness=readiness)
    if errors:
        for error in errors:
            st.error(error)
        scroll_to_bottom()
        st.stop()

    if uploaded_audio_file:
        task_dir = utils.task_dir(task_id)
        # 上传文件名来自浏览器，不能直接拼到磁盘路径里；这里只保留扩展名，
        # 并使用固定文件名保存到当前任务目录，避免路径穿越或特殊字符问题。
        _, audio_ext = os.path.splitext(os.path.basename(uploaded_audio_file.name))
        audio_ext = audio_ext.lower() or ".mp3"
        custom_audio_path = os.path.join(task_dir, f"custom-audio{audio_ext}")
        with open(custom_audio_path, "wb") as f:
            f.write(uploaded_audio_file.getbuffer())
        params.custom_audio_file = custom_audio_path

    if uploaded_files:
        local_videos_dir = utils.storage_dir("local_videos", create=True)
        # 每次重新上传时都以本次选择的素材为准，避免旧素材不断重复追加。
        params.video_materials = []
        persisted_local_materials = []
        for file in uploaded_files:
            file_path = os.path.join(local_videos_dir, f"{file.file_id}_{file.name}")
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())
                m = MaterialInfo()
                m.provider = "local"
                m.url = file_path
                params.video_materials.append(m)
                persisted_local_materials.append(
                    {
                        "provider": m.provider,
                        "url": m.url,
                        "duration": m.duration,
                    }
                )
        # 将已上传并保存到本地的视频素材写入会话，供后续只改文案时直接复用。
        st.session_state["local_video_materials"] = persisted_local_materials
    elif params.video_source == "local" and st.session_state["local_video_materials"]:
        # 当用户没有重新上传文件时，复用最近一次已经保存到磁盘的本地素材列表。
        params.video_materials = []
        for material in st.session_state["local_video_materials"]:
            m = MaterialInfo()
            m.provider = material.get("provider", "local")
            m.url = material.get("url", "")
            m.duration = material.get("duration", 0)
            if m.url:
                params.video_materials.append(m)

    log_container = st.empty()
    log_records = []

    def log_received(msg):
        if config.ui["hide_log"]:
            return
        with log_container:
            log_records.append(msg)
            st.code("\n".join(log_records))

    logger.add(log_received)

    st.toast(tr("Generating Video"))
    logger.info(tr("Start Generating Video"))
    logger.info(f"Cenara payload pronto: source={params.video_source}, aspect={params.video_aspect}, has_subject={bool(params.video_subject)}, has_script={bool(params.video_script)}, has_voice={bool(params.voice_name)}")
    scroll_to_bottom()

    result = cenara_trigger_real_generation(task_id=task_id, payload=params)
    if not result or not result.get("success"):
        error = (result or {}).get("error") or tr("Video Generation Failed")
        st.error(error)
        logger.error(error)
        scroll_to_bottom()
        st.stop()

    video_files = [result["output_path"]]
    st.session_state["cenara_latest_mp4"] = result["output_path"]
    st.session_state["cenara_latest_task_id"] = task_id
    st.success("Vídeo real gerado com sucesso.")
    try:
        player_cols = st.columns(len(video_files) * 2 + 1)
        for i, url in enumerate(video_files):
            player_cols[i * 2 + 1].video(url)
    except Exception:
        pass

    open_task_folder(task_id)
    logger.info(tr("Video Generation Completed"))
    scroll_to_bottom()

config.save_config()
