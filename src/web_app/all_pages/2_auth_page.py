import io
from datetime import date

import qrcode
import streamlit as st

from web_app import auth_service, ui
from web_app.auth_service import BLOOD_TYPES, LoginStatus, RegistrationData, RegistrationError
from web_app.security import PASSWORD_POLICY_TEXT


def qr_png(data: str) -> bytes:
    qr = qrcode.QRCode(
        version=1, box_size=8, border=4,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
    )
    qr.add_data(data)
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG")
    return buf.getvalue()


def otp_setup_section(user_id: int) -> None:
    """Muestra el QR y pide el primer código para confirmar el OTP."""
    try:
        uri = auth_service.get_otp_provisioning_uri(user_id)
        secret = auth_service.get_otp_secret_for_setup(user_id)
    except PermissionError:
        st.session_state.pop("otp_setup_user_id", None)
        st.rerun()
        return

    ui.page_header("📷", "Activa tu doble factor",
                   "Último paso: vincula tu cuenta con una app autenticadora.")
    left, right = st.columns([1, 1.2], vertical_alignment="center")
    with left:
        st.image(qr_png(uri), width=260)
    with right:
        st.markdown(
            "1. Abre **Google Authenticator**, **Microsoft Authenticator** o **Authy**.\n"
            "2. Toca **＋** y elige **Escanear código QR**.\n"
            "3. Escribe abajo el código de 6 dígitos que aparece."
        )
        with st.expander("¿No puedes escanear? Ingresa la clave manualmente"):
            st.code(secret)

    with st.form("otp-configurar", clear_on_submit=True):
        code = st.text_input("Código de 6 dígitos", max_chars=6, placeholder="123456")
        confirm = st.form_submit_button("Activar OTP", type="primary", width="stretch")

    if confirm:
        ok, message = auth_service.confirm_otp_setup(user_id, code)
        if ok:
            st.session_state.pop("otp_setup_user_id", None)
            st.session_state["flash"] = message
            st.rerun()
        else:
            st.error(message)

    if st.button("Cancelar", type="tertiary"):
        st.session_state.pop("otp_setup_user_id", None)
        st.rerun()


def login_section() -> None:
    with st.form("login", clear_on_submit=False):
        email = st.text_input("Correo electrónico", placeholder="tucorreo@ejemplo.com")
        password = st.text_input("Contraseña", type="password")
        otp_code = st.text_input("Código OTP", max_chars=6, placeholder="123456",
                                 help="Código de 6 dígitos de tu app autenticadora")
        submitted = st.form_submit_button("Iniciar sesión", type="primary", width="stretch")

    if not submitted:
        return
    if not email or not password:
        st.error("Ingrese correo y contraseña.")
        return

    result = auth_service.authenticate(email, password, otp_code)
    if result.status is LoginStatus.SUCCESS:
        st.session_state["user"] = {
            "id": result.user_id, "email": result.email, "name": result.full_name,
        }
        st.session_state["go_to_account"] = True
        st.rerun()
    elif result.status is LoginStatus.OTP_SETUP_REQUIRED:
        st.session_state["otp_setup_user_id"] = result.user_id
        st.session_state["flash"] = result.message
        st.rerun()
    else:  # INVALID o LOCKED
        st.error(result.message)


def register_section() -> None:
    with st.form("registro"):
        ui.section("🔑", "Cuenta")
        email = st.text_input("Correo electrónico *", placeholder="tucorreo@ejemplo.com")
        c1, c2 = st.columns(2)
        password = c1.text_input("Contraseña *", type="password")
        password_confirm = c2.text_input("Confirmar contraseña *", type="password")
        st.caption("Política de contraseñas:" + PASSWORD_POLICY_TEXT)

        ui.section("👤", "Datos personales")
        full_name = st.text_input("Nombre completo *")
        c1, c2 = st.columns(2)
        document_id = c1.text_input("Documento de identidad *")
        birth_date = c2.date_input(
            "Fecha de nacimiento *", value=date(2000, 1, 1),
            min_value=date(1900, 1, 1), max_value=date.today(),
        )
        c1, c2 = st.columns(2)
        phone = c1.text_input("Teléfono *")
        address = c2.text_input("Dirección *")

        ui.section("🩺", "Datos de salud")
        c1, c2 = st.columns(2)
        blood_type = c1.selectbox("Tipo de sangre *", BLOOD_TYPES)
        health_insurer = c2.text_input("EPS / aseguradora *")
        medical_conditions = st.text_area("Condiciones médicas / alergias", placeholder="Ninguna")

        ui.section("💳", "Datos crediticios")
        card_holder = st.text_input("Titular de la tarjeta *")
        c1, c2 = st.columns([2, 1])
        card_number = c1.text_input("Número de tarjeta *", placeholder="4111 1111 1111 1111")
        card_expiry = c2.text_input("Vencimiento (MM/AA) *", max_chars=5, placeholder="12/30")
        monthly_income = st.number_input("Ingresos mensuales", min_value=0.0, step=100000.0)
        st.caption("🔒 Por seguridad (PCI DSS) no solicitamos ni almacenamos el CVV. "
                   "Todos estos datos se guardan cifrados.")

        accept = st.checkbox("Autorizo el tratamiento de mis datos personales *")
        submitted = st.form_submit_button("Crear mi cuenta", type="primary", width="stretch")

    if not submitted:
        return
    if not accept:
        st.error("Debe autorizar el tratamiento de datos personales.")
        return

    data = RegistrationData(
        email=email, password=password, password_confirm=password_confirm,
        full_name=full_name, document_id=document_id, birth_date=birth_date,
        phone=phone, address=address, blood_type=blood_type,
        health_insurer=health_insurer, medical_conditions=medical_conditions,
        card_holder=card_holder, card_number=card_number, card_expiry=card_expiry,
        monthly_income=monthly_income,
    )
    try:
        user_id = auth_service.register_user(data)
    except RegistrationError as exc:
        st.error("No se pudo completar el registro:\n\n" + "\n".join(f"- {e}" for e in exc.errors))
        return

    st.session_state["otp_setup_user_id"] = user_id
    st.session_state["flash"] = "Cuenta creada. Ahora configure su OTP para activarla."
    st.rerun()


# ---------- UI ----------
if flash := st.session_state.pop("flash", None):
    st.success(flash, icon="✅")

user = st.session_state.get("user")
if user:
    ui.page_header("✅", "Ya iniciaste sesión", user["email"])
    c1, c2, _ = st.columns([1.3, 1.3, 2])
    if c1.button("👤 Ir a Mi cuenta", type="primary", width="stretch"):
        st.switch_page("all_pages/7_account_page.py")
    if c2.button("Cerrar sesión", width="stretch"):
        st.session_state.clear()
        st.rerun()
elif "otp_setup_user_id" in st.session_state:
    otp_setup_section(st.session_state["otp_setup_user_id"])
else:
    ui.page_header("🔐", "Accede a tu cuenta",
                   "Ingresa con tu contraseña y el código de tu app autenticadora, o crea una cuenta nueva.")
    tab_login, tab_register = st.tabs(["Iniciar sesión", "Crear cuenta"])
    with tab_login:
        login_section()
    with tab_register:
        register_section()

ui.footer()
