"""Official Cenara product shell.

Keeps the operational generator intact while presenting a clean, curated home
experience inspired by premium creative SaaS products.
"""

from __future__ import annotations

import html
import os
from pathlib import Path

import streamlit as st


STYLE_CARDS = [
    ("Cinemático", "Impacto visual e narrativo", "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=900&q=80"),
    ("Comercial", "Ideal para produtos", "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=80"),
    ("Institucional", "Credibilidade e autoridade", "https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=900&q=80"),
    ("Redes Sociais", "Rápido e envolvente", "https://images.unsplash.com/photo-1531297484001-80022131f5a1?auto=format&fit=crop&w=900&q=80"),
    ("Educativo", "Ensina com clareza", "https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=900&q=80"),
    ("Animação", "Explique com criatividade", "https://images.unsplash.com/photo-1550745165-9bc0b252726f?auto=format&fit=crop&w=900&q=80"),
]

TEMPLATES = [
    ("LANÇAMENTO", "00:30", "Lançamento de Produto", "Moderno e persuasivo", "https://images.unsplash.com/photo-1558655146-d09347e92766?auto=format&fit=crop&w=900&q=80"),
    ("PROMOÇÃO", "00:15", "Oferta Especial", "Aumente suas conversões", "https://images.unsplash.com/photo-1529139574466-a303027c1d8b?auto=format&fit=crop&w=900&q=80"),
    ("SUA MARCA", "00:45", "Institucional", "Conte sua história", "https://images.unsplash.com/photo-1556761175-b413da4baf72?auto=format&fit=crop&w=900&q=80"),
    ("DICAS RÁPIDAS", "00:20", "Conteúdo para Redes", "Engajamento consistente", "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=900&q=80"),
    ("TUTORIAL", "00:40", "Passo a Passo", "Ensine de forma simples", "https://images.unsplash.com/photo-1516321497487-e288fb19713f?auto=format&fit=crop&w=900&q=80"),
    ("ANTES / DEPOIS", "00:25", "Transformação", "Mostre resultados reais", "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=900&q=80"),
]

INSPO = [
    ("Liberdade em movimento", "1.2k", "https://images.unsplash.com/photo-1502680390469-be75c86b636f?auto=format&fit=crop&w=900&q=80"),
    ("Beleza real", "842", "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=900&q=80"),
    ("Pequenas grandes viagens", "2.1k", "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=900&q=80"),
    ("Mais que café", "976", "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=900&q=80"),
    ("Vida é agora", "1.4k", "https://images.unsplash.com/photo-1518717758536-85ae29035b6d?auto=format&fit=crop&w=900&q=80"),
    ("Cidades que inspiram", "2.3k", "https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?auto=format&fit=crop&w=900&q=80"),
]


def inject_official_theme() -> None:
    st.markdown(
        r"""
<style>
:root {
  --cz-bg:#050b12; --cz-bg2:#07121e; --cz-panel:#0b1623;
  --cz-border:rgba(148,163,184,.16); --cz-text:#f8fafc;
  --cz-muted:#94a3b8; --cz-cyan:#12d7f0; --cz-blue:#3b82f6; --cz-orange:#ff8a3d;
}
html,body,[class*="css"]{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}
.stApp{background:linear-gradient(180deg,#050b12 0%,#07111c 50%,#040910 100%) !important;}
.block-container{max-width:1700px !important;padding:0 !important;margin:0 !important;}
[data-testid="stHeader"],[data-testid="stToolbar"]{background:transparent !important;}
.cz-shell{min-height:100vh;color:var(--cz-text);display:grid;grid-template-columns:238px minmax(0,1fr);}
.cz-side{position:sticky;top:0;height:100vh;padding:24px 18px;border-right:1px solid var(--cz-border);background:linear-gradient(180deg,#07111b 0%,#050a10 100%);box-sizing:border-box;}
.cz-brand{display:flex;align-items:center;gap:12px;margin:2px 10px 30px;}
.cz-mark{width:32px;height:32px;display:grid;place-items:center;border-radius:10px;background:conic-gradient(from 220deg,var(--cz-cyan),var(--cz-blue),#7c3aed,var(--cz-cyan));clip-path:polygon(0 0,100% 50%,0 100%);filter:drop-shadow(0 0 14px rgba(18,215,240,.3));}
.cz-name{font-size:26px;font-weight:900;letter-spacing:.12em}.cz-tagline{font-size:9px;letter-spacing:.16em;color:#a8b5c4;margin-top:2px;}
.cz-nav{display:grid;gap:8px}.cz-nav a{display:flex;align-items:center;gap:12px;color:#c6d2df;text-decoration:none;padding:12px 14px;border-radius:11px;font-weight:700;font-size:14px;border:1px solid transparent;}
.cz-nav a:hover,.cz-nav a.active{color:#fff;background:linear-gradient(90deg,rgba(20,67,103,.68),rgba(20,41,62,.65));border-color:rgba(56,189,248,.16);}
.cz-nav .ico{width:22px;text-align:center;color:#b6c5d5}.cz-pro{position:absolute;left:18px;right:18px;bottom:18px;padding:18px;border:1px solid rgba(56,189,248,.22);border-radius:18px;background:linear-gradient(145deg,rgba(22,48,70,.75),rgba(63,34,24,.46));}
.cz-pro b{color:#54d8ff}.cz-pro p{color:#aebdcc;font-size:13px;line-height:1.55}.cz-upgrade{display:block;text-align:center;padding:12px;border-radius:12px;color:#fff;text-decoration:none;font-weight:800;background:linear-gradient(90deg,#00d4ff,#2563eb,#ff8a3d);}
.cz-main{min-width:0}.cz-top{height:64px;border-bottom:1px solid var(--cz-border);display:flex;align-items:center;justify-content:space-between;padding:0 28px;box-sizing:border-box;background:rgba(4,10,17,.82);backdrop-filter:blur(16px);}
.cz-search{width:min(580px,52vw);padding:11px 15px;border:1px solid var(--cz-border);border-radius:11px;background:#0c1724;color:#91a1b3;font-size:14px}.cz-user{display:flex;align-items:center;gap:10px}.cz-avatar{width:38px;height:38px;border-radius:50%;background:linear-gradient(135deg,#0ea5e9,#7c3aed);display:grid;place-items:center;font-weight:900}.cz-user small{display:block;color:#45cfff;margin-top:2px}
.cz-content{padding:16px 22px 34px}.cz-hero{min-height:268px;display:grid;grid-template-columns:minmax(0,.96fr) minmax(460px,1.5fr);overflow:hidden;border-bottom:1px solid var(--cz-border);background:#06101a;}
.cz-hero-copy{padding:26px 26px 22px;display:flex;flex-direction:column;justify-content:center}.cz-hero h1{font-size:clamp(36px,4vw,60px);line-height:.98;letter-spacing:-.05em;margin:0 0 16px;color:#fff}.cz-gradient{background:linear-gradient(90deg,#12d7f0,#4f8df9);-webkit-background-clip:text;background-clip:text;color:transparent}.cz-hero p{color:#c1ccd8;font-size:16px;max-width:620px;line-height:1.5}.cz-cta{display:inline-flex;align-items:center;gap:14px;width:max-content;margin-top:10px;padding:14px 22px;border-radius:16px;background:linear-gradient(90deg,#00cff5,#2563eb,#ff8b42);color:#fff;text-decoration:none;font-weight:900;box-shadow:0 12px 38px rgba(18,215,240,.18);}
.cz-hero-art{position:relative;background:
linear-gradient(90deg,#06101a 0%,rgba(6,16,26,.08) 38%,rgba(6,16,26,.12) 100%),
url('https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1600&q=85') center 46%/cover no-repeat;}
.cz-hero-art:after{content:"IDEIAS\\A MOVEM\\A O AMANHÃ";white-space:pre;position:absolute;right:9%;top:26%;font-size:20px;letter-spacing:.32em;line-height:1.7;color:#fff;text-shadow:0 2px 30px #000;}
.cz-flow{display:grid;grid-template-columns:repeat(8,1fr);gap:0;margin:0;border:1px solid var(--cz-border);border-radius:16px;overflow:hidden;background:#091420}.cz-flow div{padding:16px 12px;border-right:1px solid var(--cz-border);min-height:72px}.cz-flow div:last-child{border-right:0}.cz-flow b{display:block;font-size:13px}.cz-flow small{color:#8393a5;font-size:10px}.cz-flow span{display:inline-grid;place-items:center;width:30px;height:30px;border:1px solid rgba(148,163,184,.2);border-radius:9px;margin-bottom:7px;background:#101d2b}
.cz-section{margin-top:18px}.cz-section-head{display:flex;align-items:end;justify-content:space-between;margin-bottom:10px}.cz-section-head h2{font-size:21px;margin:0}.cz-section-head p{display:inline;color:#8393a5;font-size:12px;margin-left:10px}.cz-more{color:#42cfff;font-size:12px;text-decoration:none;font-weight:800}
.cz-grid6{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px}.cz-card{position:relative;min-width:0;border:1px solid var(--cz-border);border-radius:12px;overflow:hidden;background:#091420}.cz-thumb{height:118px;background-size:cover;background-position:center;position:relative}.cz-thumb:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,transparent 35%,rgba(2,8,15,.92) 100%)}.cz-card-body{padding:9px 10px 11px}.cz-card b{font-size:13px}.cz-card small{color:#8797aa;display:block;margin-top:3px;font-size:11px}.cz-overlay{position:absolute;left:10px;bottom:10px;z-index:2;color:#fff}.cz-duration{position:absolute;right:8px;bottom:8px;z-index:2;font-size:10px;background:rgba(2,8,15,.8);border:1px solid rgba(255,255,255,.18);padding:3px 6px;border-radius:6px}.cz-likes{position:absolute;right:8px;bottom:8px;z-index:2;font-size:10px;color:#fff}
.cz-studio-head{padding:18px 24px 8px;border-bottom:1px solid var(--cz-border);background:#06101a}.cz-studio-head h1{margin:0;font-size:28px}.cz-studio-head p{margin:6px 0 0;color:#8ea0b4}.cz-back{display:inline-block;margin-bottom:12px;color:#49d3ff;text-decoration:none;font-weight:800}
@media(max-width:1200px){.cz-grid6{grid-template-columns:repeat(3,1fr)}.cz-flow{grid-template-columns:repeat(4,1fr)}.cz-hero{grid-template-columns:1fr}.cz-hero-art{min-height:240px}}
@media(max-width:850px){.cz-shell{grid-template-columns:1fr}.cz-side{position:relative;height:auto}.cz-pro{position:relative;left:auto;right:auto;bottom:auto;margin-top:16px}.cz-top{padding:0 14px}.cz-search{width:64vw}.cz-content{padding:12px}.cz-grid6{grid-template-columns:repeat(2,1fr)}.cz-flow{grid-template-columns:repeat(2,1fr)}}
</style>
""",
        unsafe_allow_html=True,
    )


def _sidebar(active: str = "home") -> str:
    items = [
        ("home", "⌂", "Início", "?view=home"),
        ("projects", "▣", "Projetos", "?view=home#projetos"),
        ("studio", "▷", "Criar Vídeo", "?view=studio"),
        ("library", "▤", "Biblioteca", "?view=home#biblioteca"),
        ("models", "▦", "Modelos", "?view=home#modelos"),
        ("media", "▧", "Mídia", "?view=studio"),
        ("settings", "⚙", "Configurações", "?view=studio#config"),
    ]
    nav = "".join(
        f'<a class="{"active" if key == active else ""}" href="{href}"><span class="ico">{ico}</span>{label}</a>'
        for key, ico, label, href in items
    )
    return f"""
    <aside class="cz-side">
      <div class="cz-brand"><div class="cz-mark"></div><div><div class="cz-name">CENARA</div><div class="cz-tagline">AI VIDEOS. BIGGER IDEAS.</div></div></div>
      <nav class="cz-nav">{nav}</nav>
      <div class="cz-pro"><b>✦ Cenara Studio</b><p>Criação audiovisual com IA, modelos abertos e direção inteligente.</p><a class="cz-upgrade" href="?view=studio">Criar agora</a></div>
    </aside>
    """


def _topbar() -> str:
    return """
    <header class="cz-top">
      <div class="cz-search">⌕ &nbsp; Buscar modelos, estilos, projetos ou inspiração...</div>
      <div class="cz-user"><span>♢</span><div class="cz-avatar">GX</div><div><b>Operador XPeX</b><small>Cenara Studio</small></div></div>
    </header>
    """


def _cards_html(items, template=False, inspiration=False) -> str:
    cards = []
    for item in items:
        if template:
            label, duration, title, subtitle, image = item
            cards.append(f"""<article class="cz-card"><div class="cz-thumb" style="background-image:url('{image}')"><div class="cz-overlay"><b>{html.escape(label)}</b></div><div class="cz-duration">{duration}</div></div><div class="cz-card-body"><b>{html.escape(title)}</b><small>{html.escape(subtitle)}</small></div></article>""")
        elif inspiration:
            title, likes, image = item
            cards.append(f"""<article class="cz-card"><div class="cz-thumb" style="background-image:url('{image}')"><div class="cz-overlay"><b>{html.escape(title)}</b></div><div class="cz-likes">♡ {likes}</div></div></article>""")
        else:
            title, subtitle, image = item
            cards.append(f"""<article class="cz-card"><div class="cz-thumb" style="background-image:url('{image}')"><div class="cz-overlay"><b>{html.escape(title)}</b><small style="color:#d6e0ea">{html.escape(subtitle)}</small></div></div></article>""")
    return "".join(cards)


def render_official_home() -> None:
    flow = [
        ("◉", "Ideia", "Descreva seu objetivo"), ("▤", "Roteiro", "A IA cria o roteiro"),
        ("▧", "Mídia", "Imagens e clipes"), ("◖", "Voz", "Vozes realistas"),
        ("CC", "Legendas", "Automáticas"), ("✂", "Montagem", "Edição inteligente"),
        ("▶", "Prévia", "Revise e ajuste"), ("⇧", "Exportar", "Baixe e compartilhe"),
    ]
    flow_html = "".join(f"<div><span>{ico}</span><b>{title}</b><small>{sub}</small></div>" for ico,title,sub in flow)
    st.markdown(
        f"""
<div class="cz-shell">
  {_sidebar("home")}
  <main class="cz-main">
    {_topbar()}
    <section class="cz-hero">
      <div class="cz-hero-copy">
        <h1>Cenara transforma<br>briefs em vídeos<br><span class="cz-gradient">prontos para vender.</span></h1>
        <p>Da ideia à exportação, tudo em um só lugar. Crie vídeos profissionais com IA, modelos abertos e uma experiência de produção limpa.</p>
        <a class="cz-cta" href="?view=studio">＋ &nbsp; Criar meu primeiro vídeo &nbsp; →</a>
      </div>
      <div class="cz-hero-art"></div>
    </section>
    <div class="cz-content">
      <div class="cz-flow">{flow_html}</div>
      <section class="cz-section" id="modelos"><div class="cz-section-head"><div><h2>Estilos de vídeo <p>Escolha um estilo e comece mais rápido.</p></h2></div><a class="cz-more" href="?view=studio">Ver todos →</a></div><div class="cz-grid6">{_cards_html(STYLE_CARDS)}</div></section>
      <section class="cz-section"><div class="cz-section-head"><div><h2>Modelos em destaque <p>Estruturas prontas para acelerar sua produção.</p></h2></div><a class="cz-more" href="?view=studio">Ver todos →</a></div><div class="cz-grid6">{_cards_html(TEMPLATES, template=True)}</div></section>
      <section class="cz-section" id="biblioteca"><div class="cz-section-head"><div><h2>Inspiração da comunidade <p>Referências visuais para destravar novas ideias.</p></h2></div><a class="cz-more" href="?view=studio">Ver mais inspiração →</a></div><div class="cz-grid6">{_cards_html(INSPO, inspiration=True)}</div></section>
    </div>
  </main>
</div>
""",
        unsafe_allow_html=True,
    )


def render_official_studio_header() -> None:
    st.markdown(
        f"""
<div class="cz-shell" style="min-height:auto">
  {_sidebar("studio")}
  <main class="cz-main">
    {_topbar()}
    <section class="cz-studio-head"><a class="cz-back" href="?view=home">← Voltar ao início</a><h1>Criar vídeo</h1><p>Direção, roteiro, mídia, voz, legendas, montagem e exportação em um fluxo único.</p></section>
  </main>
</div>
""",
        unsafe_allow_html=True,
    )
