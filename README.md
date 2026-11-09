# today

App en Streamlit con registro de usuarios, autenticación con contraseña + OTP (TOTP con `pyotp`)
y exportación de usuarios a CSV. Soporta **PostgreSQL** (producción) y **SQLite** (pruebas).

## Puesta en marcha

```bash
# 1. Dependencias (añada --extra postgres si va a usar PostgreSQL)
uv sync
uv sync --extra postgres

# 2. Configuración
cp .env.example .env
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# -> pegue la clave en ENCRYPTION_KEY dentro de .env

# 3. Ejecutar
uv run streamlit run src/web_app/main.py
```

Las tablas se crean automáticamente al iniciar la app.

### Usar PostgreSQL

```sql
CREATE ROLE today_app LOGIN PASSWORD 'cambie-esta-contraseña';
CREATE DATABASE today OWNER today_app;
```

En `.env`:

```
DB_ENGINE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=today
DB_USER=today_app
DB_PASSWORD=cambie-esta-contraseña
DB_SSLMODE=require
```

## Estructura

| Archivo | Responsabilidad |
|---|---|
| `src/web_app/config.py` | Lee el `.env` y arma la URL de conexión |
| `src/web_app/db.py` | Engine/sesiones de SQLAlchemy, creación de tablas |
| `src/web_app/models.py` | Tabla `users` |
| `src/web_app/security.py` | Política de contraseñas, Argon2id, cifrado Fernet |
| `src/web_app/auth_service.py` | Registro, OTP, login, rate limiting, CSV |
| `src/web_app/all_pages/2_auth_page.py` | Formularios de registro, configuración OTP y login |
| `src/web_app/all_pages/6_users_page.py` | Descarga CSV (requiere sesión iniciada) |

## Política de contraseñas

- 12 a 128 caracteres.
- Al menos una mayúscula, una minúscula, un número y un símbolo.
- No puede contener el correo ni el nombre del usuario, ni ser una contraseña común.

## Almacenamiento de secretos

| Dato | Cómo se guarda |
|---|---|
| Contraseña | Hash **Argon2id** (sal aleatoria por usuario). Se re-hashea si cambian los parámetros. |
| PII (documento, fecha de nacimiento, teléfono, dirección) | Cifrado **Fernet** (AES-128-CBC + HMAC-SHA256) |
| PHI (tipo de sangre, EPS, condiciones médicas) | Cifrado Fernet |
| Datos crediticios (titular, número, vencimiento, ingresos) | Cifrado Fernet; solo los últimos 4 dígitos en claro |
| CVV | **No se solicita ni almacena** (PCI DSS) |
| Semilla OTP | Cifrado Fernet |
| Clave de cifrado y credenciales de BD | Solo en `.env` (excluido de git) o variables de entorno del servidor |

## OTP y autenticación

- Al registrarse se genera una semilla con `pyotp.random_base32()` y se muestra un QR
  (`otpauth://`). La cuenta queda activa solo después de confirmar el primer código.
- **Anti-replay**: se guarda el último *time-step* aceptado; un código ya usado (o uno más
  antiguo) se rechaza.
- **Rate limiting**: tras `MAX_LOGIN_ATTEMPTS` fallos (contraseña u OTP) la cuenta se bloquea
  `LOCKOUT_MINUTES` minutos.
- Ventana de tolerancia `OTP_VALID_WINDOW` (±1 paso de 30 s por defecto) y comparación en
  tiempo constante.
- En PostgreSQL la fila del usuario se bloquea (`SELECT … FOR UPDATE`) durante la verificación
  para evitar condiciones de carrera.

Casos del login (usuario, contraseña, OTP):

| Usuario | Contraseña | OTP | Resultado |
|---|---|---|---|
| No existe | – | – | Mensaje genérico (con hash ficticio para igualar tiempos) |
| Bloqueado | – | – | "Cuenta bloqueada", no se evalúa la contraseña |
| Existe | Incorrecta | – | Mensaje genérico + intento fallido |
| Existe | Correcta | Sin configurar | Se muestra el QR para configurar OTP |
| Existe | Correcta | Incorrecto / reutilizado | Mensaje genérico + intento fallido |
| Existe | Correcta | Correcto | Sesión iniciada, contador reiniciado |

## Exportar usuarios

La página **Usuarios** (requiere sesión) descarga un CSV con los datos descifrados, sin hash de
contraseña ni semilla OTP y con la tarjeta enmascarada.
