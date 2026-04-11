# Search Service Performance Evidence (Newman)

Fecha: 2026-04-10
Objetivo SLO local: p95 < 800 ms para `GET /api/v1/search`.

## 1) Alcance de la medicion

- Metodo: benchmark con Newman (Postman collection).
- Entorno: Docker Compose local, `APP_ENV=development`.
- Dataset: seed activo en development.
- Endpoint bajo prueba:
  - `GET /api/v1/search?city=Bogota&check_in=2026-04-10&check_out=2026-04-12&guests=2&page=1&page_size=10`

## 2) Verificacion del volumen de datos

Comando ejecutado:

```bash
curl -s http://localhost:8006/api/v1/search/test-dataset | jq '{count_properties:(.properties|length), first:(.properties[0].name), last:(.properties[-1].name)}'
```

Resultado:

- `count_properties`: 1000
- `first`: `Hotel Demo Search 01`
- `last`: `Hotel Demo Search 1000`

## 3) Ejecucion reproducible

Comando del proyecto:

```bash
make search-perf
```

Comando interno que ejecuta el target:

```bash
npx --yes newman run postman/e2e/search-p95/search_p95.postman_collection.json --env-var base_url=http://localhost:8006 --iteration-count 130 --reporters cli
```

Notas de la corrida:

- Iteraciones totales: 130
- Ventana efectiva para metricas custom: 120 requests (descarta warmup inicial)
- Assertions: 131 ejecutadas, 0 fallidas

## 4) Resultados Newman (corrida actual)

Metricas custom reportadas por la coleccion:

- requests: 120
- avg_ms: 17.05
- p50_ms: 17.00
- p95_ms: 21.00
- p99_ms: 23.00
- regla de aceptacion: PASS (`p95 < 800 ms`)

Resumen global del CLI de Newman:

- average response time: 10 ms
- min: 8 ms
- max: 52 ms
- standard deviation: 3 ms
- failed requests: 0

## 5) Conclusiones

- El objetivo de performance se cumple ampliamente: `p95=21 ms` << `800 ms`.
- Con dataset de 1000 propiedades, el endpoint mantiene latencia baja y estable en esta carga secuencial local.
- Esta evidencia queda como baseline actual para detectar regresiones en cambios futuros de filtros, joins o indices.
