# Block 8 - Exit Checklist

Fecha: 2026-04-07
Servicio: search

## 1) Criterios de aceptacion cubiertos por pruebas

- [x] Busqueda exitosa con paginacion.
- [x] Filtros por amenidades.
- [x] Filtros por precio.
- [x] Sin resultados + empty state.
- [x] Validaciones inline (`422`).
- [x] Reglas de negocio (`400`) para fechas y rango de precio.
- [x] Limites de `page` y `page_size`.
- [x] Cobertura por capas:
  - endpoint
  - repositorio
  - use case

## 2) Endpoint documentado y versionado

- [x] Versionado por ruta: `/api/v1/search`.
- [x] Version OpenAPI declarada: `1.0.0`.
- [x] Documentacion de uso y errores en `services/search/README.md`.

## 3) Performance validada

- [x] Objetivo p95 < 800 ms validado.
- [x] Evidencia con benchmark local en `services/search/PERFORMANCE.md`.
- [x] Escenario con seed ampliado (1000 propiedades) incluido.

## 4) Integracion local funcional

- [x] Search integrado en `docker-compose.yml` (puerto 8003).
- [x] Comandos de monorepo para search en `Makefile`.
- [x] Flujo local y comandos reflejados en `README.md`.

## 5) Evidencia para PR

### Suite search

Comando:

```bash
make search-test
```

Resultado esperado:

- `19 passed`

### Benchmark p95

Comando:

```bash
make search-perf
```

Resultado esperado con seed actual:

- p95 en milisegundos, objetivo `p95 < 800 ms`.
