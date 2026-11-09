import streamlit as st

from web_app.db import init_db

all_pages = [
    st.Page("all_pages/1_landing_page.py", title="Home"),
    st.Page("all_pages/2_auth_page.py", title="Sign Up/Sign In"),
    st.Page("all_pages/3_A_page.py", title="Equipo A"),
    st.Page("all_pages/4_B_page.py", title="Equipo B"),
    st.Page("all_pages/5_C_page.py", title="Equipo Chat"),
    st.Page("all_pages/6_users_page.py", title="Usuarios"),
]


@st.cache_resource
def _setup_database() -> bool:
    init_db()
    return True


def main() -> None:
    _setup_database()

    user = st.session_state.get("user")
    with st.sidebar:
        if user:
            st.caption(f"Conectado: {user['email']}")
            if st.button("Cerrar sesión", key="sidebar-logout"):
                st.session_state.clear()
                st.rerun()

    pg = st.navigation(all_pages)
    pg.run()


if __name__ == "__main__":
    main()
