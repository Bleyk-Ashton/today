"""Conexión a la base de datos.

Modos de conexión (variables en .env):
- ``DB_ENGINE=sqlite``: archivo local, solo para pruebas.
- ``DB_ENGINE=postgresql`` + ``DB_USE_TUNNEL=false``: conexión directa a
  ``DB_HOST:DB_PORT`` (la app corre en el servidor web de AWS).
- ``DB_ENGINE=postgresql`` + ``DB_USE_TUNNEL=true``: la app corre en el PC;
  se abre un túnel SSH por el servidor web (vía Tailscale) hacia
  ``DB_HOST:DB_PORT`` y se conecta a ``127.0.0.1:<puerto local>``.

El túnel y el engine (pool de conexiones) son únicos por proceso, así que
se reutilizan entre reruns y sesiones de Streamlit.
"""

from __future__ import annotations

import logging
import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, MetaData, Table, create_engine, event, inspect, select, text
from sqlalchemy.exc import DBAPIError, NoSuchTableError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from web_app.config import Settings, get_settings

log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class DatabaseUnavailableError(RuntimeError):
    """Error de conexión con un mensaje entendible para mostrar en la UI."""


class DatabasePermissionError(DatabaseUnavailableError):
    """Hay conexión, pero el usuario no puede crear las tablas de la app."""


# ---------------------------------------------------------------------------
# Túnel SSH
# ---------------------------------------------------------------------------
_tunnel = None
_tunnel_lock = threading.Lock()


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _tcp_reachable(host: str, port: int, timeout: float = 5.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _start_tunnel(settings: Settings):
    import sshtunnel

    missing = [n for n, v in (("SSH_HOST", settings.ssh_host), ("SSH_USER", settings.ssh_user),
                              ("SSH_KEY_PATH", settings.ssh_key_path)) if not v]
    if missing:
        raise DatabaseUnavailableError(f"DB_USE_TUNNEL=true pero faltan variables: {', '.join(missing)}.")
    if not Path(settings.ssh_key_path).expanduser().is_file():
        raise DatabaseUnavailableError(
            f"No se encontró la clave SSH en SSH_KEY_PATH={settings.ssh_key_path!r}."
        )

    sshtunnel.SSH_TIMEOUT = float(settings.db_connect_timeout)
    sshtunnel.TUNNEL_TIMEOUT = float(settings.db_connect_timeout)

    local_port = settings.ssh_local_port or _free_local_port()
    tunnel = sshtunnel.SSHTunnelForwarder(
        (settings.ssh_host, settings.ssh_port),
        ssh_username=settings.ssh_user,
        ssh_pkey=settings.ssh_key_path,
        allow_agent=False,
        remote_bind_address=(settings.db_host, settings.db_port),
        local_bind_address=("127.0.0.1", local_port),
        set_keepalive=30.0,
    )
    try:
        tunnel.start()
    except Exception as exc:
        raise DatabaseUnavailableError(_describe_ssh_error(settings, exc)) from exc
    log.info("Túnel SSH activo: 127.0.0.1:%s -> %s:%s vía %s",
             local_port, settings.db_host, settings.db_port, settings.ssh_host)
    return tunnel


def _ensure_tunnel(settings: Settings) -> int:
    """Abre el túnel (o lo reabre si se cayó) y devuelve el puerto local."""
    global _tunnel
    with _tunnel_lock:
        if _tunnel is None:
            _tunnel = _start_tunnel(settings)
        elif not _tunnel.is_active:
            log.warning("El túnel SSH se cayó, reconectando…")
            try:
                _tunnel.restart()  # conserva el mismo puerto local
            except Exception as exc:
                raise DatabaseUnavailableError(_describe_ssh_error(settings, exc)) from exc
        return _tunnel.local_bind_port


# ---------------------------------------------------------------------------
# Engine / sesiones
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _create_engine(host: str | None, port: int | None) -> Engine:
    settings = get_settings()
    url = settings.database_url(host, port)
    kwargs: dict = {"echo": settings.db_echo, "pool_pre_ping": True}

    if url.get_backend_name() == "sqlite":
        # Streamlit ejecuta cada sesión en un hilo distinto.
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["connect_args"] = {
            "connect_timeout": settings.db_connect_timeout,
            "application_name": "today-streamlit",
        }
        kwargs["pool_recycle"] = 1800

    engine = create_engine(url, **kwargs)

    if url.get_backend_name() == "sqlite":
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

    return engine


def get_engine() -> Engine:
    settings = get_settings()
    if settings.is_postgres and settings.db_use_tunnel:
        return _create_engine("127.0.0.1", _ensure_tunnel(settings))
    return _create_engine(None, None)


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(expire_on_commit=False)


@contextmanager
def get_session() -> Iterator[Session]:
    """Sesión transaccional: hace commit al salir o rollback si hay error."""
    session = _session_factory()(bind=get_engine())
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _migrate(engine: Engine) -> None:
    """Agrega columnas nuevas a tablas creadas por versiones anteriores de la app."""
    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    columns = {c["name"] for c in insp.get_columns("users")}
    if "role" not in columns:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'cliente'"
            ))
        log.info("Migración: columna users.role agregada")


def init_db() -> None:
    """Comprueba la conexión y crea las tablas de la app si no existen."""
    from web_app import models  # noqa: F401  (registra los modelos en Base)

    try:
        engine = get_engine()
        Base.metadata.create_all(engine)
        _migrate(engine)
    except DatabaseUnavailableError:
        raise
    except Exception as exc:
        if "permission denied" in str(exc).lower():
            raise DatabasePermissionError(describe_db_error(exc)) from exc
        raise DatabaseUnavailableError(describe_db_error(exc)) from exc


# ---------------------------------------------------------------------------
# Lectura de tablas (solo lectura, consultas parametrizadas)
# ---------------------------------------------------------------------------
# Los nombres de tabla no pueden ir como parámetro SQL, por eso solo se
# permiten los de esta lista blanca.
READABLE_TABLES = {"a", "b"}


def read_table(name: str, limit: int = 100) -> list[dict]:
    if name not in READABLE_TABLES:
        raise ValueError(f"Tabla no permitida: {name!r}")
    engine = get_engine()
    try:
        with engine.connect() as conn:
            if engine.dialect.name == "postgresql":
                conn = conn.execution_options(postgresql_readonly=True)
            table = Table(name, MetaData(), autoload_with=conn)
            stmt = select(table).limit(limit)  # LIMIT se envía como parámetro
            if "id" in table.c:
                stmt = stmt.order_by(table.c.id)
            return [dict(row) for row in conn.execute(stmt).mappings()]
    except NoSuchTableError:
        raise DatabaseUnavailableError(f"La tabla '{name}' no existe o el usuario no tiene acceso a ella.")
    except DatabaseUnavailableError:
        raise
    except Exception as exc:
        if "permission denied" in str(exc).lower():
            raise DatabasePermissionError(describe_db_error(exc)) from exc
        raise DatabaseUnavailableError(describe_db_error(exc)) from exc


# ---------------------------------------------------------------------------
# Mensajes de error
# ---------------------------------------------------------------------------
def _describe_ssh_error(settings: Settings, exc: Exception) -> str:
    target = f"{settings.ssh_host}:{settings.ssh_port}"
    log.debug("Error SSH: %r", exc)
    if not _tcp_reachable(settings.ssh_host, settings.ssh_port):
        return (
            f"Timeout: no se puede llegar al servidor web {target}. Verifique que su PC "
            "esté conectada a Tailscale y que la instancia 'ciber-web-server' esté encendida."
        )
    return (
        f"Permission denied: el servidor SSH {target} rechazó la clave del usuario "
        f"'{settings.ssh_user}'. Revise SSH_USER y SSH_KEY_PATH."
    )


def describe_db_error(exc: BaseException) -> str:
    """Traduce errores de conexión de PostgreSQL a un mensaje claro."""
    settings = get_settings()
    original = exc.orig if isinstance(exc, DBAPIError) and exc.orig is not None else exc
    text = str(original).lower()
    where = f"{settings.db_host}:{settings.db_port}/{settings.db_name}"

    if "password authentication failed" in text:
        return f"password authentication failed: usuario o contraseña de PostgreSQL incorrectos (DB_USER={settings.db_user!r})."
    if "no password supplied" in text:
        return "PostgreSQL pide contraseña: defina DB_PASSWORD en el .env o en .streamlit/secrets.toml."
    if "no pg_hba.conf entry" in text:
        return (
            f"PostgreSQL rechazó la conexión desde esta máquina (pg_hba.conf). "
            f"Pida al administrador que permita al usuario '{settings.db_user}' desde esta IP."
        )
    if f'database "{settings.db_name.lower()}" does not exist' in text:
        return f"La base de datos '{settings.db_name}' no existe en el servidor."
    if "permission denied for schema" in text:
        return (
            f"El usuario '{settings.db_user}' no puede crear tablas en el esquema public "
            f"({original}). La app necesita crear y escribir la tabla 'users' para el registro: "
            f"pida al administrador GRANT CREATE ON SCHEMA public TO {settings.db_user};"
        )
    if "permission denied" in text:
        return f"El usuario '{settings.db_user}' no tiene permisos para esta operación: {original}."
    if any(s in text for s in ("timeout", "timed out", "could not connect", "connection refused",
                                 "server closed the connection", "connection is bad")):
        hint = (
            "la instancia 'base-de-datos' está apagada o el túnel no llega a ella"
            if settings.db_use_tunnel else
            "la instancia 'base-de-datos' está apagada, sin red, o PostgreSQL no escucha en esa IP"
        )
        return f"Timeout / sin conexión con PostgreSQL en {where}: probablemente {hint}."
    return f"Error de base de datos: {original}"
