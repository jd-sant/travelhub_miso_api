# Reservations Service

Servicio de reservas de TravelHub. Gestiona la creación, consulta y actualización de reservas bajo el schema `reservations_schema`.

## Stack

- FastAPI 0.135.2
- SQLModel 0.0.27
- PostgreSQL 15
- Pytest

## Estructura

- `src/domain/` - casos de uso, puertos y schemas
- `src/adapters/` - repositorios SQLModel y modelos ORM
- `src/entrypoints/api/` - routers FastAPI
- `src/db/` - sesión y creación de tablas
- `tests/` - pruebas unitarias y de endpoints

## Ejecutar pruebas

```bash
cd services/reservations
PYTHONPATH=src pytest tests/ -v
```

## Prueba E2E con Newman (Postman)

Colección disponible en `perf/reservations_checkstatus.postman_collection.json`.

Ejecutar desde la raíz del monorepo:

```bash
make reservations-perf
```

Nota: este comando toma `INTERNAL_API_KEY` desde el `.env` de la raíz del monorepo (si existe).

O ejecutar directamente con Newman:

```bash
npx --yes newman run services/reservations/perf/reservations_checkstatus.postman_collection.json --env-var base_url=http://localhost:8002 --reporters cli
```

Variables de colección:

- `base_url`: URL del servicio reservations (por defecto `http://localhost:8002`)
- `INTERNAL_API_KEY`: API key interna para el endpoint PATCH; debe coincidir con la variable `INTERNAL_API_KEY` del servicio
- `WRONG_INTERNAL_API_KEY`: valor inválido para validar respuesta `403`

## Endpoints públicos

### Crear reservación

`POST /api/v1/reservations`

Crea una reserva con estado inicial `pending_payment`.

### Obtener reservación

`GET /api/v1/reservations/{reservation_id}`

Retorna el detalle completo de la reserva.

### Verificar estado de reserva

`GET /api/v1/reservations/{reservation_id}/checkstatus`

Consulta la reserva y, si el estado actual es `pending_payment`, ejecuta una transición a `cancelled` mediante el flujo interno del servicio.

Respuesta:

- `reservation`: reserva actualizada o sin cambios
- `status_before`: estado antes de la validación
- `status_after`: estado final
- `action_applied`: `cancelled` o `none`

## Endpoint interno

### Actualizar estado de reservación

`PATCH /api/v1/internal/reservations/{reservation_id}/status`

Encapsula la actualización de estado para trazabilidad interna.

Header requerido:

- `X-Internal-Api-Key`

Body:

```json
{
  "status": "cancelled"
}
```

## Notas

- La validación de disponibilidad solo ignora reservas canceladas.
- El estado inicial de una reserva creada por el servicio es `pending_payment`.
- El flujo de `checkstatus` está pensado para ser consumido por la capa que coordina el hold de pago.
