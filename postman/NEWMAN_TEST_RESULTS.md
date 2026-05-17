# Newman Test Results - Postman Suite

## Ejecucion

- Fecha: 17 de mayo de 2026
- Tipo de corrida: Newman, coleccion por coleccion (contract + functional + e2e + perf)
- Reporters usados: JSON (artefactos) + consolidado en `postman/reports/latest-newman-run/summary.csv`

## Resumen Global

- Colecciones ejecutadas: 19
- Colecciones aprobadas: 19
- Colecciones fallidas: 0
- Assertions aprobadas: 390
- Assertions fallidas: 0

## Configuracion usada por prueba y resultado

| Coleccion | Scope | Configuracion usada | Exit Code | Assertions aprobadas |
|---|---|---|---:|---:|
| travelhub-inventory-contract.postman_collection.json | contract | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 7/7 |
| travelhub-notifications-contract.postman_collection.json | contract | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 6/6 |
| travelhub-notifications.postman_collection.json | functional | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 5/5 |
| travelhub-payments-contract.postman_collection.json | contract | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 15/15 |
| travelhub-payments.postman_collection.json | functional | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 27/27 |
| travelhub-payments-stripe-evidence.postman_collection.json | functional | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 8/8 |
| travelhub-privacy-contract.postman_collection.json | contract | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 14/14 |
| travelhub-properties-contract.postman_collection.json | contract | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 6/6 |
| seasonal-pricing-signed.postman_collection.json | functional | env:postman/environments/travelhub-properties-seasonal-pricing-local.postman_environment.json | 0 | 22/22 |
| travelhub-reservations-contract.postman_collection.json | contract | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 36/36 |
| travelhub-search-contract.postman_collection.json | contract | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 6/6 |
| travelhub-security-contract.postman_collection.json | contract | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 3/3 |
| travelhub-users-contract.postman_collection.json | contract | env:postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 2/2 |
| travelhub-payments-reservations-e2e.postman_collection.json | e2e | env:postman/environments/travelhub-payments-reservations-local.postman_environment.json | 0 | 17/17 |
| e2e-signature-integrity.postman_collection.json | e2e | env:postman/environments/travelhub-properties-seasonal-pricing-local.postman_environment.json | 0 | 29/29 |
| reservation_modification_cancellation_refunds.postman_collection.json | e2e | env:postman/environments/travelhub-payments-reservations-local.postman_environment.json | 0 | 32/32 |
| travelhub-reservation-payment-failure-checkstatus-e2e.postman_collection.json | e2e | env:postman/environments/travelhub-payments-reservations-local.postman_environment.json | 0 | 12/12 |
| reservations_checkstatus.postman_collection.json | e2e | vars:base_url=http://localhost:8002;INTERNAL_API_KEY=travelhub-internal-secret-key | 0 | 12/12 |
| search_p95.postman_collection.json | perf | vars:base_url=http://localhost:8006;iteration-count=130 | 0 | 131/131 |

## Colecciones con fallas

Ninguna.

## Evidencia de salida

- Consolidado: `postman/reports/latest-newman-run/summary.csv`
- Resultados JSON por coleccion: `postman/reports/latest-newman-run/results/`
- Snapshot de esta corrida: `postman/reports/newman-run-1779056051/summary.csv`

## Resultado

La suite Newman queda en verde en esta corrida. Se actualizaron los resultados y artefactos para reflejar el estado real del branch `develop` al momento de la ejecucion.
