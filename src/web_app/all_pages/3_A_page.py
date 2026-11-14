import streamlit as st

from web_app import ui
from web_app.db import read_table
from web_app.guards import require_admin

require_admin()

ui.page_header("📄", "Equipo A", "Datos de la tabla public.a · solo lectura")

limit = st.slider("Filas a mostrar", min_value=10, max_value=1000, value=100, step=10)
rows = read_table("a", limit=limit)  # solo lectura, consulta parametrizada

c1, _ = st.columns([1, 3])
c1.metric("Filas mostradas", len(rows), border=True)
if rows:
    st.dataframe(rows, width="stretch", hide_index=True)
else:
    st.info("La tabla está vacía.", icon="📭")

ui.footer()
