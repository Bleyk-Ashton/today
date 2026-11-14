"""Control de acceso para las páginas de Streamlit.

El rol se consulta siempre en la base de datos (no se confía en lo guardado en
la sesión), así que quitarle el rol admin a alguien tiene efecto inmediato.
"""

from __future__ import annotations

import streamlit as st

from web_app import auth_service
from web_app.auth_service import ROLE_ADMIN


def current_user() -> dict | None:
    return st.session_state.get("user")


def current_role() -> str | None:
    """Rol del usuario con sesión iniciada, o None si no hay sesión."""
    user = current_user()
    if not user:
        return None
    role = auth_service.get_user_role(user["id"])
    if role is None:  # el usuario fue eliminado de la BD
        st.session_state.clear()
    return role


def require_login() -> dict:
    user = current_user()
    if not user:
        st.warning("Debe iniciar sesión para acceder a esta página.")
        if st.button("Ir a Sign In"):
            st.switch_page("all_pages/2_auth_page.py")
        st.stop()
    return user


def require_admin() -> dict:
    """Detiene la página si el usuario no es administrador."""
    user = require_login()
    if current_role() != ROLE_ADMIN:
        st.error("🚫 Acceso restringido: esta sección es solo para administradores.")
        st.stop()
    return user
