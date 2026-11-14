from html import escape
from pathlib import Path

import streamlit as st

from web_app import auth_service
from web_app.auth_service import ROLE_ADMIN
from web_app.guards import current_role, require_login

WELCOME_GIF = Path(__file__).resolve().parents[1] / "assets" / "welcome.gif"

user = require_login()
profile = auth_service.get_my_profile(user["id"])
if profile is None:
    st.session_state.clear()
    st.rerun()

first_name = (profile["Nombre"].split() or ["usuario"])[0].capitalize()
st.title(f"👋 ¡Hola, {first_name}!")

left, right = st.columns([1, 1], vertical_alignment="center")
with left:
    if WELCOME_GIF.is_file():
        st.image(str(WELCOME_GIF), width="stretch")
with right:
    st.markdown(
        "Bienvenido a **Site**. Tu cuenta está protegida con:\n\n"
        "- 🔑 Contraseña robusta (guardada solo como hash Argon2id)\n"
        "- 📱 Código OTP de un solo uso\n"
        "- 🔒 Datos personales, de salud y financieros cifrados\n"
    )
    st.caption(f"Último acceso: {profile['Último acceso']}")
    if current_role() == ROLE_ADMIN:
        st.info("🛡️ Tienes rol de **administrador**: verás la sección *Administración* en el menú.")

st.divider()
st.subheader("Mi información")
st.caption("Solo tú puedes ver estos datos. Los más sensibles se muestran parcialmente.")

sections = {
    "👤 Datos personales": ["Nombre", "Correo", "Documento", "Fecha de nacimiento", "Teléfono", "Dirección"],
    "🩺 Salud": ["Tipo de sangre", "EPS / aseguradora", "Condiciones médicas"],
    "💳 Datos crediticios": ["Tarjeta", "Vencimiento"],
}
cols = st.columns(len(sections))
for col, (title, keys) in zip(cols, sections.items()):
    with col.container(border=True):
        st.markdown(f"**{title}**")
        for key in keys:
            # Escapar: son datos escritos por el usuario (evita XSS).
            st.markdown(f"<small>{escape(key)}</small><br>{escape(str(profile[key]))}",
                        unsafe_allow_html=True)
