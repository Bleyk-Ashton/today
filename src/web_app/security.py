"""Política de contraseñas, hashing y cifrado de datos sensibles."""

from __future__ import annotations

import re
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet

from web_app.config import get_settings

# ---------------------------------------------------------------------------
# Política de contraseñas
# ---------------------------------------------------------------------------
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128

PASSWORD_POLICY_TEXT = f"""
- Entre {PASSWORD_MIN_LENGTH} y {PASSWORD_MAX_LENGTH} caracteres.
- Al menos una mayúscula, una minúscula, un número y un símbolo.
- No puede contener su correo ni su nombre.
- No puede ser una contraseña común.
"""

# Lista corta de contraseñas comunes (en producción usar una lista completa
# o la API "Have I Been Pwned" con k-anonymity).
_COMMON_PASSWORDS = {
    "password", "password123", "123456789012", "qwertyuiop", "contraseña",
    "administrator", "letmein12345", "welcome12345", "iloveyou1234",
}


def validate_password(password: str, email: str = "", full_name: str = "") -> list[str]:
    """Devuelve la lista de reglas incumplidas (vacía si la contraseña es válida)."""
    errors: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"Debe tener al menos {PASSWORD_MIN_LENGTH} caracteres.")
    if len(password) > PASSWORD_MAX_LENGTH:
        errors.append(f"Debe tener como máximo {PASSWORD_MAX_LENGTH} caracteres.")
    if not re.search(r"[A-Z]", password):
        errors.append("Debe incluir al menos una letra mayúscula.")
    if not re.search(r"[a-z]", password):
        errors.append("Debe incluir al menos una letra minúscula.")
    if not re.search(r"\d", password):
        errors.append("Debe incluir al menos un número.")
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("Debe incluir al menos un símbolo.")

    lowered = password.lower()
    if lowered in _COMMON_PASSWORDS:
        errors.append("Es una contraseña demasiado común.")
    local_part = email.split("@")[0].lower()
    if len(local_part) >= 3 and local_part in lowered:
        errors.append("No debe contener su correo.")
    for part in full_name.lower().split():
        if len(part) >= 3 and part in lowered:
            errors.append("No debe contener su nombre.")
            break
    return errors


# ---------------------------------------------------------------------------
# Hash de contraseñas (Argon2id, parámetros por defecto recomendados por OWASP)
# ---------------------------------------------------------------------------
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# Hash ficticio para igualar el tiempo de respuesta cuando el usuario no
# existe (evita enumerar usuarios midiendo tiempos).
DUMMY_PASSWORD_HASH = _hasher.hash("dummy-password-for-timing")


# ---------------------------------------------------------------------------
# Cifrado simétrico de campos sensibles
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    return Fernet(get_settings().encryption_key.encode())


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
