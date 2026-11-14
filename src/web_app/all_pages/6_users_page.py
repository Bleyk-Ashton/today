from datetime import datetime

import streamlit as st

from web_app import auth_service, ui
from web_app.auth_service import ROLE_ADMIN
from web_app.guards import require_admin

require_admin()

ui.page_header("👥", "Usuarios registrados", "Resumen de cuentas y exportación de datos.")

users = auth_service.list_users_summary()
m1, m2, m3, m4 = st.columns(4)
m1.metric("Usuarios", len(users), border=True)
m2.metric("Administradores", sum(u["Rol"] == ROLE_ADMIN for u in users), border=True)
m3.metric("OTP activo", sum(u["OTP activo"] for u in users), border=True)
m4.metric("Bloqueados", sum(u["Bloqueado"] for u in users), border=True)

st.dataframe(
    users,
    hide_index=True,
    width="stretch",
    column_config={
        "OTP activo": st.column_config.CheckboxColumn(),
        "Bloqueado": st.column_config.CheckboxColumn(),
        "Creado": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm"),
        "Último acceso": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm"),
    },
)

with st.container(border=True):
    ui.section("⬇️", "Exportar a CSV")
    st.caption(
        "Incluye los datos descifrados de todos los usuarios. No incluye contraseñas "
        "ni semillas OTP, y el número de tarjeta va enmascarado. Manéjelo con cuidado."
    )
    st.download_button(
        "Descargar usuarios (CSV)",
        data=auth_service.export_users_csv,  # se genera solo al hacer clic
        file_name=f"usuarios_{datetime.now():%Y%m%d_%H%M%S}.csv",
        mime="text/csv",
        on_click="ignore",
        type="primary",
    )

ui.footer()
