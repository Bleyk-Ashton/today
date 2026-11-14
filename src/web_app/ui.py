"""Estilos y componentes visuales compartidos por todas las páginas.

Todo texto dinámico que se inserta como HTML pasa por ``html.escape`` para
evitar XSS: solo el CSS y la estructura son HTML fijo escrito aquí.
"""

from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path

import streamlit as st

APP_NAME = "Site"
ASSETS = Path(__file__).resolve().parent / "assets"

_CSS = """
<style>
/* ---------- Layout ---------- */
.block-container { max-width: 1000px; padding-top: 2.2rem; padding-bottom: 1rem; }
[data-testid="stSidebarNav"] a span { font-weight: 500; }

/* ---------- Hero ---------- */
.ui-hero {
  background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 55%, #C026D3 100%);
  color: #fff; border-radius: 22px; padding: 2.6rem 2.4rem 2.4rem;
  box-shadow: 0 24px 48px -24px rgba(79, 70, 229, .65);
  margin-bottom: 1.6rem; position: relative; overflow: hidden;
}
.ui-hero::after {
  content: ""; position: absolute; right: -60px; top: -60px; width: 260px; height: 260px;
  border-radius: 50%; background: rgba(255, 255, 255, .08);
}
.ui-hero .eyebrow {
  display: inline-block; background: rgba(255, 255, 255, .18); padding: .3rem .8rem;
  border-radius: 999px; font-size: .75rem; font-weight: 600; letter-spacing: .06em;
  text-transform: uppercase; margin-bottom: 1rem;
}
.ui-hero .title {
  font-family: "Plus Jakarta Sans", sans-serif; font-size: 2.5rem; font-weight: 800;
  line-height: 1.12; margin: 0 0 .7rem; max-width: 720px;
}
.ui-hero .subtitle { font-size: 1.08rem; opacity: .9; max-width: 640px; line-height: 1.55; }

/* ---------- Encabezado de página ---------- */
.ui-header { display: flex; align-items: center; gap: 1rem; margin: .2rem 0 1.4rem; }
.ui-header .icon {
  font-size: 1.7rem; width: 3.2rem; height: 3.2rem; flex: none; display: flex;
  align-items: center; justify-content: center; border-radius: 14px;
  background: linear-gradient(135deg, #EEF2FF, #E0E7FF); box-shadow: inset 0 0 0 1px #C7D2FE;
}
.ui-header .title {
  font-family: "Plus Jakarta Sans", sans-serif; font-size: 1.75rem; font-weight: 800;
  color: #0F172A; line-height: 1.2;
}
.ui-header .subtitle { color: #64748B; font-size: .95rem; margin-top: .15rem; }

/* ---------- Tarjetas ---------- */
.ui-card {
  background: #fff; border: 1px solid #E2E8F0; border-radius: 18px; padding: 1.35rem;
  height: 100%; box-shadow: 0 1px 2px rgba(15, 23, 42, .04);
  transition: transform .15s ease, box-shadow .15s ease;
}
.ui-card:hover { transform: translateY(-2px); box-shadow: 0 12px 24px -14px rgba(15, 23, 42, .25); }
.ui-card .icon {
  font-size: 1.4rem; width: 2.8rem; height: 2.8rem; display: flex; align-items: center;
  justify-content: center; border-radius: 12px; background: #EEF2FF; margin-bottom: .85rem;
}
.ui-card .title { font-weight: 700; font-size: 1.02rem; color: #0F172A; margin-bottom: .3rem; }
.ui-card .text { color: #475569; font-size: .92rem; line-height: 1.5; }
.ui-step { font-size: .75rem; font-weight: 700; color: #4F46E5; letter-spacing: .06em; margin-bottom: .3rem; }

/* ---------- Campos de perfil ---------- */
.ui-field { padding: .45rem 0; border-bottom: 1px dashed #E2E8F0; }
.ui-field:last-child { border-bottom: none; }
.ui-field .k { font-size: .75rem; color: #64748B; text-transform: uppercase; letter-spacing: .04em; }
.ui-field .v { font-size: .97rem; color: #0F172A; font-weight: 500; word-break: break-word; }

/* ---------- Badges ---------- */
.ui-badge {
  display: inline-block; padding: .2rem .7rem; border-radius: 999px; font-size: .78rem;
  font-weight: 600; background: #EEF2FF; color: #4338CA;
}
.ui-badge.admin { background: #FEF3C7; color: #92400E; }

/* ---------- Formularios ---------- */
[data-testid="stForm"] {
  background: #fff; border: 1px solid #E2E8F0 !important; border-radius: 18px;
  padding: 1.4rem 1.5rem; box-shadow: 0 10px 30px -22px rgba(15, 23, 42, .35);
}
.ui-section {
  font-weight: 700; color: #0F172A; margin: .9rem 0 .2rem; font-size: .98rem;
  display: flex; align-items: center; gap: .45rem;
}

/* ---------- Pestañas ---------- */
[data-baseweb="tab-list"] { gap: .4rem; }
[data-baseweb="tab"] { font-weight: 600; }

/* ---------- Pie de página ---------- */
.ui-footer {
  text-align: center; color: #94A3B8; font-size: .82rem; padding: 2.2rem 0 .6rem;
  border-top: 1px solid #E2E8F0; margin-top: 2.4rem;
}
</style>
"""


def setup_page() -> None:
    """Configuración común: título de pestaña, logo y CSS."""
    st.set_page_config(
        page_title=f"{APP_NAME} · Banca segura",
        page_icon=str(ASSETS / "icon.png"),
        layout="centered",
    )
    st.logo(str(ASSETS / "logo.png"), icon_image=str(ASSETS / "icon.png"), size="large")
    st.html(_CSS)


def hero(title: str, subtitle: str = "", eyebrow: str = "") -> None:
    eyebrow_html = f'<div class="eyebrow">{escape(eyebrow)}</div>' if eyebrow else ""
    st.html(
        f'<div class="ui-hero">{eyebrow_html}'
        f'<div class="title">{escape(title)}</div>'
        f'<div class="subtitle">{escape(subtitle)}</div></div>'
    )


def page_header(icon: str, title: str, subtitle: str = "") -> None:
    st.html(
        f'<div class="ui-header"><div class="icon">{escape(icon)}</div><div>'
        f'<div class="title">{escape(title)}</div>'
        f'<div class="subtitle">{escape(subtitle)}</div></div></div>'
    )


def card(icon: str, title: str, text: str, step: str = "") -> None:
    step_html = f'<div class="ui-step">{escape(step)}</div>' if step else ""
    st.html(
        f'<div class="ui-card">{step_html}<div class="icon">{escape(icon)}</div>'
        f'<div class="title">{escape(title)}</div><div class="text">{escape(text)}</div></div>'
    )


def cards(items: list[tuple[str, str, str]], steps: bool = False) -> None:
    cols = st.columns(len(items))
    for i, (col, (icon, title, text)) in enumerate(zip(cols, items), start=1):
        with col:
            card(icon, title, text, step=f"PASO {i}" if steps else "")


def section(icon: str, title: str) -> None:
    st.html(f'<div class="ui-section">{escape(icon)} {escape(title)}</div>')


def fields(data: dict[str, object]) -> None:
    """Lista de pares clave/valor (escapados: pueden venir del usuario)."""
    rows = "".join(
        f'<div class="ui-field"><div class="k">{escape(str(k))}</div>'
        f'<div class="v">{escape(str(v))}</div></div>'
        for k, v in data.items()
    )
    st.html(rows)


def badge(text: str, admin: bool = False) -> str:
    cls = "ui-badge admin" if admin else "ui-badge"
    return f'<span class="{cls}">{escape(text)}</span>'


def footer() -> None:
    st.html(
        f'<div class="ui-footer">© {date.today().year} {escape(APP_NAME)} · '
        "Protegido con contraseña Argon2id, OTP y cifrado de datos sensibles</div>"
    )
