# Postman

Archivos listos para probar el MVP de `payments` desde Postman y validar los criterios de aceptacion aplicables al backend.

## Estructura de archivos

- `collections/payments/travelhub-payments.postman_collection.json`
- `collections/payments/travelhub-payments-stripe-evidence.postman_collection.json`
- `collections/payments/travelhub-payments-contract.postman_collection.json`
- `collections/notifications/travelhub-notifications.postman_collection.json`
- `collections/notifications/travelhub-notifications-contract.postman_collection.json`
- `collections/users/travelhub-users-contract.postman_collection.json`
- `collections/security/travelhub-security-contract.postman_collection.json`
- `collections/reservations/travelhub-reservations-contract.postman_collection.json`
- `collections/properties/travelhub-properties-contract.postman_collection.json`
- `collections/search/travelhub-search-contract.postman_collection.json`
- `e2e/payments-reservations/travelhub-payments-reservations-e2e.postman_collection.json`
- `e2e/reservation-modification-cancellation-refunds/reservation_modification_cancellation_refunds.postman_collection.json`
- `e2e/reservation-payment-failure-checkstatus/travelhub-reservation-payment-failure-checkstatus-e2e.postman_collection.json`
- `e2e/reservations-checkstatus/reservations_checkstatus.postman_collection.json`
- `e2e/search-p95/search_p95.postman_collection.json`
- `environments/travelhub-local.postman_environment.json`
- `environments/travelhub-payments-reservations-local.postman_environment.json`
- `environments/travelhub-notifications-local.postman_environment.json`
- `environments/travelhub-microservices-local.postman_environment.json`
- `reports/payments-reservations/newman-results.json`
- `reports/reservation-payment-failure-checkstatus/newman-failure-checkstatus-results.json`
- `reports/debug/newman-failed-flow-results.json`

## Preparacion

1. Importa la coleccion y el environment.
2. Selecciona el environment `TravelHub Local`.
3. Levanta el backend en `http://localhost:8003`.

## Coleccion principal MVP

`collections/payments/travelhub-payments.postman_collection.json`

Orden sugerido de ejecucion:

1. `00 - Health / Health - Payments`
2. `01 - Pago Exitoso / Create Charge - Success`
3. `01 - Pago Exitoso / Get Payment By Id`
4. `01 - Pago Exitoso / List Payment Events - Success`
5. `02 - Pago Fallido / Create Charge - Failure`
6. `02 - Pago Fallido / List Payment Events - Failure`
7. `03 - Duplicados / Create Charge - Duplicate Seed`
8. `03 - Duplicados / Create Charge - Idempotency Replay`
9. `03 - Duplicados / Create Charge - Duplicate Window`
10. `04 - Seguridad Transporte / Create Charge - Missing TLS Header`

Esta coleccion valida:

- El backend recibe solo `payment_method_token` y no expone datos sensibles en respuesta.
- Un cargo exitoso retorna `status=confirmed` y genera recibo.
- Un cargo fallido retorna `status=failed` y un `failure_reason` claro.
- Un intento duplicado en ventana corta es rechazado con `409`.
- La reutilizacion de una `idempotency_key` tambien es rechazada con `409` y mensaje especifico.
- Un request sin el header de transporte seguro es rechazado.
- Los eventos de pago dejan trazabilidad para confirmacion y recibo.

## Colecciones Contract por Microservicio

Environment sugerido para estas colecciones:

`environments/travelhub-microservices-local.postman_environment.json`

Colecciones:

- `collections/users/travelhub-users-contract.postman_collection.json`
- `collections/security/travelhub-security-contract.postman_collection.json`
- `collections/reservations/travelhub-reservations-contract.postman_collection.json`
- `collections/payments/travelhub-payments-contract.postman_collection.json`
- `collections/notifications/travelhub-notifications-contract.postman_collection.json`
- `collections/properties/travelhub-properties-contract.postman_collection.json`
- `collections/search/travelhub-search-contract.postman_collection.json`

Ejecucion sugerida en lote:

```bash
for c in $(find postman/collections -type f -name '*.postman_collection.json' | sort); do
  newman run "$c" -e postman/environments/travelhub-microservices-local.postman_environment.json --reporters cli
done
```

## Coleccion Stripe ejecutable

`collections/payments/travelhub-payments-stripe-evidence.postman_collection.json`

Esta coleccion solo contiene lo que si se puede ejecutar de forma repetible desde Postman o Newman en `stripe_test`:

1. `Get Payments Config`
2. `Create Intent`

Valida:

- Que `payments` esta corriendo en `stripe_test`.
- Que Stripe esta habilitado.
- Que el backend devuelve `publishable_key` de prueba.
- Que `create-intent` crea una sesion de checkout interna con `payment_transaction_id`.

## Coleccion E2E Payments + Reservations (Newman)

`e2e/payments-reservations/travelhub-payments-reservations-e2e.postman_collection.json`

Valida dos escenarios:

1. Happy path cross-service: reserva `pending_payment` -> pago `confirmed` -> reserva `confirmed`.
2. Error path: pago `confirmed` pero falla la actualizacion de reserva, con reproceso por endpoint interno de retry.

Ejecucion sugerida con Newman:

```bash
newman run postman/e2e/payments-reservations/travelhub-payments-reservations-e2e.postman_collection.json \
  -e postman/environments/travelhub-payments-reservations-local.postman_environment.json \
  --reporters cli,json \
  --reporter-json-export postman/reports/payments-reservations/newman-results.json
```

## Coleccion E2E Reserva + Pago fallido + CheckStatus (Newman)

`e2e/reservation-payment-failure-checkstatus/travelhub-reservation-payment-failure-checkstatus-e2e.postman_collection.json`

Valida el flujo:

1. Crear reserva (`pending_payment`).
2. Pago fallido (`failed`).
3. Ejecutar `checkstatus`.
4. Verificar que la reserva queda `cancelled`.

Ejecucion sugerida con Newman:

```bash
newman run postman/e2e/reservation-payment-failure-checkstatus/travelhub-reservation-payment-failure-checkstatus-e2e.postman_collection.json \
  -e postman/environments/travelhub-payments-reservations-local.postman_environment.json \
  --reporters cli,json \
  --reporter-json-export postman/reports/reservation-payment-failure-checkstatus/newman-failure-checkstatus-results.json
```

## Coleccion E2E HU Modificacion + Cancelacion + Refunds (Newman)

`e2e/reservation-modification-cancellation-refunds/reservation_modification_cancellation_refunds.postman_collection.json`

Valida los flujos completos de la HU:

1. Cancelacion de reserva con pago confirmado y transicion final a `refund_completed`.
2. Modificacion con delta negativo, refund iniciado y transicion final a `modification_confirmed`.

Ejecucion sugerida con Newman:

```bash
newman run postman/e2e/reservation-modification-cancellation-refunds/reservation_modification_cancellation_refunds.postman_collection.json \
  -e postman/environments/travelhub-payments-reservations-local.postman_environment.json \
  --reporters cli
```

## Coleccion E2E Reservations CheckStatus (Newman)

`e2e/reservations-checkstatus/reservations_checkstatus.postman_collection.json`

Ejecucion sugerida con Newman:

```bash
newman run postman/e2e/reservations-checkstatus/reservations_checkstatus.postman_collection.json \
  --env-var base_url=http://localhost:8002 \
  --env-var INTERNAL_API_KEY=${INTERNAL_API_KEY:-dev-internal-key-change-me} \
  --reporters cli
```

## Coleccion E2E Search P95 (Newman)

`e2e/search-p95/search_p95.postman_collection.json`

Ejecucion sugerida con Newman:

```bash
newman run postman/e2e/search-p95/search_p95.postman_collection.json \
  --env-var base_url=http://localhost:8006 \
  --iteration-count 130 \
  --reporters cli
```

Prerequisitos:

- Reservations activo en `http://localhost:8002`.
- Payments activo en `http://localhost:8003`.
- `INTERNAL_API_KEY` alineada entre servicios y environment de Postman.

## Flujo Stripe que queda fuera de Postman/Newman

No se incluye `POST /api/v1/payments/finalize` ni las consultas finales del pago en la coleccion Stripe, porque ese flujo requiere un `confirmation_token_id` de un solo uso generado por Stripe Elements en el navegador.

La evidencia de esa parte debe tomarse desde el frontend:

1. Abrir `/checkout`.
2. Completar el pago con Stripe Elements.
3. Capturar en DevTools el `POST /api/v1/payments/finalize`.
4. Validar `GET /api/v1/payments/{payment_id}` y `GET /api/v1/payments/{payment_id}/events` con el `payment_id` devuelto por el frontend.

## Fuera de alcance de Postman en este repo

- Stripe Elements en navegador.
- Tokenizacion real contra Stripe fuera del navegador.
- Confirmacion real de reserva en otro microservicio.
- Enforcement real de TLS 1.2+ por infraestructura.

## Notas

- La coleccion MVP genera `idempotency_key` dinamicos para evitar choques entre corridas.
- El token `pm_fail_insufficient_funds` simula rechazo por fondos insuficientes en el gateway MVP.

## Coleccion notifications

`collections/notifications/travelhub-notifications.postman_collection.json`

Orden sugerido:

1. `00 - Health / Health - Notifications`
2. `01 - Preparacion / Create Traveler`
3. `02 - Pago Base / Create Charge - Success`
4. `03 - Confirmacion de Pago / Create Payment Confirmation`
5. `03 - Confirmacion de Pago / Get Notification By Id`

Valida:

- Que el microservicio `notifications` esta arriba.
- Que la confirmacion de pago se resuelve desde `payments` y `users`.
- Que la confirmacion de pago se registra con `notification_id`.
- Que el estado inicial del recurso queda en `pending` y luego se materializa como `sent`.
- Que la notificacion puede consultarse posteriormente por id.

Nota:

- Esta coleccion es autoejecutable cuando `payments` esta corriendo con `PAYMENT_PROVIDER=fake_stripe`, porque genera un pago confirmado via `POST /payments/charges`.
- Si `payments` esta en `stripe_test`, la coleccion de `notifications` requiere usar un `payment_id` confirmado previamente desde el frontend o desde una evidencia real de Stripe.
