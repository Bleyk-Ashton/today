"""Modelos de la base de datos.

Política de almacenamiento de secretos:
- Contraseña: NUNCA se guarda; solo su hash Argon2id (incluye sal aleatoria).
- PII / PHI / datos crediticios y la semilla OTP: cifrados con Fernet
  (AES-128-CBC + HMAC-SHA256) usando ENCRYPTION_KEY del .env. Las columnas
  terminadas en ``_enc`` contienen el texto cifrado.
- CVV: no se almacena nunca (PCI DSS 3.2).
- Datos en claro: solo los necesarios para operar (email para buscar al
  usuario, nombre para mostrar, últimos 4 dígitos de la tarjeta).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from web_app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Credenciales
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    # PII
    full_name: Mapped[str] = mapped_column(String(150))
    document_id_enc: Mapped[str] = mapped_column(Text)
    birth_date_enc: Mapped[str] = mapped_column(Text)
    phone_enc: Mapped[str] = mapped_column(Text)
    address_enc: Mapped[str] = mapped_column(Text)

    # PHI
    blood_type_enc: Mapped[str] = mapped_column(Text)
    health_insurer_enc: Mapped[str] = mapped_column(Text)
    medical_conditions_enc: Mapped[str] = mapped_column(Text)

    # Datos crediticios
    card_holder_enc: Mapped[str] = mapped_column(Text)
    card_number_enc: Mapped[str] = mapped_column(Text)
    card_last4: Mapped[str] = mapped_column(String(4))
    card_expiry_enc: Mapped[str] = mapped_column(Text)
    monthly_income_enc: Mapped[str] = mapped_column(Text)

    # OTP (TOTP)
    otp_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    otp_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    # Último time-step TOTP aceptado: impide reutilizar un código (replay).
    otp_last_timestep: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Rate limiting / bloqueo
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
