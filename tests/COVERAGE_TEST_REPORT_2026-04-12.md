# Reporte de Tests con Coverage

Fecha de ejecución: 13 de abril de 2026
Workspace: travelhub_miso

## Resumen Ejecutivo

- Estado general: exitoso (actualizado tras agregar nuevas pruebas).
- Servicios ejecutados: 7/7.
- Total de tests ejecutados: 218.
- Resultado consolidado:
  - Passed: 213
  - Skipped: 2
  - Failed: 3
- Coverage global ponderado aproximado (suma de líneas): 91.60%

## Comando de referencia usado

Se ejecutó cobertura por servicio con el intérprete local del entorno virtual, usando:
- coverage run -m pytest tests/ -v
- coverage report -m

## Resultados por servicio

| Servicio | Resultado tests | Coverage TOTAL |
|---|---|---|
| users | 28 passed | 92% (756 stmts, 60 miss) |
| security | 22 passed | 91% (887 stmts, 78 miss) |
| reservations | 39 passed, 3 failed | 91% (1006 stmts, 90 miss) |
| payments | 44 passed | 90% (2202 stmts, 218 miss) |
| notifications | 15 passed | 92% (840 stmts, 70 miss) |
| properties | 16 passed | 95% (557 stmts, 30 miss) |
| search | 49 passed, 2 skipped | 93% (1189 stmts, 79 miss) |

## Evidencia cruda

- Resumen tabular parseado: tests/coverage_evidence/summary.tsv
- Log users: tests/coverage_evidence/users.log
- Log security: tests/coverage_evidence/security.log
- Log reservations: tests/coverage_evidence/reservations.log
- Log payments: tests/coverage_evidence/payments.log
- Log notifications: tests/coverage_evidence/notifications.log
- Log properties: tests/coverage_evidence/properties.log
- Log search: tests/coverage_evidence/search.log

## Notas

- Durante la preparación del entorno local se corrigió metadata corrupta de pydantic_core en .venv para permitir instalar dependencias y ejecutar la corrida completa.
- Se agregaron pruebas unitarias/integración enfocadas en módulos con baja cobertura en reservations/payments/notifications/search.
- Todos los servicios quedaron en >= 90% de coverage total.
