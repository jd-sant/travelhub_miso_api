# Properties Service

Microservicio para gestión de detalles de propiedades en TravelHub.

## Descripción

Este servicio proporciona funcionalidad para obtener los detalles de una propiedad específica e incluye información como nombre, descripción, ubicación, precio, rating, amenidades, imágenes y reseñas.

## Stack

- Python 3.11+
- FastAPI
- SQLModel / SQLAlchemy
- Pydantic v2
- PostgreSQL 15
- Docker

## Estructura

```
src/
├── adapters/
│   ├── models/
│   │   ├── property.py
│   │   ├── property_image.py
│   │   └── property_review.py
│   └── repositories/
│       └── property_repository.py
├── core/
│   └── config.py
├── db/
│   └── session.py
├── domain/
│   ├── ports/
│   │   └── property_repository.py
│   ├── schemas/
│   │   └── property.py
│   └── use_cases/
│       ├── base.py
│       ├── get_property_detail.py
│       └── get_properties_list.py
├── entrypoints/
│   └── api/
│       ├── main.py
│       └── routers/
│           └── properties.py
├── assembly.py
└── errors.py
```

## API Endpoints

### GET /api/v1/properties

Obtiene la lista de todas las propiedades disponibles.

**Respuesta:**
```json
[
  {
    "id": "uuid",
    "name": "Modern Beachfront Penthouse",
    "description": "Stunning contemporary penthouse...",
    "location": "Miami Beach, Florida",
    "latitude": 25.7907,
    "longitude": -80.1300,
    "price_per_night": 2150.00,
    "currency": "USD",
    "rating": 4.87,
    "review_count": 42,
    "bedrooms": 3,
    "bathrooms": 3.0,
    "max_guests": 8,
    "amenities": ["Private Beach Access", "Smart Home Automation"],
    "images": [
      {
        "id": "uuid",
        "url": "/mock/property-1.svg",
        "alt_text": "Beachfront View",
        "position": 0
      }
    ],
    "status": 1
  }
]
```

### GET /api/v1/properties/{id}

Obtiene el detalle completo de una propiedad específica incluyendo reseñas.

**Parámetros:**
- `id` (UUID): ID de la propiedad

**Respuesta:**
```json
{
  "id": "uuid",
  "name": "Modern Beachfront Penthouse",
  "description": "Stunning contemporary penthouse...",
  "location": "Miami Beach, Florida",
  "latitude": 25.7907,
  "longitude": -80.1300,
  "price_per_night": 2150.00,
  "currency": "USD",
  "rating": 4.87,
  "review_count": 42,
  "bedrooms": 3,
  "bathrooms": 3.0,
  "max_guests": 8,
  "amenities": ["Private Beach Access", "Smart Home Automation"],
  "images": [
    {
      "id": "uuid",
      "url": "/mock/property-1.svg",
      "alt_text": "Beachfront View",
      "position": 0
    }
  ],
  "reviews": [
    {
      "id": "uuid",
      "author": "Sarah Holkins",
      "rating": 5,
      "date": "September 2024",
      "comment": "Amazing property!",
      "verified_stay": true
    }
  ],
  "status": 1
}
```

## Ejecución local

```bash
# Con Docker
docker build -t properties .
docker run -p 8003:8003 properties

# O con uvicorn
PYTHONPATH=src uvicorn entrypoints.api.main:app --reload --port 8003
```

### Seeding de datos

El servicio se auto-inicializa con datos de ejemplo (4 propiedades) cuando la BD está vacía. 

Para ejecutar seeding manual:

```bash
PYTHONPATH=src python seed_data.py
```

Los datos incluyen 4 propiedades con imágenes y reseñas:
- **Renaissance Estate & Private Vineyard** (Florencia)
- **Modern Beachfront Penthouse** (Miami Beach)
- **Alpine Mountain Lodge** (Chamonix)
- **Tropical Paradise Villa** (Bora Bora)

## Tests

### Ejecutar tests con Make (desde raíz del proyecto)
```bash
make properties-test
```

### Ejecutar tests con pytest (desde services/properties)
```bash
PYTHONPATH=src pytest tests/ -v
```

### Tests específicos
```bash
# Solo tests de API
PYTHONPATH=src pytest tests/test_property_api.py -v

# Solo tests de listado
PYTHONPATH=src pytest tests/test_property_api.py::test_list_properties_endpoint_success -v

# Solo tests de detalle
PYTHONPATH=src pytest tests/test_property_api.py::test_get_property_endpoint_with_seeded_data -v

# Solo tests de seeding
PYTHONPATH=src pytest tests/test_seeded_data.py -v
```

**Coverage actual:** 15+ tests pasando con 100% cobertura en funcionalidad core

Véase [TESTS_COVERAGE_REPORT.md](TESTS_COVERAGE_REPORT.md) para detalles completos.

## Health Check

```bash
GET /health
```

