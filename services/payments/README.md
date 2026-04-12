# Payments Service

Microservicio de pagos de TravelHub para el MVP de procesamiento seguro.

## Responsabilidades

- Recibir solo tokens de pago generados fuera del backend
- Ejecutar el cargo a traves de un gateway desacoplado
- Evitar cobros duplicados accidentales
- Registrar eventos del pago y generar recibo en exitos
- Rechazar requests de pago sin transporte seguro cuando TLS es exigido

## Alcance MVP de HU016

- El backend no recibe numero de tarjeta, CVV ni fecha de expiracion
- El contrato HTTP acepta unicamente `payment_method_token`
- Requests que intenten enviar campos de tarjeta fuera del contrato se rechazan
- Se persiste solo el hash del token, nunca el token en claro
- Las referencias sensibles de checkout (`confirmation_token_id`, `client_secret`) se cifran en reposo con AES-256-GCM a nivel de aplicacion
- Se genera recibo cuando el pago queda `confirmed`
- Se devuelve `failure_reason` cuando el cargo falla
- Se rechazan duplicados por `idempotency_key` y por ventana corta de 2 segundos
- El servicio puede operar en `fake_stripe` o en `stripe_test` con `ConfirmationToken`
- `fake_stripe` queda restringido a desarrollo; en compliance mode solo se permite `stripe_test`
- Se persiste `provider_code` para trazabilidad del proveedor que proceso la transaccion
- Se registra auditoria tecnica del flujo de checkout, confirmacion y webhook con payloads saneados

## Modelo de datos MVP

- `payment`: transaccion materializada del pago con estado, referencia externa, proveedor y recibo
- `payment_checkout_session`: sesion interna del checkout Stripe hasta su materializacion en pago
- `payment_event`: eventos de negocio asociados al pago
- `payment_audit_log`: bitacora tecnica de acciones relevantes del flujo de pagos

## Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/payments/config` | Exponer configuracion publica de pagos |
| POST | `/api/v1/payments/create-intent` | Crear sesion de checkout para Stripe test |
| POST | `/api/v1/payments/finalize` | Crear y confirmar PaymentIntent con ConfirmationToken |
| GET | `/api/v1/payments/checkout/{payment_transaction_id}` | Consultar estado del checkout Stripe |
| GET | `/api/v1/payments/{payment_id}/confirmation` | Obtener resumen de confirmacion para pantalla de exito |
| POST | `/api/v1/payments/webhook` | Consumir webhooks firmados de Stripe |
| POST | `/api/v1/payments/charges` | Crear cargo con token de pago |
| GET | `/api/v1/payments/{payment_id}` | Consultar un pago |
| GET | `/api/v1/payments/{payment_id}/events` | Listar eventos del pago |

## Ejecucion

### Con Docker

```bash
make docker-up
# El servicio queda en http://localhost:8003
```

### Local

```bash
cd services/payments
pip install -r requirements.txt
PYTHONPATH=src uvicorn entrypoints.api.main:app --reload --port 8003
```

### Tests

```bash
# Desde la raiz del monorepo
make payments-test
# o, desde services/payments
PYTHONPATH=services/payments/src pytest services/payments/tests/ -v

# postura de seguridad
# Desde la raiz del monorepo
make payments-security-scan
# o, desde services/payments
PYTHONPATH=src pytest tests/test_payments_security_posture.py -v
```

## Configuracion

| Variable | Default | Descripcion |
|----------|---------|-------------|
| `RDS_HOSTNAME` | `localhost` | Host de PostgreSQL |
| `RDS_PORT` | `5432` | Puerto de PostgreSQL |
| `RDS_USERNAME` | `travelhub_user` | Usuario de BD |
| `RDS_PASSWORD` | `travelhub_pass` | Contrasena de BD |
| `RDS_DB_NAME` | `travelhub` | Nombre de la BD |
| `DB_SCHEMA` | `payments_schema` | Schema de PostgreSQL |
| `PAYMENT_PROVIDER` | `fake_stripe` | Gateway del MVP |
| `PAYMENTS_COMPLIANCE_MODE` | `False` | Endurece el servicio para flujo token-only con Stripe |
| `PAYMENT_DUPLICATE_WINDOW_SECONDS` | `2` | Ventana anti-duplicados |
| `PAYMENT_INTEGRITY_SECRET` | - | Secreto HMAC para checksum |
| `PAYMENTS_DATA_ENCRYPTION_KEY` | - | Clave para cifrar referencias sensibles en reposo |
| `ENFORCE_TLS_HEADER` | `True` | Exige `X-Forwarded-Proto: https` |
| `STRIPE_SECRET_KEY` | - | Secret key de Stripe en modo test |
| `STRIPE_PUBLISHABLE_KEY` | - | Publishable key de Stripe en modo test |
| `STRIPE_WEBHOOK_SECRET` | - | Secreto para verificar firma del webhook |
| `ALLOWED_CORS_ORIGIN` | `http://localhost:3000,http://127.0.0.1:3000` | Origenes permitidos para el frontend |

## Notas de arquitectura

- Este repo backend deja listo el contrato token-only para integrarse luego con Stripe Elements desde el frontend.
- En el MVP actual el gateway por defecto es simulado para permitir pruebas automatizadas sin depender de servicios externos.
- Para HU-ARQ-05, el modo defendible es `PAYMENTS_COMPLIANCE_MODE=true` con `PAYMENT_PROVIDER=stripe_test`.
- En ese modo, el backend queda restringido al flujo token-only y exige configuracion valida de Stripe, cifrado de referencias sensibles y URL HTTPS para notificaciones internas.
- La suite incluye pruebas de postura de seguridad para verificar ausencia de PAN hardcodeado en backend y redaccion de payloads sensibles.
- Si `PAYMENT_PROVIDER=stripe_test` y las llaves estan configuradas, el servicio expone el flujo `create-intent` + `finalize` + `webhook` para Stripe test mode.
- Los eventos `reservation.confirmation.requested`, `notification.payment_confirmation.requested` e `inventory.update.requested` dejan trazabilidad para la futura integracion asincrona.
- El modelo persiste relaciones referenciales minimas entre `payment`, `payment_checkout_session`, `payment_event` y `payment_audit_log`.
