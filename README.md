# TravelHub MISO - Backend API

Monorepo del backend de TravelHub, organizado como microservicios independientes con Python, FastAPI y arquitectura hexagonal.

## Arquitectura

El proyecto sigue una arquitectura de microservicios donde cada servicio tiene su propia base de codigo, Dockerfile y schema de base de datos. Todos los servicios comparten una instancia de PostgreSQL pero operan en schemas aislados.

```text
travelhub_miso/
|-- services/
|   |-- users/          # Gestion de usuarios y roles
|   |-- security/       # Autenticacion, OTP y JWT
|   |-- properties/     # Detalles de propiedades
|   |-- reservations/   # Creacion y consulta de reservas
|   |-- payments/       # Pagos tokenizados y recibos
|   |-- notifications/  # Confirmaciones y notificaciones de pago
|   `-- search/         # Busqueda de propiedades y disponibilidad
|-- docker-compose.yml  # Orquestacion local
|-- init-schemas.sql    # Creacion de schemas en PostgreSQL
|-- Makefile            # Comandos de desarrollo
`-- .github/workflows/  # CI/CD con GitHub Actions
```

Cada microservicio sigue arquitectura hexagonal:

```text
service/
|-- src/
|   |-- adapters/          # Implementaciones concretas
|   |-- core/              # Configuracion y utilidades
|   |-- db/                # Sesion y conexion a BD
|   |-- domain/
|   |   |-- ports/         # Interfaces abstractas
|   |   |-- schemas/       # DTOs de entrada y salida
|   |   `-- use_cases/     # Logica de negocio
|   `-- entrypoints/
|       `-- api/routers/   # Endpoints HTTP
|-- tests/
|-- Dockerfile
`-- requirements.txt
```

## Stack

- Python 3.11+
- FastAPI
- SQLModel / SQLAlchemy
- Pydantic v2
- PostgreSQL 15
- Docker Compose
- Pytest
- GitHub Actions

## Servicios

| Servicio | Puerto | Schema BD | Descripcion |
|----------|--------|-----------|-------------|
| `users` | 8000 | `users_schema` | Gestion de usuarios y roles |
| `security` | 8001 | `security_schema` | Autenticacion, OTP y tokens JWT |
| `reservations` | 8002 | `reservations_schema` | Creacion y consulta de reservas |
| `payments` | 8003 | `payments_schema` | Procesamiento seguro de pagos con token |
| `notifications` | 8004 | `notifications_schema` | Confirmaciones y notificaciones de pago |
| `properties` | 8005 | `properties_schema` | Detalles de propiedades y hospedajes |
| [search](services/search/) | 8006 | `search_schema` | Búsqueda de propiedades, filtros y disponibilidad |

## Ejecucion local

### Requisitos previos

- Docker y Docker Compose
- Python 3.11+ para desarrollo y tests

### Con Docker Compose

```bash
# Copiar variables de entorno
cp .env.example .env

# Levantar todos los servicios
make docker-up

# Ver logs
make docker-logs
```

Los servicios quedan disponibles en:

- Users: http://localhost:8000
- Security: http://localhost:8001
- Reservations: http://localhost:8002
- Payments: http://localhost:8003
- Notifications: http://localhost:8004
- Properties: http://localhost:8005
- Search: http://localhost:8006

### Tests

```bash
# Con make (recomendado)
make users-test
make security-test
make reservations-test
make payments-test
make notifications-test
make properties-test
make search-test

PYTHONPATH=services/users/src pytest services/users/tests/ -v
PYTHONPATH=services/security/src pytest services/security/tests/ -v
PYTHONPATH=services/reservations/src pytest services/reservations/tests/ -v
PYTHONPATH=services/payments/src pytest services/payments/tests/ -v
PYTHONPATH=services/notifications/src pytest services/notifications/tests/ -v
PYTHONPATH=services/properties/src pytest services/properties/tests/ -v
PYTHONPATH=services/search/src pytest services/search/tests/ -v
```

## Comandos disponibles

```bash
make help              # Ver todos los comandos
make docker-up         # Levantar servicios
make docker-down       # Detener servicios
make docker-build      # Construir imágenes
make clean             # Limpiar __pycache__
make users-test        # Tests del servicio de usuarios
make security-test     # Tests del servicio de seguridad
make reservations-test # Tests del servicio de reservas
make payments-test     # Tests del servicio de pagos
make notifications-test # Tests del servicio de notificaciones
make properties-test   # Tests del servicio de propiedades
make search-test      # Tests del servicio de búsqueda
make search-build     # Build del servicio de búsqueda
make search-logs      # Logs del servicio de búsqueda
make search-perf      # Benchmark p95 del servicio de búsqueda
```

## CI / CD

### CI - GitHub Actions

El workflow `pr-test-validation.yml` se ejecuta en cada PR hacia `develop`, `release` o `main`:

1. Valida que el PR tenga descripcion.
2. Detecta que servicios tuvieron cambios.
3. Ejecuta los tests solo de los servicios afectados.

### CD - AWS CodeBuild

Cada servicio mantiene su propio `buildspec.yml` para pruebas y build de imagen.

## Seguridad financiera

- `payments` soporta flujo token-only con Stripe (`stripe_test`) y endurecimiento opcional por `PAYMENTS_COMPLIANCE_MODE`.
- El backend rechaza campos de tarjeta fuera del contrato HTTP y no persiste PAN, CVV ni fecha de expiracion.
- Las referencias sensibles de checkout se cifran en reposo a nivel de aplicacion.
- Las suites de `payments` y `notifications` incluyen pruebas de postura de seguridad ejecutadas por CI.
- Para validar HU-ARQ-05 de punta a punta, el frontend debe operar con `NUXT_PUBLIC_PAYMENTS_COMPLIANCE_MODE=true` y el backend con `PAYMENTS_COMPLIANCE_MODE=true` + `PAYMENT_PROVIDER=stripe_test`.
- El script `security:scan` no esta definido en este repositorio backend; se ejecuta en el repositorio frontend [ngcaicedo/travelhub_frontend](https://github.com/ngcaicedo/travelhub_frontend) para detectar PAN hardcodeado, logs inseguros y patrones que contradigan el flujo token-only.

## Variables de entorno

Ver `.env.example` para la lista minima. Variables principales:

| Variable | Descripcion |
|----------|-------------|
| `JWT_SECRET_KEY` | Clave secreta para firmar tokens JWT |
| `INTERNAL_API_KEY` | Clave para comunicacion entre servicios |
| `PAYMENT_INTEGRITY_SECRET` | Secreto para checksum e integridad de requests de pago |
