# TravelHub MISO - Backend API

Monorepo del backend de TravelHub, organizado como microservicios independientes con Python, FastAPI y arquitectura hexagonal.

## Arquitectura

El proyecto sigue una arquitectura de microservicios donde cada servicio tiene su propia base de código, Dockerfile y schema de base de datos. Todos los servicios comparten una instancia de PostgreSQL pero operan en schemas aislados.

```text
travelhub_miso/
├── services/
│   ├── users/          # Gestión de usuarios y roles
│   ├── security/       # Autenticación, OTP y JWT
│   └── reservations/   # Creación y consulta de reservas
├── docker-compose.yml  # Orquestación local
├── init-schemas.sql    # Creación de schemas en PostgreSQL
├── Makefile            # Comandos de desarrollo
└── .github/workflows/  # CI/CD con GitHub Actions
```

Cada microservicio sigue arquitectura hexagonal:

```text
service/
├── src/
│   ├── adapters/          # Implementaciones concretas (repos, clientes HTTP)
│   ├── core/              # Configuración y utilidades
│   ├── db/                # Sesión y conexión a BD
│   ├── domain/
│   │   ├── ports/         # Interfaces abstractas
│   │   ├── schemas/       # DTOs de entrada y salida
│   │   └── use_cases/     # Lógica de negocio
│   └── entrypoints/
│       └── api/routers/   # Endpoints HTTP
├── tests/
├── Dockerfile
└── requirements.txt
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

| Servicio | Puerto | Schema BD | Descripción |
|----------|--------|-----------|-------------|
| [users](services/users/README.md) | 8000 | `users_schema` | Gestión de usuarios y roles |
| [security](services/security/README.md) | 8001 | `security_schema` | Autenticación, OTP y tokens JWT |
| [reservations](services/reservations/) | 8002 | `reservations_schema` | Creación y consulta de reservas |

## Ejecución local

### Requisitos previos

- Docker y Docker Compose
- Python 3.11+ (para desarrollo y tests)

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

### Tests

```bash
# Todos los servicios
make users-test
make security-test
make reservations-test

# O directamente con pytest
PYTHONPATH=services/users/src pytest services/users/tests/ -v
PYTHONPATH=services/security/src pytest services/security/tests/ -v
PYTHONPATH=services/reservations/src pytest services/reservations/tests/ -v
```

## Comandos disponibles

```bash
make help             # Ver todos los comandos
make docker-up        # Levantar servicios
make docker-down      # Detener servicios
make docker-build     # Construir imágenes
make clean            # Limpiar __pycache__
make users-test       # Tests del servicio de usuarios
make security-test    # Tests del servicio de seguridad
make reservations-test # Tests del servicio de reservas
```

## CI / CD

### CI - GitHub Actions

El workflow `pr-test-validation.yml` se ejecuta en cada PR hacia `develop`, `release` o `main`:

1. Valida que el PR tenga descripción
2. Detecta qué servicios tienen cambios
3. Ejecuta los tests solo de los servicios afectados

### CD - AWS CodePipeline

El despliegue continuo se gestiona con AWS CodePipeline. Cada servicio tiene su propio `buildspec.yml` que define los pasos de build, test y push de la imagen Docker.

## Variables de entorno

Ver `.env.example` para la lista completa. Las principales:

| Variable | Descripción |
|----------|-------------|
| `JWT_SECRET_KEY` | Clave secreta para firmar tokens JWT |
| `INTERNAL_API_KEY` | Clave para comunicación entre servicios |
