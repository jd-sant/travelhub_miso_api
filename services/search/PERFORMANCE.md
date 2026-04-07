# Search Service Performance Evidence

Fecha: 2026-04-07
Objetivo: p95 < 800 ms para el endpoint de busqueda.

## 1) Indices implementados

Se agregaron indices orientados a los filtros y joins de la consulta principal:

- `search_schema.propiedades`
  - `ix_propiedades_ciudad`
  - `ix_propiedades_lower_ciudad`
  - `ix_propiedades_estado_activo`
  - `ix_propiedades_capacidad_maxima`
  - `ix_propiedades_rating`
  - `ix_propiedades_ciudad_estado`
- `search_schema.tipos_habitacion`
  - `ix_tipos_habitacion_propiedad_id`
  - `ix_tipos_habitacion_capacidad`
  - `ix_tipos_habitacion_estado_activo`
  - `ix_tipos_habitacion_propiedad_estado_capacidad`
- `search_schema.planes_tarifa`
  - `ix_planes_tarifa_tipo_habitacion_id`
  - `ix_planes_tarifa_estado_activo`
  - `ix_planes_tarifa_tipo_estado_precio`
- `search_schema.calendario_inventario`
  - `ix_calendario_inventario_tipo_habitacion_id`
  - `ix_calendario_inventario_fecha`
  - `ix_calendario_inventario_tipo_fecha_disponibilidad`
- `search_schema.calendario_tarifas`
  - `ix_calendario_tarifas_plan_tarifa_id`
  - `ix_calendario_tarifas_fecha`
  - `ix_calendario_tarifas_plan_fecha_precio`
- `search_schema.amenidades`
  - `ix_amenidades_lower_nombre`
- `search_schema.propiedad_amenidad`
  - `ix_propiedad_amenidad_amenidad_id`
  - `ix_propiedad_amenidad_amenidad_propiedad`

## 2) Medicion local reproducible

Script: `services/search/tests/benchmark_p95.py`

Comando ejecutado:

```bash
make search-perf
```

Resultado obtenido (baseline inicial):

- requests: 120
- avg: 2.61 ms
- p50: 2.50 ms
- p95: 3.16 ms
- p99: 3.93 ms
- estado: PASS (`p95 < 800 ms`)

Resultado obtenido (dataset ampliado a 1000 propiedades):

- requests: 120
- avg: 7.52 ms
- p50: 7.33 ms
- p95: 8.91 ms
- p99: 9.72 ms
- estado: PASS (`p95 < 800 ms`)

Tabla comparativa (baseline vs 1000 propiedades):

| Escenario | requests | avg (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Objetivo p95 < 800 ms |
|-----------|----------|----------|----------|----------|----------|-------------------------|
| Baseline inicial | 120 | 2.61 | 2.50 | 3.16 | 3.93 | PASS |
| Seed 1000 propiedades | 120 | 7.52 | 7.33 | 8.91 | 9.72 | PASS |

## 3) Supuestos de la medicion

- Entorno local Docker Compose.
- Entorno `development` con seeding activo.
- Dataset dummy local generado por seeding (>= 1000 propiedades).
- Verificacion de volumen mediante endpoint de diagnostico:
  - `GET /api/v1/search/test-dataset`
- Query de referencia:
  - ciudad=Bogota
  - check_in=2026-04-10
  - check_out=2026-04-12
  - huespedes=2
  - page=1
  - page_size=10

## 4) Interpretacion de resultados

- Aun con 1000 propiedades, el p95 medido localmente permanece muy por debajo del umbral objetivo de 800 ms.
- El aumento de latencia respecto al baseline es esperado por mayor volumen de datos y sigue dentro de margen saludable.
- La prueba usa una carga secuencial controlada (no concurrencia alta), util para regression check rapido.

## 5) Plan de monitoreo recomendado

1. Instrumentar metricas por endpoint:
   - latencia (`p50/p95/p99`) por ruta y status code.
   - throughput (RPS).
   - tasa de error (`4xx/5xx`).
2. Dashboard minimo (por ambiente):
   - `search /api/v1/search` p95 y p99 en ventanas de 5m y 1h.
   - uso de CPU/memoria del contenedor.
   - conexiones activas a PostgreSQL.
3. Alertas:
   - alerta warning: p95 > 500 ms por 10 min.
   - alerta critical: p95 > 800 ms por 5 min.
   - alerta error-rate: 5xx > 1% por 5 min.
4. Rutina de verificacion:
   - ejecutar `make search-perf` antes de merge en cambios de consulta o indices.
   - revisar plan de ejecucion (`EXPLAIN ANALYZE`) cuando p95 suba.
