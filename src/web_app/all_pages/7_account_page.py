import streamlit as st

from web_app import auth_service, ui
from web_app.auth_service import ROLE_ADMIN
from web_app.guards import current_role, require_login

WELCOME_VIDEO = ui.ASSETS / "welcome.mp4"
WELCOME_GIF = ui.ASSETS / "welcome.gif"

user = require_login()
profile = auth_service.get_my_profile(user["id"])
if profile is None:
    st.session_state.clear()
    st.rerun()

is_admin = current_role() == ROLE_ADMIN
first_name = (profile["Nombre"].split() or ["usuario"])[0].capitalize()

ui.hero(
    eyebrow="Administrador" if is_admin else "Mi cuenta",
    title=f"¡Hola, {first_name}! 👋",
    subtitle=f"Último acceso: {profile['Último acceso']}",
)

left, right = st.columns([1, 1], vertical_alignment="center", gap="large")
with left:
    # Video tipo GIF: automático, en bucle y sin sonido (los navegadores
    # bloquean la reproducción automática con sonido). Si no está, usa el GIF.
    if WELCOME_VIDEO.is_file():
        st.video(str(WELCOME_VIDEO), autoplay=True, loop=True, muted=True)
    elif WELCOME_GIF.is_file():
        st.image(str(WELCOME_GIF), width="stretch")
with right:
    st.markdown("#### Tu cuenta está protegida")
    st.markdown(
        "- 🔑 **Contraseña robusta**, guardada solo como hash Argon2id\n"
        "- 📱 **Código OTP** de un solo uso en cada ingreso\n"
        "- 🔒 **Datos cifrados**: personales, de salud y financieros\n"
        "- 🚦 **Bloqueo automático** tras varios intentos fallidos"
    )
    if is_admin:
        st.info("Tienes rol de **administrador**: encontrarás la sección "
                "*Administración* en el menú lateral.", icon="🛡️")

st.write("")
st.subheader("Mi información")
st.caption("Solo tú puedes ver estos datos. Los más sensibles se muestran parcialmente.")

sections = {
    ("👤", "Datos personales"): ["Nombre", "Correo", "Documento", "Fecha de nacimiento", "Teléfono", "Dirección"],
    ("🩺", "Salud"): ["Tipo de sangre", "EPS / aseguradora", "Condiciones médicas"],
    ("💳", "Datos crediticios"): ["Tarjeta", "Vencimiento", "Cuenta creada"],
}
cols = st.columns(len(sections))
for col, ((icon, title), keys) in zip(cols, sections.items()):
    with col.container(border=True):
        ui.section(icon, title)
        ui.fields({k: profile[k] for k in keys})  # valores escapados (evita XSS)

ui.footer()
