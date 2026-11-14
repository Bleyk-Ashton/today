import streamlit as st

from web_app.db import read_table

st.title("Equipo A")

if not st.session_state.get("user"):
    st.warning("Debe iniciar sesión para ver los datos.")
    if st.button("Ir a Sign In"):
        st.switch_page("all_pages/2_auth_page.py")
    st.stop()

limit = st.slider("Filas a mostrar", min_value=10, max_value=1000, value=100, step=10)
rows = read_table("a", limit=limit)  # solo lectura, consulta parametrizada
st.caption(f"Tabla `public.a` · {len(rows)} filas")
if rows:
    st.dataframe(rows, width="stretch", hide_index=True)
else:
    st.info("La tabla está vacía.")
