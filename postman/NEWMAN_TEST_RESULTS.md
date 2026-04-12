# Newman Test Results - Postman Suite

## Ejecucion

- Fecha: 11 de abril de 2026
- Tipo de corrida: Newman, coleccion por coleccion
- Reporters usados en esta solicitud: CLI (sin reporte exportado como artefacto de salida)

## Resumen Global

- Colecciones ejecutadas: 14
- Colecciones aprobadas: 14
- Colecciones fallidas: 0
- Assertions aprobadas: 242
- Assertions fallidas: 0

## Configuracion usada por prueba y resultado

| Coleccion | Scope | Configuracion usada | Exit Code | Assertions aprobadas |
|---|---|---|---:|---:|
| travelhub-notifications-contract.postman_collection.json | contract | env: postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 3/3 |
| travelhub-notifications.postman_collection.json | contract | env: postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 5/5 |
| travelhub-payments-contract.postman_collection.json | contract | env: postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 6/6 |
| travelhub-payments.postman_collection.json | contract | env: postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 27/27 |
| travelhub-payments-stripe-evidence.postman_collection.json | contract | env: postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 8/8 |
| travelhub-properties-contract.postman_collection.json | contract | env: postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 4/4 |
| travelhub-reservations-contract.postman_collection.json | contract | env: postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 6/6 |
| travelhub-search-contract.postman_collection.json | contract | env: postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 6/6 |
| travelhub-security-contract.postman_collection.json | contract | env: postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 3/3 |
| travelhub-users-contract.postman_collection.json | contract | env: postman/environments/travelhub-microservices-local.postman_environment.json | 0 | 2/2 |
| travelhub-payments-reservations-e2e.postman_collection.json | e2e | env: postman/environments/travelhub-payments-reservations-local.postman_environment.json | 0 | 17/17 |
| travelhub-reservation-payment-failure-checkstatus-e2e.postman_collection.json | e2e | env: postman/environments/travelhub-payments-reservations-local.postman_environment.json | 0 | 12/12 |
| reservations_checkstatus.postman_collection.json | e2e | vars: base_url=http://localhost:8002, INTERNAL_API_KEY=travelhub-internal-secret-key | 0 | 12/12 |
| search_p95.postman_collection.json | perf | vars: base_url=http://localhost:8006, iteration-count=130 | 0 | 131/131 |

## Resultado

Todas las pruebas de Newman Postman solicitadas fueron aprobadas.
