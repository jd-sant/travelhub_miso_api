# Search Service

Microservicio de búsqueda avanzada de TravelHub. **Stateless**: no tiene base de datos propia. Orquesta dos llamadas HTTP por request:

1. `GET /api/v1/properties/search` (servicio `properties`) → metadata + filtros + paginación.
2. `POST /api/v1/internal/reservations/availability-check` (servicio `reservations`) → propiedades bloqueadas para el rango de fechas.

El servicio combina ambas respuestas, descarta las propiedades sin disponibilidad y devuelve el contrato esperado por frontend y mobile. La única persistencia es Redis, usado como cache opcional.

## Arquitectura

```
HTTP request
   ↓
SearchPropertiesUseCase
   ├─ cache.get(key)            (Redis, opcional)
   ├─ properties.search(filters) → http://properties:8000/api/v1/properties/search
   ├─ reservations.availability_check(ids, range)
   │       → http://reservations:8000/api/v1/internal/reservations/availability-check
   ├─ merge + map (city/country split, price_from = price_per_night, etc.)
   └─ cache.set(key, result)
```

Ports & adapters:
- `domain/ports/properties_service.py` → `adapters/services/properties_service_client.py` (`HttpPropertiesServiceClient`)
- `domain/ports/reservations_service.py` → `adapters/services/reservations_service_client.py` (`HttpReservationsServiceClient`)
- `domain/ports/cache_port.py` → `adapters/cache/redis_cache.py` (`RedisCache`)

## Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `PROPERTIES_SERVICE_URL` | `http://properties:8000` | URL base del microservicio properties |
| `RESERVATIONS_SERVICE_URL` | `http://reservations:8000` | URL base del microservicio reservations |
| `INTERNAL_API_KEY` | `""` | API key compartido para los endpoints `/internal/*` de reservations |
| `SERVICE_REQUEST_TIMEOUT` | `5.0` | Timeout HTTP en segundos para llamadas downstream |
| `REDIS_HOST` | `localhost` | Host Redis |
| `REDIS_PORT` | `6379` | Puerto Redis |
| `REDIS_CACHE_ENABLED` | `true` | Activar cache (silent failure si Redis cae) |
| `REDIS_CACHE_TTL_SECONDS` | `300` | TTL del cache en segundos |
| `ALLOWED_CORS_ORIGIN` | (varía por env) | Lista separada por comas |

## API versionada

- Prefijo base: `/api/v1`
- OpenAPI version: `2.0.0`

## Endpoints

### Health
`GET /health` → `{"status": "healthy"}`

### Estado
`GET /api/v1/search/status` → `{"service": "search", "status": "ok"}`

### Búsqueda avanzada

`GET /api/v1/search`

Query params **obligatorios**:
- `city` (str, 2-120 chars)
- `check_in` (YYYY-MM-DD)
- `check_out` (YYYY-MM-DD)
- `guests` (int ≥ 1)

Query params **opcionales**:
- `amenities` (repetible, case-insensitive — ej. `?amenities=wifi&amenities=piscina`)
- `min_price`, `max_price` (decimal)
- `order_by` (`price` | `rating` | `name`, default `price`)
- `order_dir` (`asc` | `desc`, default `asc`)
- `page` (≥ 1, default 1)
- `page_size` (1-100, default 10)

Respuesta:
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "string",
      "city": "string",        // derivado de properties.location split por ","
      "country": "string",
      "max_capacity": int,     // = properties.max_guests
      "main_image_url": "string|null",  // imagen con is_cover=true
      "rating": float,
      "price_from": "decimal", // = properties.price_per_night
      "currency": "string",
      "amenities": ["string"]
    }
  ],
  "pagination": { "total": int, "page": int, "page_size": int, "total_pages": int },
  "empty_state": [
    { "code": "TRY_OTHER_CITY|TRY_OTHER_DATES", "message": "string" }
  ]
}
```

Códigos de respuesta:
- `200` éxito
- `400` reglas de negocio (check_out ≤ check_in, min_price > max_price, order_by inválido, etc.)
- `422` parámetros faltantes o fuera de rango
- `503` properties o reservations caídos

### Disponibilidad puntual

`GET /api/v1/search/properties/{property_id}/availability?check_in=...&check_out=...&guests=...`

Combina `properties.status` (debe estar activa y soportar capacidad) + ausencia de reservas solapando `[check_in, check_out)` en `reservations`.

Respuesta:
```json
{
  "property_id": "uuid",
  "check_in": "date",
  "check_out": "date",
  "guests": int,
  "available": bool,
  "price_from": "float|null",  // precio sólo si está disponible
  "currency": "string|null"
}
```

## Tests

```
PYTHONPATH=src pytest tests/ -v
```

Los tests usan fakes in-memory (`FakePropertiesServiceClient`, `FakeReservationsServiceClient`) que cumplen los ports — no requieren Postgres ni servicios reales corriendo.

## Notas de migración

Versiones previas (≤1.x) tenían base de datos propia con tablas duplicadas (`properties`, `amenities`, `room_types`, etc.) cargadas vía seed manual. Esa duplicación fue removida; ahora el catálogo es la única fuente de verdad en `properties` y la disponibilidad por fechas se deriva de las reservas en `reservations`.
