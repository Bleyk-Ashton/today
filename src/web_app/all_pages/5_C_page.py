import streamlit as st

from web_app.guards import require_admin

st.title("Equipo C")
require_admin()
