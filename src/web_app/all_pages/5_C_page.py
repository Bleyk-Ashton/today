import streamlit as st

from web_app import ui
from web_app.guards import require_admin

require_admin()

ui.page_header("💬", "Equipo Chat", "Canal interno del equipo")
st.info("Esta sección estará disponible próximamente.", icon="🚧")

ui.footer()
