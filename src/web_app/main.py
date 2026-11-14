from html import escape

import streamlit as st
from sqlalchemy.exc import DBAPIError

from web_app import ui
from web_app.auth_service import ROLE_ADMIN
from web_app.db import (
    DatabasePermissionError,
    DatabaseUnavailableError,
    describe_db_error,
    init_db,
)
from web_app.guards import current_role

home_page = st.Page("all_pages/1_landing_page.py", title="Home", icon="🏠", default=True)
auth_page = st.Page("all_pages/2_auth_page.py", title="Acceder", icon="🔐")
account_page = st.Page("all_pages/7_account_page.py", title="Mi cuenta", icon="👤")
admin_pages = [
    st.Page("all_pages/3_A_page.py", title="Equipo A", icon="📄"),
    st.Page("all_pages/4_B_page.py", title="Equipo B", icon="📄"),
    st.Page("all_pages/5_C_page.py", title="Equipo Chat", icon="💬"),
    st.Page("all_pages/6_users_page.py", title="Usuarios", icon="👥"),
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


def _pages_for(role: str | None) -> dict[str, list]:
    """Menú según el rol: visitante, cliente o administrador."""
    if role is None:
        return {"": [home_page, auth_page]}
    pages = {"": [home_page, account_page, auth_page]}
    if role == ROLE_ADMIN:
        pages["Administración"] = admin_pages
    return pages


def main() -> None:
    ui.setup_page()
    try:
        _setup_database()
    except DatabasePermissionError as exc:
        # Hay conexión: las páginas que no usan la tabla users siguen funcionando.
        st.sidebar.warning(f"⚠️ Registro/login no disponibles.\n\n{exc}")
    except DatabaseUnavailableError as exc:
        _show_db_error(str(exc))

    try:
        role = current_role()
    except DatabaseUnavailableError as exc:
        _show_db_error(str(exc))
    except DBAPIError as exc:
        _show_db_error(describe_db_error(exc))

    user = st.session_state.get("user")
    with st.sidebar:
        if user:
            is_admin = role == ROLE_ADMIN
            st.html(
                ui.badge("🛡️ Administrador" if is_admin else "👤 Cliente", admin=is_admin)
                + f'<div style="margin-top:.5rem;font-size:.85rem;opacity:.85;word-break:break-all">'
                f"{escape(user['email'])}</div>"
            )
            if st.button("Cerrar sesión", key="sidebar-logout", icon="🚪", width="stretch"):
                st.session_state.clear()
                st.rerun()

    pg = st.navigation(_pages_for(role))

    # Tras iniciar sesión, llevar al usuario a "Mi cuenta".
    if user and st.session_state.pop("go_to_account", False):
        st.switch_page(account_page)

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
