import streamlit as st

from web_app import ui

ui.hero(
    eyebrow="Banca digital segura",
    title="Haz crecer tu dinero sin poner en riesgo tus datos",
    subtitle=(
        f"En {ui.APP_NAME} tu cuenta está protegida con doble factor de autenticación, "
        "cifrado de tus datos sensibles y bloqueo automático ante intentos sospechosos."
    ),
)

logged_in = bool(st.session_state.get("user"))
c1, c2, _ = st.columns([1.3, 1.3, 2])
if logged_in:
    if c1.button("👤 Ir a Mi cuenta", type="primary", width="stretch"):
        st.switch_page("all_pages/7_account_page.py")
else:
    if c1.button("🚀 Crear cuenta", type="primary", width="stretch"):
        st.switch_page("all_pages/2_auth_page.py")
    if c2.button("🔐 Iniciar sesión", width="stretch"):
        st.switch_page("all_pages/2_auth_page.py")

st.write("")
st.subheader("¿Por qué confiar en nosotros?")
ui.cards([
    ("📱", "Doble factor (OTP)",
     "Además de tu contraseña, cada ingreso pide un código de un solo uso de tu app autenticadora."),
    ("🔒", "Datos cifrados",
     "Tu información personal, de salud y financiera se guarda cifrada. Tu contraseña, solo como hash."),
    ("🚦", "Protección activa",
     "Bloqueamos la cuenta tras varios intentos fallidos y rechazamos códigos reutilizados."),
])

st.write("")
st.subheader("Empieza en 3 pasos")
ui.cards([
    ("📝", "Regístrate", "Completa el formulario con tus datos y una contraseña robusta."),
    ("📷", "Escanea el QR", "Vincula tu cuenta con Google o Microsoft Authenticator."),
    ("✅", "Ingresa", "Entra con tu correo, tu contraseña y el código de 6 dígitos."),
], steps=True)

ui.footer()
