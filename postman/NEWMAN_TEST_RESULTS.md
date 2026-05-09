# Newman Test Results - Postman Suite

## Ejecucion

- Fecha: 26 de abril de 2026
- Tipo de corrida: Newman, coleccion por coleccion (contract + functional + e2e + perf)
- Reporters usados: JSON (artefactos) + consolidado en `postman/reports/latest-newman-run/summary.csv`

## Resumen Global

- Colecciones ejecutadas: 15
- Colecciones aprobadas: 15
- Colecciones fallidas: 0
- Assertions aprobadas: 316
- Assertions fallidas: 0

## Configuracion usada por prueba y resultado

| Coleccion | Scope | Configuracion usada | Exit Code | Assertions aprobadas |
|---|---|---|---:|---:|
| travelhub-notifications-contract.postman_collection.json | contract | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 6/6 |
| travelhub-notifications.postman_collection.json | functional | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 5/5 |
| travelhub-payments-contract.postman_collection.json | contract | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 15/15 |
| travelhub-payments.postman_collection.json | functional | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 27/27 |
| travelhub-payments-stripe-evidence.postman_collection.json | functional | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 8/8 |
| travelhub-properties-contract.postman_collection.json | contract | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 6/6 |
| travelhub-reservations-contract.postman_collection.json | contract | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 35/35 |
| travelhub-search-contract.postman_collection.json | contract | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 6/6 |
| travelhub-security-contract.postman_collection.json | contract | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 3/3 |
| travelhub-users-contract.postman_collection.json | contract | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 2/2 |
| travelhub-payments-reservations-e2e.postman_collection.json | e2e | env:postman/environments/travelhub-payments-reservations-local.postman_environment.json | 0 | 17/17 |
| reservation_modification_cancellation_refunds.postman_collection.json | e2e | env:postman/environments/travelhub-payments-reservations-local.postman_environment.json | 0 | 31/31 |
| travelhub-reservation-payment-failure-checkstatus-e2e.postman_collection.json | e2e | env:postman/environments/travelhub-payments-reservations-local.postman_environment.json | 0 | 12/12 |
| reservations_checkstatus.postman_collection.json | e2e | vars:base_url=http://localhost:8002;INTERNAL_API_KEY=travelhub-internal-secret-key | 0 | 12/12 |
| search_p95.postman_collection.json | perf | vars:base_url=http://localhost:8006;iteration-count=130 | 0 | 131/131 |

## Colecciones con fallas

Ninguna.

## Evidencia de salida

- Consolidado: `postman/reports/latest-newman-run/summary.csv`
- Resultados JSON por coleccion: `postman/reports/latest-newman-run/results/`

## Resultado

La suite Newman queda en verde en esta corrida. Se actualizaron los resultados y artefactos para reflejar el estado real del branch `develop` al momento de la ejecucion.
