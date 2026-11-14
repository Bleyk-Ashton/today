import streamlit as st
from sqlalchemy.exc import DBAPIError

from web_app.db import (
    DatabasePermissionError,
    DatabaseUnavailableError,
    describe_db_error,
    init_db,
)

all_pages = [
    st.Page("all_pages/1_landing_page.py", title="Home"),
    st.Page("all_pages/2_auth_page.py", title="Sign Up/Sign In"),
    st.Page("all_pages/3_A_page.py", title="Equipo A"),
    st.Page("all_pages/4_B_page.py", title="Equipo B"),
    st.Page("all_pages/5_C_page.py", title="Equipo Chat"),
    st.Page("all_pages/6_users_page.py", title="Usuarios"),
]


@st.cache_resource(show_spinner="Conectando a la base de datos…")
def _setup_database() -> bool:
    # Si falla, Streamlit no guarda el resultado y lo reintenta en el próximo rerun.
    init_db()
    return True


def _show_db_error(message: str) -> None:
    st.error(f"🛑 No hay conexión con la base de datos.\n\n{message}")
    if st.button("Reintentar"):
        st.rerun()
    st.stop()


def main() -> None:
    try:
        _setup_database()
    except DatabasePermissionError as exc:
        # Hay conexión: las páginas de solo lectura siguen funcionando.
        st.sidebar.warning(f"⚠️ Registro/login no disponibles.\n\n{exc}")
    except DatabaseUnavailableError as exc:
        _show_db_error(str(exc))

    user = st.session_state.get("user")
    with st.sidebar:
        if user:
            st.caption(f"Conectado: {user['email']}")
            if st.button("Cerrar sesión", key="sidebar-logout"):
                st.session_state.clear()
                st.rerun()

    pg = st.navigation(all_pages)
    try:
        pg.run()
    except DatabasePermissionError as exc:
        st.error(f"🔒 Sin permisos en la base de datos.\n\n{exc}")
    except DatabaseUnavailableError as exc:
        _show_db_error(str(exc))
    except DBAPIError as exc:
        _show_db_error(describe_db_error(exc))


if __name__ == "__main__":
    main()
