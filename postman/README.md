# Postman

Archivos listos para probar el MVP de `payments` desde Postman y validar los criterios de aceptacion aplicables al backend.

## Archivos

- `travelhub-payments.postman_collection.json`
- `travelhub-payments-stripe-evidence.postman_collection.json`
- `travelhub-local.postman_environment.json`

## Preparacion

1. Importa la coleccion y el environment.
2. Selecciona el environment `TravelHub Local`.
3. Levanta el backend en `http://localhost:8003`.

## Coleccion principal MVP

`travelhub-payments.postman_collection.json`

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

## Coleccion Stripe ejecutable

`travelhub-payments-stripe-evidence.postman_collection.json`

Esta coleccion solo contiene lo que si se puede ejecutar de forma repetible desde Postman o Newman en `stripe_test`:

1. `Get Payments Config`
2. `Create Intent`

Valida:

- Que `payments` esta corriendo en `stripe_test`.
- Que Stripe esta habilitado.
- Que el backend devuelve `publishable_key` de prueba.
- Que `create-intent` crea una sesion de checkout interna con `payment_transaction_id`.

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
