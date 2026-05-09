# Search Service - Performance Notes

## Estado actual (post-refactor stateless)

A partir de la versión 2.0 el servicio dejó de tener base de datos local (SQLite/Postgres). Cada request encadena dos llamadas HTTP internas (`properties` + `reservations`), por lo que el baseline anterior — **p95 ≈ 21 ms con la DB local** — ya no aplica.

El nuevo baseline depende de:

- Latencia de la red interna entre los servicios (en docker-compose suele ser ≪1 ms; en ECS dentro de la misma VPC suele ser <5 ms).
- Latencia de cada servicio downstream (properties y reservations).
- Hit ratio del cache Redis. En cache hit, la latencia es comparable a la implementación previa (no hay llamadas HTTP).

## Cómo medir

Con el stack levantado:

```bash
docker-compose up -d postgres redis properties reservations search

# Smoke
curl -s "http://localhost:8006/api/v1/search?city=Bogot%C3%A1&check_in=2026-06-10&check_out=2026-06-15&guests=2&page=1&page_size=10" | jq

# Newman benchmark con la collection de Postman (ver carpeta benchmarks/)
newman run benchmarks/search.postman_collection.json -n 150
```

Targets sugeridos (a re-validar tras el refactor):

| Métrica | Target |
|---------|--------|
| p95 cache miss | ≤ 800 ms |
| p95 cache hit | ≤ 200 ms |
| 100 búsquedas concurrentes p99 | ≤ 1200 ms |
| Tasa de error | < 1% |

Si properties o reservations caen, search devuelve `503` (no degrada silenciosamente).

## Re-baseline pendiente

El primer despliegue post-refactor debe documentar aquí el nuevo p95 medido para fijar el SLO real. Con cache habilitado y los servicios sanos en docker-compose local se espera un p95 cache miss en el rango **20-80 ms** (dos saltos HTTP cortos). En ECS con los servicios en la misma VPC el p95 esperado es **40-150 ms**.
