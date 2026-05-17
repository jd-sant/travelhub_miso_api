# Users Service

Microservicio de gestión de usuarios y roles de TravelHub.

## Responsabilidades

- Crear y listar usuarios
- Gestionar roles y asignación de roles a usuarios
- Verificar credenciales (endpoint interno consumido por el servicio de seguridad)

## Endpoints

| Método | Ruta | Descripción | Acceso |
|--------|------|-------------|--------|
| GET | `/health` | Health check | Público |
| POST | `/api/v1/users` | Crear usuario | Público |
| GET | `/api/v1/users` | Listar usuarios | Público |
| POST | `/api/v1/internal/verify-credentials` | Verificar credenciales | Interno (requiere `X-Internal-Api-Key`) |

## Modelos

- **User**: id, email, phone, password (hasheado), status
- **Role**: id, name
- **UserRole**: user_id, role_id (tabla de asociación)

## Ejecución

### Con Docker (desde la raíz del monorepo)

```bash
make docker-up
# El servicio queda en http://localhost:8000
```

### Local

```bash
cd services/users
pip install -r requirements.txt
PYTHONPATH=src uvicorn entrypoints.api.main:app --reload --port 8000
```

### Tests

```bash
make users-test
# o
PYTHONPATH=services/users/src pytest services/users/tests/ -v
```

## Configuración

| Variable | Default | Descripción |
|----------|---------|-------------|
| `RDS_HOSTNAME` | `localhost` | Host de PostgreSQL |
| `RDS_PORT` | `5432` | Puerto de PostgreSQL |
| `RDS_USERNAME` | `travelhub_user` | Usuario de BD |
| `RDS_PASSWORD` | `travelhub_pass` | Contraseña de BD |
| `RDS_DB_NAME` | `travelhub` | Nombre de la BD |
| `DB_SCHEMA` | `users_schema` | Schema de PostgreSQL |
| `INTERNAL_API_KEY` | - | Clave para el endpoint interno |

## HU036 - PII, auditoria y residencia

Users es la fuente de verdad del perfil de usuario y por eso aplica los controles de privacidad de HU036:

- `USERS_PII_ENCRYPTION_ENABLED=true` cifra `email`, `phone`, `full_name` y `hotel_name` con AES-256-GCM antes de persistirlos.
- `email_lookup_hash` permite login y deteccion de duplicados sin depender del email en texto plano.
- `country_code` y `data_region` se calculan desde `DATA_RESIDENCY_POLICIES` para soportar residencia de datos por pais.
- Los endpoints que acceden, crean o exportan PII emiten auditoria central al Security Service cuando `PRIVACY_AUDIT_ENABLED=true`.
- En entornos no dev/test, `ENFORCE_TLS_HEADER=true` rechaza operaciones PII sin `X-Forwarded-Proto: https`.
