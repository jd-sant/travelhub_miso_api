# Notifications Service

Microservicio responsable de resolver la informacion de confirmacion del pago, persistir la notificacion, registrar auditoria y despachar el mensaje por email mediante un sender desacoplado.

## Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/internal/payment-confirmations` | Crear y despachar confirmacion de pago a partir de `payment_id` |
| GET | `/api/v1/notifications/{notification_id}` | Consultar estado de una notificacion |

## Modelo de datos MVP

- `notification`: mensaje de confirmacion asociado a pago y reserva
- `notification_delivery_attempt`: intentos de envio al proveedor de correo
- `notification_audit_log`: bitacora tecnica del flujo de confirmacion

## Notas

- El servicio resuelve el resumen del pago desde `payments` y el destinatario desde `users`.
- Los endpoints operativos requieren `X-Internal-Api-Key`.
- El servicio nace listo para desacoplarse hacia cola/eventos en una fase posterior.
- En desarrollo usa `LogEmailSender`; si hay configuracion SMTP, usa sender SMTP.
