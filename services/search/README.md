# Search Service

Microservicio de búsqueda de propiedades de TravelHub.

## API versionada

- Prefijo base versionado: `/api/v1`
- Version OpenAPI: `1.0.0`

## Endpoints

### Health

- `GET /health`
- Respuesta:

```json
{
  "status": "healthy"
}
```

### Estado del servicio

- `GET /api/v1/search/status`
- Respuesta:

```json
{
  "service": "search",
  "status": "ok"
}
```

### Búsqueda de propiedades

- `GET /api/v1/search`
- Query params obligatorios:
  - `ciudad`
  - `check_in` (YYYY-MM-DD)
  - `check_out` (YYYY-MM-DD)
  - `huespedes`
- Query params opcionales:
  - `amenidades` (repetible)
  - `precio_min`
  - `precio_max`
  - `order_by` (`price|rating|name`)
  - `order_dir` (`asc|desc`)
  - `page` (>= 1)
  - `page_size` (1..100)

Ejemplo:

```http
GET /api/v1/search?ciudad=Bogota&check_in=2026-04-10&check_out=2026-04-12&huespedes=2&page=1&page_size=10
```

Respuesta:

```json
{
  "items": [
    {
      "id": "uuid",
      "nombre": "Hotel Demo Search 01",
      "ciudad": "Bogota",
      "pais": "Colombia",
      "capacidad_maxima": 3,
      "imagen_principal_url": "https://cdn.example.com/hotel-01.jpg",
      "rating": 4.2,
      "precio_desde": "98.00",
      "moneda": "USD",
      "amenidades": ["wifi", "piscina"]
    }
  ],
  "pagination": {
    "total": 120,
    "page": 1,
    "page_size": 10,
    "total_pages": 12
  },
  "empty_state": []
}
```

## Errores

- `422`: faltantes o formato invalido de query params.
- `400`: reglas de negocio invalidas.
  - `check_out` debe ser mayor que `check_in`.
  - `precio_min` no puede ser mayor que `precio_max`.

## Endpoint de diagnostico local

Disponible solo en entorno `development`:

- `GET /api/v1/search/test-dataset`

Se usa para validar volumen de seed y pruebas locales en Postman.

## Performance

Evidencia y plan de monitoreo en:

- `services/search/PERFORMANCE.md`
