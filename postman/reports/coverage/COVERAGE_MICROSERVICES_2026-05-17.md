# Reporte Coverage por Microservicio

## Ejecucion

- Fecha: 17 de mayo de 2026
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
| users | 42 passed in 6.68s | 88% | 1250 / 150 | 0 |
| security | 33 passed in 3.89s | 91% | 1248 / 110 | 0 |
| reservations | 145 passed in 12.97s | 90% | 4686 / 488 | 0 |
| payments | 78 passed in 4.92s | 89% | 3829 / 428 | 0 |
| notifications | 56 passed in 2.11s | 89% | 2251 / 239 | 0 |
| properties | 1 failed, 112 passed, 7 warnings in 142.92s (0:02:22) | 93% | 2446 / 173 | 1 |
| search | 74 passed in 0.69s | 93% | 1367 / 90 | 0 |
| inventory | no tests ran in 0.01s | N/A | N/A | 5 |

## Resumen global

- Microservicios evaluados: 8/8
- Corridas con exit code 0: 6/8
- Microservicios con coverage medible: 7/8
- Coverage promedio simple: 90.43%
- Coverage minimo: 88% (`users`)
- Coverage maximo: 93% (`properties`)

## Artefactos

- Resumen tabular: `tests/coverage_evidence/summary.tsv`
- Log users: `tests/coverage_evidence/users.log`
- Log security: `tests/coverage_evidence/security.log`
- Log reservations: `tests/coverage_evidence/reservations.log`
- Log payments: `tests/coverage_evidence/payments.log`
- Log notifications: `tests/coverage_evidence/notifications.log`
- Log properties: `tests/coverage_evidence/properties.log`
- Log search: `tests/coverage_evidence/search.log`
- Log inventory: `tests/coverage_evidence/inventory.log`
