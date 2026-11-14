# today

Aplicación web en Streamlit con registro de usuarios, autenticación con **contraseña + OTP**
(TOTP con `pyotp`), roles **cliente / administrador** y exportación de usuarios a CSV.
Usa **PostgreSQL** en AWS (o SQLite para pruebas locales) y gestiona dependencias con **uv**.

Producción: <https://bleyk-lab-ciber.jhonb.dev>

## Arquitectura

```
Internet ──443/HTTPS──► nginx (webserver) ──► Streamlit 127.0.0.1:8501
                                                   │
                                                   ▼ 5432 (TLS, scram-sha-256)
                                   PostgreSQL 192.168.101.103 (sin IP pública)

PC del administrador ══ VPN Tailscale ══► webserver ──túnel SSH (dbtunnel)──► PostgreSQL
```

- **webserver** (subred pública): nginx como proxy inverso, la app y Tailscale. SSH solo es
  accesible por la VPN.
- **base-de-datos** (subred privada): PostgreSQL 18, escucha solo en `localhost` y en su IP
  privada.

## Puesta en marcha

```bash
cp .env.example .env
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# -> pegue la clave en ENCRYPTION_KEY y complete el resto del .env
uv sync --locked
uv run streamlit run src/web_app/main.py
```

Las tablas se crean (y migran) automáticamente al iniciar la app.

### Modos de conexión (`.env`)

| Escenario | Variables clave |
|---|---|
| Pruebas locales | `DB_ENGINE=sqlite` |
| App en el **webserver** | `DB_ENGINE=postgresql`, `DB_HOST=192.168.101.103`, `DB_USE_TUNNEL=false` |
| App en el **PC** (desarrollo) | Igual que arriba con `DB_USE_TUNNEL=true`, `SSH_HOST=webserver.taild46e50.ts.net`, `SSH_USER=dbtunnel`, `SSH_KEY_PATH=<ruta a la clave>` |

Con túnel, la app abre un túnel SSH (`sshtunnel`) por el webserver vía Tailscale y se conecta a
`127.0.0.1:<puerto local>`. El túnel y el pool de conexiones se reutilizan y se reconectan solos.
Todas las variables están documentadas en [.env.example](.env.example); también pueden ir en
`.streamlit/secrets.toml`. **Nunca** se suben `.env` ni claves al repositorio.

### Despliegue en el webserver (detrás de nginx)

nginx reenvía el tráfico HTTPS a `127.0.0.1:8501` (upstream `ciber`):

```bash
cd ~/today && git pull && uv sync --locked
pkill -f streamlit
nohup uv run streamlit run src/web_app/main.py --server.port 8501 --server.address 127.0.0.1 > ~/streamlit.log 2>&1 &
```

`--server.address 127.0.0.1` hace que Streamlit solo sea accesible a través de nginx.

## Roles y control de acceso

| Rol | Cómo se obtiene | Qué ve |
|---|---|---|
| Visitante | — | Home y Acceder |
| **Cliente** | Al registrarse | Mi cuenta: solo sus propios datos, con los sensibles enmascarados |
| **Administrador** | Solo por SQL: `UPDATE users SET role = 'admin' WHERE email = '...';` | Además: Equipo A/B/Chat (tablas `a` y `b`, solo lectura) y Usuarios (resumen y CSV) |

- El menú se construye según el rol y las páginas no registradas no son accesibles por URL.
- Cada página de administración vuelve a verificar el rol **en la base de datos** (no en la
  sesión), así que quitar el rol tiene efecto inmediato.
- Un cliente nunca puede asignarse el rol de admin desde la aplicación.

Por debajo, la app se conecta a PostgreSQL con un único usuario (`analyst_3`), cuyos permisos los
limita la propia base de datos (defensa en profundidad).

## Política de contraseñas

- 12 a 128 caracteres.
- Al menos una mayúscula, una minúscula, un número y un símbolo.
- No puede contener el correo ni el nombre del usuario, ni ser una contraseña común.

## Almacenamiento de secretos

| Dato | Cómo se guarda |
|---|---|
| Contraseña | Hash **Argon2id** con sal aleatoria; se re-hashea si cambian los parámetros |
| PII (documento, fecha de nacimiento, teléfono, dirección) | Cifrado **Fernet** (AES-128-CBC + HMAC-SHA256) |
| PHI (tipo de sangre, EPS, condiciones médicas) | Cifrado Fernet |
| Datos crediticios (titular, número, vencimiento, ingresos) | Cifrado Fernet; solo los últimos 4 dígitos en claro |
| CVV | **No se solicita ni almacena** (PCI DSS) |
| Semilla OTP | Cifrado Fernet |
| Clave de cifrado y credenciales de BD | Solo en `.env` / variables de entorno (excluidos de git) |

## OTP y autenticación

- Al registrarse se genera una semilla con `pyotp.random_base32()` y se muestra un QR
  (`otpauth://`). La cuenta se activa al confirmar el primer código.
- **Anti-replay**: se guarda el último *time-step* aceptado; un código ya usado se rechaza.
- **Rate limiting**: tras `MAX_LOGIN_ATTEMPTS` fallos (contraseña u OTP) la cuenta se bloquea
  `LOCKOUT_MINUTES` minutos.
- Ventana de tolerancia `OTP_VALID_WINDOW` (±1 paso de 30 s) y comparación en tiempo constante.
- En PostgreSQL la fila del usuario se bloquea (`SELECT … FOR UPDATE`) durante la verificación.

| Usuario | Contraseña | OTP | Resultado |
|---|---|---|---|
| No existe | – | – | Mensaje genérico (con hash ficticio para igualar tiempos) |
| Bloqueado | – | – | "Cuenta bloqueada", no se evalúa la contraseña |
| Existe | Incorrecta | – | Mensaje genérico + intento fallido |
| Existe | Correcta | Sin configurar | Se muestra el QR para configurar OTP |
| Existe | Correcta | Incorrecto / reutilizado | Mensaje genérico + intento fallido |
| Existe | Correcta | Correcto | Sesión iniciada, contador reiniciado |

## Otras medidas de seguridad

- Consultas parametrizadas (SQLAlchemy); los nombres de tabla legibles están en lista blanca.
- Todo texto del usuario que se muestra como HTML se escapa (prevención de XSS).
- Los visitantes no ven trazas de error (`showErrorDetails = "none"`); se registran en el log.
- Estadísticas de uso de Streamlit desactivadas.

## Estructura

| Archivo | Responsabilidad |
|---|---|
| `src/web_app/main.py` | Menú según rol, conexión inicial y manejo de errores |
| `src/web_app/config.py` | Lee `.env` / `st.secrets` y arma la URL de conexión |
| `src/web_app/db.py` | Engine, túnel SSH, migraciones, lectura de tablas y mensajes de error |
| `src/web_app/models.py` | Tabla `users` |
| `src/web_app/security.py` | Política de contraseñas, Argon2id, cifrado Fernet |
| `src/web_app/auth_service.py` | Registro, OTP, login, rate limiting, perfil, roles y CSV |
| `src/web_app/guards.py` | `require_login` / `require_admin` |
| `src/web_app/ui.py` | Estilos y componentes visuales compartidos |
| `src/web_app/all_pages/` | Páginas: Home, Acceder, Mi cuenta y Administración |
| `.streamlit/config.toml` | Tema visual y opciones de seguridad del cliente |
