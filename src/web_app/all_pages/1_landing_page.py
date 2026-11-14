import streamlit as st


st.set_page_config(
    page_title="site | Welcome",
    page_icon="✨",
    layout="centered",
)

# Main section
st.title("👋 Welcome to Site")
st.subheader("We’re glad you’re here at **domain.lat**")

st.write("""
At **Site**, we believe in innovation, creativity, and connection.
Explore our world and discover how we can grow your MONEY together.
""")

if st.session_state.get("user"):
    if st.button("👤 Ir a Mi cuenta"):
        st.switch_page("all_pages/7_account_page.py")
elif st.button("🚀 Sign Up/Sign In"):
    st.switch_page("all_pages/2_auth_page.py")

# Footer
st.markdown("---")
st.markdown(
    "<p style='text-align: center;'>© 2025 Nuu | All rights reserved.</p>",
    unsafe_allow_html=True,
)
