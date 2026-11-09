"""Configuración de la aplicación cargada desde variables de entorno / archivo .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL

# Raíz del proyecto (carpeta que contiene pyproject.toml).
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# El .env se busca en la raíz del proyecto; las variables ya definidas en el
# entorno (p. ej. en el servidor) tienen prioridad sobre el archivo.
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value not in (None, "") else default


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

    # Secretos / cifrado
    encryption_key: str

    # OTP
    otp_issuer: str
    otp_valid_window: int

    # Rate limiting
    max_login_attempts: int
    lockout_minutes: int

    @property
    def database_url(self) -> URL:
        engine = self.db_engine.lower()
        if engine == "sqlite":
            path = Path(self.sqlite_path)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            return URL.create("sqlite", database=str(path))
        if engine in ("postgres", "postgresql"):
            query = {"sslmode": self.db_sslmode} if self.db_sslmode else {}
            return URL.create(
                "postgresql+psycopg",
                username=self.db_user,
                password=self.db_password,  # URL.create escapa caracteres especiales
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                query=query,
            )
        raise ValueError(f"DB_ENGINE no soportado: {self.db_engine!r} (use sqlite o postgresql)")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    encryption_key = os.getenv("ENCRYPTION_KEY", "")
    if not encryption_key:
        raise RuntimeError(
            "Falta ENCRYPTION_KEY en el .env. Genere una con:\n"
            '  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )

    return Settings(
        db_engine=os.getenv("DB_ENGINE", "sqlite"),
        sqlite_path=os.getenv("SQLITE_PATH", "app.db"),
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=_get_int("DB_PORT", 5432),
        db_name=os.getenv("DB_NAME", "today"),
        db_user=os.getenv("DB_USER", "postgres"),
        db_password=os.getenv("DB_PASSWORD", ""),
        db_sslmode=os.getenv("DB_SSLMODE", ""),
        db_echo=os.getenv("DB_ECHO", "false").lower() in ("1", "true", "yes"),
        encryption_key=encryption_key,
        otp_issuer=os.getenv("OTP_ISSUER", "domain.lat"),
        otp_valid_window=_get_int("OTP_VALID_WINDOW", 1),
        max_login_attempts=_get_int("MAX_LOGIN_ATTEMPTS", 5),
        lockout_minutes=_get_int("LOCKOUT_MINUTES", 15),
    )
