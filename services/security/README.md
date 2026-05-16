# Security Service

Microservicio de autenticación y seguridad de TravelHub.

## Responsabilidades

- Autenticación de usuarios mediante login + OTP (2FA)
- Generación y validación de tokens JWT
- Registro de auditoría de eventos de seguridad
- Control de intentos de login y bloqueo de cuentas/IPs

## Flujo de autenticación

```
1. POST /auth/login       → Verifica credenciales → Envía OTP al correo
2. POST /auth/verify-otp  → Valida OTP           → Retorna JWT
3. POST /auth/validate-token → Valida JWT         → Retorna datos del usuario
```

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/auth/login` | Iniciar login (envía OTP) |
| POST | `/api/v1/auth/verify-otp` | Verificar código OTP y obtener JWT |
| POST | `/api/v1/auth/validate-token` | Validar un token JWT |

## Modelos

- **OtpCode**: id, user_id, email, code (hasheado), roles, created_at, expires_at, is_used, attempts
- **LoginAttempt**: id, user_id, ip_address, success, failure_reason, created_at
- **AuditLog**: id, user_id, entity_type, entity_id, action, ip_address, created_at
- **UserLock**: id, email, locked_until

## Mecanismos de seguridad

- **OTP hasheado**: Los códigos OTP se almacenan con HMAC-SHA256, nunca en texto plano
- **Bloqueo de cuenta**: Después de 3 intentos fallidos de OTP, la cuenta se bloquea temporalmente
- **Bloqueo de IP**: Después de 10 intentos fallidos de login desde la misma IP, se bloquea
- **Comparación segura**: Se usa `hmac.compare_digest` para prevenir ataques de timing
- **Fail-fast en producción**: `JWT_SECRET_KEY` e `INTERNAL_API_KEY` deben configurarse explícitamente fuera de desarrollo

## Ejecución

### Con Docker (desde la raíz del monorepo)

```bash
make docker-up
# El servicio queda en http://localhost:8001
```

### Local

```bash
cd services/security
pip install -r requirements.txt
PYTHONPATH=src uvicorn entrypoints.api.main:app --reload --port 8001
```

### Tests

```bash
make security-test
# o
PYTHONPATH=services/security/src pytest services/security/tests/ -v
```

## Configuración

| Variable | Default | Descripción |
|----------|---------|-------------|
| `RDS_HOSTNAME` | `localhost` | Host de PostgreSQL |
| `RDS_PORT` | `5432` | Puerto de PostgreSQL |
| `RDS_USERNAME` | `travelhub_user` | Usuario de BD |
| `RDS_PASSWORD` | `travelhub_pass` | Contraseña de BD |
| `RDS_DB_NAME` | `travelhub` | Nombre de la BD |
| `DB_SCHEMA` | `security_schema` | Schema de PostgreSQL |
| `JWT_SECRET_KEY` | - | Clave secreta para firmar tokens JWT |
| `JWT_ALGORITHM` | `HS256` | Algoritmo de JWT |
| `JWT_EXPIRATION_MINUTES` | `30` | Tiempo de expiración del token |
| `OTP_EXPIRY_MINUTES` | `5` | Tiempo de expiración del OTP |
| `OTP_MAX_ATTEMPTS` | `3` | Intentos máximos de OTP antes de bloqueo |
| `ACCOUNT_LOCK_MINUTES` | `15` | Duración del bloqueo de cuenta |
| `IP_BLOCK_THRESHOLD` | `10` | Intentos fallidos antes de bloquear IP |
| `IP_BLOCK_WINDOW_MINUTES` | `5` | Ventana de tiempo para conteo de intentos |
| `USERS_SERVICE_URL` | `http://localhost:8000` | URL del servicio de usuarios |
| `INTERNAL_API_KEY` | - | Clave para comunicación con users service |

## Dependencias entre servicios

Este servicio se comunica con **Users Service** mediante HTTP para verificar credenciales (`POST /api/v1/internal/verify-credentials`), autenticado con `INTERNAL_API_KEY`.

## HU036 - Proteccion de datos sensibles

El servicio de seguridad centraliza los controles transversales de privacidad:

- `POST /api/v1/internal/privacy/audit` registra eventos append-only de acceso, modificacion o exportacion de PII, incluyendo actor, timestamp, IP, accion, recurso, campos PII y pais.
- Cada evento queda encadenado con `previous_hash` y `entry_hash`, lo que permite detectar alteraciones en la bitacora.
- `GET /api/v1/internal/privacy/residency?country_code=CO` resuelve la region de residencia usando `DATA_RESIDENCY_POLICIES`.
- `PII_DATA_ENCRYPTION_KEY` habilita helpers AES-256-GCM para cifrado de datos sensibles en servicios que persisten PII.
