"""Configuración de la aplicación.

Orden de prioridad de cada variable:
1. Variables de entorno del sistema (p. ej. en el servidor web).
2. Archivo ``.env`` en la raíz del proyecto.
3. ``.streamlit/secrets.toml`` (``st.secrets``).
4. Valor por defecto.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL

# Raíz del proyecto (carpeta que contiene pyproject.toml).
PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env", override=False)


def _from_streamlit_secrets(name: str) -> str | None:
    try:
        import streamlit as st

        value = st.secrets.get(name)
    except Exception:  # sin secrets.toml o fuera de Streamlit
        return None
    return None if value is None else str(value)


def _get(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        value = _from_streamlit_secrets(name)
    return default if value is None else value


def _get_int(name: str, default: int) -> int:
    value = _get(name)
    return int(value) if value.strip() else default


def _get_bool(name: str, default: bool = False) -> bool:
    value = _get(name)
    return value.strip().lower() in ("1", "true", "yes", "si", "sí") if value.strip() else default


@dataclass(frozen=True)
class Settings:
    # Base de datos
    db_engine: str
    sqlite_path: str
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_sslmode: str
    db_echo: bool
    db_connect_timeout: int

    # Túnel SSH (desarrollo local: PC -> Tailscale -> servidor web -> BD)
    db_use_tunnel: bool
    ssh_host: str
    ssh_port: int
    ssh_user: str
    ssh_key_path: str
    ssh_local_port: int  # 0 = elegir un puerto libre automáticamente

    # Secretos / cifrado
    encryption_key: str

    # OTP
    otp_issuer: str
    otp_valid_window: int

    # Rate limiting
    max_login_attempts: int
    lockout_minutes: int

    @property
    def is_postgres(self) -> bool:
        return self.db_engine.lower() in ("postgres", "postgresql")

    def database_url(self, host: str | None = None, port: int | None = None) -> URL:
        """URL de conexión. ``host``/``port`` permiten apuntar al extremo local del túnel."""
        if self.db_engine.lower() == "sqlite":
            path = Path(self.sqlite_path)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            return URL.create("sqlite", database=str(path))
        if self.is_postgres:
            query = {"sslmode": self.db_sslmode} if self.db_sslmode else {}
            return URL.create(
                "postgresql+psycopg",
                username=self.db_user,
                password=self.db_password,  # URL.create escapa caracteres especiales
                host=host or self.db_host,
                port=port or self.db_port,
                database=self.db_name,
                query=query,
            )
        raise ValueError(f"DB_ENGINE no soportado: {self.db_engine!r} (use sqlite o postgresql)")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    encryption_key = _get("ENCRYPTION_KEY")
    if not encryption_key:
        raise RuntimeError(
            "Falta ENCRYPTION_KEY en el .env. Genere una con:\n"
            '  uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )

    return Settings(
        db_engine=_get("DB_ENGINE", "sqlite"),
        sqlite_path=_get("SQLITE_PATH", "app.db"),
        db_host=_get("DB_HOST", "localhost"),
        db_port=_get_int("DB_PORT", 5432),
        db_name=_get("DB_NAME", "ciber_bleyk"),
        db_user=_get("DB_USER", "postgres"),
        db_password=_get("DB_PASSWORD"),
        db_sslmode=_get("DB_SSLMODE"),
        db_echo=_get_bool("DB_ECHO"),
        db_connect_timeout=_get_int("DB_CONNECT_TIMEOUT", 10),
        db_use_tunnel=_get_bool("DB_USE_TUNNEL"),
        ssh_host=_get("SSH_HOST"),
        ssh_port=_get_int("SSH_PORT", 22),
        ssh_user=_get("SSH_USER"),
        ssh_key_path=_get("SSH_KEY_PATH"),
        ssh_local_port=_get_int("SSH_LOCAL_PORT", 0),
        encryption_key=encryption_key,
        otp_issuer=_get("OTP_ISSUER", "domain.lat"),
        otp_valid_window=_get_int("OTP_VALID_WINDOW", 1),
        max_login_attempts=_get_int("MAX_LOGIN_ATTEMPTS", 5),
        lockout_minutes=_get_int("LOCKOUT_MINUTES", 15),
    )
