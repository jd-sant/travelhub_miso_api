# Inventory Service

Microservicio de inventario y tarifas de TravelHub. Es el **owner** del dominio de disponibilidad y pricing hotelero para HU030:

- disponibilidad por propiedad y rango de fechas
- calendario tarifario por `rate_plan`
- preview de ajustes de tarifa
- aplicación de descuentos/cambios masivos
- historial de cambios y reversión

Este servicio es el equivalente implementado del **Sincronizador Inventario / Inventory Service** descrito en la arquitectura.

## Responsabilidades

- Exponer consultas de disponibilidad y precio efectivo para otros servicios
- Permitir que el hotel gestione tarifas y descuentos dinámicos
- Validar ownership del hotel contra `properties`
- Registrar trazabilidad del cambio (usuario, dispositivo, IP, checksum)

## Arquitectura

```text
Mobile / Search / Reservations
            ↓
       Inventory Service
            ↓
 inventory_schema (rate_plans, rate_calendar, inventory_calendar, pricing_change_log)
```

### Integraciones

- `properties`:
  - valida qué propiedades pertenecen al hotel autenticado
- `reservations`:
  - consume disponibilidad/precio efectivo para reservas del traveler
- `search`:
  - consume disponibilidad/precio efectivo para búsqueda y detalle con fechas

## Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./inventory.db` en local | URL de base de datos |
| `DB_SCHEMA` | `inventory_schema` | Schema Postgres del servicio |
| `PROPERTIES_SERVICE_URL` | `http://properties:8000` | URL base de `properties` |
| `RESERVATIONS_SERVICE_URL` | `http://reservations:8000` | URL base de `reservations` |
| `INTERNAL_API_KEY` | local/test fallback | API key interna entre servicios |
| `JWT_SECRET_KEY` | local/test fallback | Secreto para validar JWT |
| `SERVICE_REQUEST_TIMEOUT` | `5.0` | Timeout HTTP downstream |
| `ALLOWED_CORS_ORIGIN` | depende del entorno | CORS |

## API versionada

- Prefijo base: `/api/v1`
- OpenAPI version: `2.0.0`

## Endpoints

### Health
- `GET /health`

### Estado del servicio
- `GET /api/v1/inventory/status`

### Disponibilidad puntual
- `GET /api/v1/inventory/properties/{property_id}/availability`

Query params:
- `check_in`
- `check_out`
- `guests`

Respuesta:

```json
{
  "property_id": "uuid",
  "check_in": "date",
  "check_out": "date",
  "guests": 2,
  "available": true,
  "price_from": "180000.00",
  "currency": "COP"
}
```

### Gestión hotelera de tarifas

- `GET /api/v1/inventory/hotel/pricing/targets`
- `POST /api/v1/inventory/hotel/pricing/preview`
- `POST /api/v1/inventory/hotel/pricing/apply`
- `GET /api/v1/inventory/hotel/pricing/history`
- `POST /api/v1/inventory/hotel/pricing/history/{change_id}/revert`

Notas:
- `preview` y `apply` requieren `X-Pricing-Checksum`
- `apply` registra `actor_ip` y `request_checksum`

## Persistencia

Tablas principales:

- `properties`
- `room_types`
- `rate_plans`
- `inventory_calendar`
- `rate_calendar`
- `pricing_change_log`

## Tests

```bash
PYTHONPATH=src pytest tests/ -v
```

## Notas de diseño

- `search` ya no es dueño del pricing ni del inventario
- `inventory` es la fuente de verdad para disponibilidad y tarifa efectiva
- el seed local existe para facilitar validación manual y E2E en desarrollo
