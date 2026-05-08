# Reporte Coverage por Microservicio

## Ejecucion

- Fecha: 26 de abril de 2026
- Fuente: ejecucion local de `pytest` con `coverage` por cada microservicio en `services/`
- Evidencia cruda: `tests/coverage_evidence/*.log` y `tests/coverage_evidence/summary.tsv`

## Comando base usado por servicio

```bash
PYTHONPATH=src python -m coverage run -m pytest tests -v
python -m coverage report -m
```

## Resultado por microservicio

| Microservicio | Resultado tests | Coverage TOTAL | Lineas (stmts/miss) | Exit Code |
|---|---|---:|---:|---:|
| users | 36 passed in 5.34s | 92% | 863 / 65 | 0 |
| security | 26 passed in 1.74s | 92% | 936 / 78 | 0 |
| reservations | 110 passed in 14.69s | 89% | 3988 / 450 | 0 |
| payments | 75 passed in 3.48s | 89% | 3780 / 434 | 0 |
| notifications | 27 passed in 1.47s | 88% | 1437 / 171 | 0 |
| properties | 34 passed in 1.87s | 92% | 1210 / 100 | 0 |
| search | 54 passed, 2 skipped in 1.26s | 93% | 1301 / 88 | 0 |

## Resumen global

- Microservicios evaluados: 7/7
- Corridas con exit code 0: 7/7
- Coverage promedio simple: 90.71%
- Coverage minimo: 88% (`notifications`)
- Coverage maximo: 93% (`search`)

## Artefactos

- Resumen tabular: `tests/coverage_evidence/summary.tsv`
- Log users: `tests/coverage_evidence/users.log`
- Log security: `tests/coverage_evidence/security.log`
- Log reservations: `tests/coverage_evidence/reservations.log`
- Log payments: `tests/coverage_evidence/payments.log`
- Log notifications: `tests/coverage_evidence/notifications.log`
- Log properties: `tests/coverage_evidence/properties.log`
- Log search: `tests/coverage_evidence/search.log`
