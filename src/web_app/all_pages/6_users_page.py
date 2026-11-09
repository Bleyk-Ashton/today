from datetime import datetime

import streamlit as st

from web_app import auth_service

st.title("👥 Usuarios")

if not st.session_state.get("user"):
    st.warning("Debe iniciar sesión para acceder a esta página.")
    if st.button("Ir a Sign In"):
        st.switch_page("all_pages/2_auth_page.py")
    st.stop()

st.write(
    "Descargue los datos de los usuarios registrados en formato CSV. "
    "El archivo no incluye contraseñas ni semillas OTP, y el número de tarjeta va enmascarado."
)

st.download_button(
    "⬇️ Descargar usuarios (CSV)",
    data=auth_service.export_users_csv,  # se genera solo al hacer clic
    file_name=f"usuarios_{datetime.now():%Y%m%d_%H%M%S}.csv",
    mime="text/csv",
    on_click="ignore",
)
