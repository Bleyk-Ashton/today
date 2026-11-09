"""Registro de usuarios, configuración de OTP (TOTP) y autenticación.

Recomendaciones de pyotp aplicadas:
- La semilla OTP se genera con ``pyotp.random_base32()`` (CSPRNG) y se guarda cifrada.
- Anti-replay: se guarda el último time-step aceptado y se rechaza cualquier
  código de un time-step igual o anterior (un código no se puede usar 2 veces).
- Rate limiting: tras ``MAX_LOGIN_ATTEMPTS`` fallos (contraseña u OTP) la
  cuenta se bloquea ``LOCKOUT_MINUTES`` minutos. Sin esto un atacante podría
  probar el millón de combinaciones del código de 6 dígitos.
- Ventana de validez pequeña (``OTP_VALID_WINDOW``, por defecto ±1 paso de 30 s)
  para tolerar desfases de reloj sin ampliar demasiado la superficie de ataque.
- Comparación en tiempo constante (``hmac.compare_digest``).
"""

from __future__ import annotations

import csv
import hmac
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum

import pyotp
from sqlalchemy import select
from sqlalchemy.orm import Session

from web_app import security
from web_app.config import get_settings
from web_app.db import get_session
from web_app.models import User

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
OTP_RE = re.compile(r"^\d{6}$")
BLOOD_TYPES = ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite devuelve datetimes sin zona horaria; se asumen en UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def normalize_email(email: str) -> str:
    return email.strip().lower()


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------
@dataclass
class RegistrationData:
    email: str
    password: str
    password_confirm: str
    full_name: str
    document_id: str
    birth_date: date
    phone: str
    address: str
    blood_type: str
    health_insurer: str
    medical_conditions: str
    card_holder: str
    card_number: str
    card_expiry: str  # MM/AA
    monthly_income: float


class RegistrationError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _luhn_ok(number: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(number)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _validate_registration(data: RegistrationData) -> tuple[list[str], str]:
    errors: list[str] = []
    email = normalize_email(data.email)

    if not EMAIL_RE.match(email) or len(email) > 254:
        errors.append("Correo electrónico inválido.")
    if data.password != data.password_confirm:
        errors.append("Las contraseñas no coinciden.")
    errors += security.validate_password(data.password, email, data.full_name)

    required = {
        "Nombre completo": data.full_name,
        "Documento de identidad": data.document_id,
        "Teléfono": data.phone,
        "Dirección": data.address,
        "EPS / aseguradora": data.health_insurer,
        "Titular de la tarjeta": data.card_holder,
    }
    for label, value in required.items():
        if not value or not value.strip():
            errors.append(f"El campo '{label}' es obligatorio.")

    if not re.fullmatch(r"[0-9A-Za-z-]{5,20}", data.document_id.strip()):
        errors.append("Documento de identidad inválido.")
    if not re.fullmatch(r"\+?[0-9 ]{7,15}", data.phone.strip()):
        errors.append("Teléfono inválido.")

    today = date.today()
    if data.birth_date >= today or data.birth_date.year < 1900:
        errors.append("Fecha de nacimiento inválida.")
    elif (today.year - data.birth_date.year
          - ((today.month, today.day) < (data.birth_date.month, data.birth_date.day))) < 18:
        errors.append("Debe ser mayor de edad para registrarse.")

    if data.blood_type not in BLOOD_TYPES:
        errors.append("Tipo de sangre inválido.")

    card = re.sub(r"[\s-]", "", data.card_number)
    if not card.isdigit() or not 13 <= len(card) <= 19 or not _luhn_ok(card):
        errors.append("Número de tarjeta inválido.")

    m = re.fullmatch(r"(0[1-9]|1[0-2])/(\d{2})", data.card_expiry.strip())
    if not m:
        errors.append("Vencimiento de la tarjeta inválido (formato MM/AA).")
    elif (2000 + int(m.group(2)), int(m.group(1))) < (today.year, today.month):
        errors.append("La tarjeta está vencida.")

    if data.monthly_income < 0:
        errors.append("Los ingresos no pueden ser negativos.")

    return errors, card


def register_user(data: RegistrationData) -> int:
    """Crea el usuario (OTP pendiente de confirmar). Devuelve su id."""
    errors, card = _validate_registration(data)
    if errors:
        raise RegistrationError(errors)

    email = normalize_email(data.email)
    enc = security.encrypt
    with get_session() as session:
        if session.scalar(select(User.id).where(User.email == email)) is not None:
            raise RegistrationError(["Ya existe una cuenta con ese correo."])

        user = User(
            email=email,
            password_hash=security.hash_password(data.password),
            full_name=data.full_name.strip(),
            document_id_enc=enc(data.document_id.strip()),
            birth_date_enc=enc(data.birth_date.isoformat()),
            phone_enc=enc(data.phone.strip()),
            address_enc=enc(data.address.strip()),
            blood_type_enc=enc(data.blood_type),
            health_insurer_enc=enc(data.health_insurer.strip()),
            medical_conditions_enc=enc(data.medical_conditions.strip()),
            card_holder_enc=enc(data.card_holder.strip()),
            card_number_enc=enc(card),
            card_last4=card[-4:],
            card_expiry_enc=enc(data.card_expiry.strip()),
            monthly_income_enc=enc(f"{data.monthly_income:.2f}"),
            otp_secret_enc=enc(pyotp.random_base32()),
            otp_confirmed=False,
            failed_attempts=0,
        )
        session.add(user)
        session.flush()
        return user.id


# ---------------------------------------------------------------------------
# OTP
# ---------------------------------------------------------------------------
def _totp_for(user: User) -> pyotp.TOTP:
    return pyotp.TOTP(security.decrypt(user.otp_secret_enc))


def _match_timestep(totp: pyotp.TOTP, code: str) -> int | None:
    """Devuelve el time-step al que corresponde ``code`` dentro de la ventana."""
    if not OTP_RE.match(code):
        return None
    window = get_settings().otp_valid_window
    current = totp.timecode(datetime.now(timezone.utc))
    for offset in range(-window, window + 1):
        step = current + offset
        if hmac.compare_digest(totp.generate_otp(step), code):
            return step
    return None


def _check_otp(user: User, code: str) -> bool:
    """Verifica el código y lo marca como usado (anti-replay)."""
    step = _match_timestep(_totp_for(user), code.strip())
    if step is None:
        return False
    if user.otp_last_timestep is not None and step <= user.otp_last_timestep:
        return False  # código ya utilizado (o uno más antiguo): replay
    user.otp_last_timestep = step
    return True


def get_otp_provisioning_uri(user_id: int) -> str:
    """URI otpauth:// para generar el QR. Solo disponible si el OTP aún no se confirmó."""
    with get_session() as session:
        user = session.get(User, user_id)
        if user is None or user.otp_confirmed:
            raise PermissionError("El OTP de este usuario ya fue configurado.")
        return _totp_for(user).provisioning_uri(
            name=user.email, issuer_name=get_settings().otp_issuer
        )


def get_otp_secret_for_setup(user_id: int) -> str:
    """Semilla en base32 para ingreso manual en la app autenticadora."""
    with get_session() as session:
        user = session.get(User, user_id)
        if user is None or user.otp_confirmed:
            raise PermissionError("El OTP de este usuario ya fue configurado.")
        return security.decrypt(user.otp_secret_enc)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
def _lock_remaining(user: User) -> timedelta | None:
    locked_until = _aware(user.locked_until)
    if locked_until and locked_until > _now():
        return locked_until - _now()
    return None


def _register_failure(user: User) -> None:
    settings = get_settings()
    user.failed_attempts = (user.failed_attempts or 0) + 1
    if user.failed_attempts >= settings.max_login_attempts:
        user.locked_until = _now() + timedelta(minutes=settings.lockout_minutes)
        user.failed_attempts = 0


def _reset_failures(user: User) -> None:
    user.failed_attempts = 0
    user.locked_until = None


def _get_user_for_update(session: Session, **filters) -> User | None:
    # FOR UPDATE (en PostgreSQL) evita que dos peticiones concurrentes acepten
    # el mismo código OTP o se salten el contador de intentos.
    stmt = select(User).filter_by(**filters).with_for_update()
    return session.scalar(stmt)


class LoginStatus(Enum):
    SUCCESS = "success"
    INVALID = "invalid"
    LOCKED = "locked"
    OTP_SETUP_REQUIRED = "otp_setup_required"


@dataclass
class LoginResult:
    status: LoginStatus
    message: str
    user_id: int | None = None
    email: str | None = None
    full_name: str | None = None
    extra: dict = field(default_factory=dict)


GENERIC_INVALID = "Usuario, contraseña u OTP incorrectos."


def _locked_message(remaining: timedelta) -> str:
    minutes = max(1, int(remaining.total_seconds() // 60) + 1)
    return f"Demasiados intentos fallidos. Cuenta bloqueada, intente en {minutes} min."


def confirm_otp_setup(user_id: int, code: str) -> tuple[bool, str]:
    """Confirma la configuración del OTP con el primer código generado."""
    with get_session() as session:
        user = _get_user_for_update(session, id=user_id)
        if user is None:
            return False, "Usuario no encontrado."
        if user.otp_confirmed:
            return True, "El OTP ya estaba configurado."
        remaining = _lock_remaining(user)
        if remaining:
            return False, _locked_message(remaining)
        if _check_otp(user, code):
            user.otp_confirmed = True
            _reset_failures(user)
            return True, "OTP configurado correctamente. Ya puede iniciar sesión."
        _register_failure(user)
        remaining = _lock_remaining(user)
        return False, _locked_message(remaining) if remaining else "Código incorrecto, intente nuevamente."


def authenticate(email: str, password: str, otp_code: str) -> LoginResult:
    """Autenticación con 3 factores de entrada: usuario, contraseña y OTP.

    Casos:
    - Usuario inexistente           -> INVALID (mensaje genérico, tiempo constante).
    - Cuenta bloqueada              -> LOCKED (no se evalúa la contraseña).
    - Contraseña incorrecta         -> INVALID + suma intento fallido.
    - Contraseña OK, OTP sin config -> OTP_SETUP_REQUIRED (se muestra el QR).
    - Contraseña OK, OTP incorrecto
      o reutilizado (replay)        -> INVALID + suma intento fallido.
    - Todo correcto                 -> SUCCESS + reinicia contador.
    """
    email = normalize_email(email)
    with get_session() as session:
        user = _get_user_for_update(session, email=email)
        if user is None:
            security.verify_password(security.DUMMY_PASSWORD_HASH, password)
            return LoginResult(LoginStatus.INVALID, GENERIC_INVALID)

        remaining = _lock_remaining(user)
        if remaining:
            return LoginResult(LoginStatus.LOCKED, _locked_message(remaining))

        if not security.verify_password(user.password_hash, password):
            _register_failure(user)
            remaining = _lock_remaining(user)
            if remaining:
                return LoginResult(LoginStatus.LOCKED, _locked_message(remaining))
            return LoginResult(LoginStatus.INVALID, GENERIC_INVALID)

        if security.password_needs_rehash(user.password_hash):
            user.password_hash = security.hash_password(password)

        if not user.otp_confirmed:
            return LoginResult(
                LoginStatus.OTP_SETUP_REQUIRED,
                "Su cuenta aún no tiene OTP configurado. Escanee el QR para continuar.",
                user_id=user.id,
            )

        if not _check_otp(user, otp_code or ""):
            _register_failure(user)
            remaining = _lock_remaining(user)
            if remaining:
                return LoginResult(LoginStatus.LOCKED, _locked_message(remaining))
            return LoginResult(LoginStatus.INVALID, GENERIC_INVALID)

        _reset_failures(user)
        user.last_login_at = _now()
        return LoginResult(
            LoginStatus.SUCCESS,
            f"Bienvenido, {user.full_name}.",
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
        )


# ---------------------------------------------------------------------------
# Exportación CSV
# ---------------------------------------------------------------------------
CSV_COLUMNS = [
    "id", "email", "full_name", "document_id", "birth_date", "phone", "address",
    "blood_type", "health_insurer", "medical_conditions", "card_holder",
    "card_number", "card_expiry", "monthly_income", "otp_confirmed",
    "created_at", "last_login_at",
]


def export_users_csv() -> bytes:
    """CSV con los usuarios registrados.

    No incluye hash de contraseña ni semilla OTP, y la tarjeta va enmascarada.
    """
    dec = security.decrypt
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    with get_session() as session:
        for u in session.scalars(select(User).order_by(User.id)):
            writer.writerow({
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "document_id": dec(u.document_id_enc),
                "birth_date": dec(u.birth_date_enc),
                "phone": dec(u.phone_enc),
                "address": dec(u.address_enc),
                "blood_type": dec(u.blood_type_enc),
                "health_insurer": dec(u.health_insurer_enc),
                "medical_conditions": dec(u.medical_conditions_enc),
                "card_holder": dec(u.card_holder_enc),
                "card_number": f"**** **** **** {u.card_last4}",
                "card_expiry": dec(u.card_expiry_enc),
                "monthly_income": dec(u.monthly_income_enc),
                "otp_confirmed": u.otp_confirmed,
                "created_at": u.created_at.isoformat() if u.created_at else "",
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else "",
            })
    # BOM para que Excel abra correctamente las tildes.
    return buf.getvalue().encode("utf-8-sig")
