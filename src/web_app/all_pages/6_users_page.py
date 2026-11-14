from datetime import datetime

import streamlit as st

from web_app import auth_service
from web_app.guards import require_admin

st.title("👥 Usuarios")

require_admin()

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
