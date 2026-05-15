# Pruebas de carga — MPF-74

Suite de Locust para validar **HU-ARQ-04: gestión de sesiones en alta demanda**.

## Alcance

- Objetivo: **600–3.600 usuarios/min** sostenidos durante **2 h**, tasa de éxito > 99,9 %.
- Estrategia: corrida de 20 minutos (5 min de rampa + 15 min al pico) con **extrapolación de estado estacionario a 2 h**. Ver `docs/load-tests/MPF-74/REPORT.md` para el argumento de extrapolación.

## Estrategia del flujo de autenticación

El OTP por correo no se puede pasar de forma automatizada (no hay acceso al inbox del usuario sintético). Solución estándar:

1. **Cada VU registra su propio usuario** vía `POST /api/v1/users` en el `on_start`.
2. **El VU pre-firma su propio JWT** localmente con el mismo `JWT_SECRET_KEY` que usa el servicio security (`HS256`).
3. El JWT pre-firmado es **válido y aceptado por cualquier task** del cluster
4. El flujo de `auth/login` se mantiene en el mix para ejercitar la escritura sobre `login_attempt` bajo carga (el path de IP-block distribuido).

## Prerrequisitos

1. **Stack AWS desplegado** desde `travelhub_terraform` rama `feat/mpf-74` (RDS t3.medium, `min_capacity=2`, política ALBRequestCountPerTarget habilitada).
2. `**PAYMENT_PROVIDER=fake_stripe`** ya es el valor en producción hoy, así que `POST /api/v1/payments/charges` usa el `FakeStripePaymentGateway` existente — no hace falta override.
3. **Snapshot de RDS** creado antes del test (los miles de usuarios sintéticos se borran al restaurar):
  ```bash
   aws rds create-db-snapshot \
     --db-instance-identifier <rds-id> \
     --db-snapshot-identifier mpf-74-pre-load
   aws rds wait db-snapshot-completed --db-snapshot-identifier mpf-74-pre-load
  ```
4. **Propiedad seed**: al menos una propiedad existente en la DB. Exportar su UUID como `LOADTEST_PROPERTY_ID`.
5. **Secreto JWT** leído desde AWS Secrets Manager:
  ```bash
   export LOADTEST_JWT_SECRET=$(aws secretsmanager get-secret-value \
     --secret-id <security-config-arn> --query SecretString --output text \
     | jq -r .JWT_SECRET_KEY)
  ```

## Instalación

```bash
cd services/load-tests
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Prueba de humo local (docker-compose)

```bash
make docker-up
cd services/load-tests
export LOADTEST_PROPERTY_ID=<uuid-de-propiedad-seed>
export LOADTEST_JWT_SECRET=$(grep ^JWT_SECRET_KEY ../../.env | cut -d= -f2)
locust -f locustfile.py --host http://localhost \
  --users 10 --spawn-rate 1 --run-time 1m --headless
```

Si la prueba de humo local falla, no continuar con AWS.

## Ejecución en AWS (corrida real)

```bash
cd services/load-tests
export LOADTEST_PROPERTY_ID=<uuid>
export LOADTEST_JWT_SECRET=<secreto-de-secrets-manager>

locust -f locustfile.py --host http://<dns-del-alb> \
  --processes 4 \
  --users 60 --spawn-rate 0.2 --run-time 20m \
  --headless --html ../../docs/load-tests/MPF-74/report.html \
  --csv ../../docs/load-tests/MPF-74/stats
```

`--processes 4` distribuye los VUs entre 4 procesos worker locales (evita el GIL de Python).

## Escenario


| Fase  | Duración | Carga                         |
| ----- | -------- | ----------------------------- |
| Rampa | 5 min    | 10 → 60 VUs (lineal)          |
| Pico  | 15 min   | 60 VUs (≈ 60 RPS / 3.600 RPM) |


Ciclo de vida del VU:

- `on_start` → `POST /api/v1/users` con email único + JWT pre-firmado guardado en `self.token`.

Mix por iteración (≈ 1 request cada 10 s por VU):

- **60 % búsqueda** — `GET /api/v1/search?city=…`.
- **15 % login** — `POST /api/v1/auth/login`; 30 % con credenciales propias (200 → escribe OTP), 70 % con email aleatorio (401 → escribe login_attempt).
- **5 % registro sostenido** — `POST /api/v1/users` adicionales durante el test (no solo en `on_start`).
- **20 % reserva/pago** — `POST /api/v1/payments/charges` con JWT pre-firmado en `Authorization`.

## Captura de evidencia durante la fase de pico

Mientras Locust corre, capturar screenshots de CloudWatch durante los últimos 5 minutos del pico:

- `AWS/ECS` → `CPUUtilization`, `MemoryUtilization`, `DesiredCount`, `RunningCount` por `ServiceName`.
- `AWS/RDS` → `DatabaseConnections`, `CPUUtilization`, `FreeableMemory`.
- `AWS/ApplicationELB` → `RequestCountPerTarget`, `HTTPCode_Target_2XX_Count`, `HTTPCode_Target_5XX_Count`, `TargetResponseTime`.

Guardar cada captura en `docs/load-tests/MPF-74/cloudwatch/<metric>.png`.

## Validación manual de sesión distribuida (AC2)

Fuera del pico, demostrar que dos tasks distintos comparten el estado de sesión:

1. Listar tasks del servicio security:
  ```bash
   aws ecs list-tasks --cluster travelhub-prod --service-name travelhub-prod-security
  ```
2. Pedir OTP vía el ALB (round-robin enruta al task A):
  ```bash
   curl -X POST "http://$ALB_DNS/api/v1/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"email":"loadtest@example.com","password":"Demo123!"}'
  ```
3. Verificar el OTP recibido — la request puede caer en el task B (distinto del A):
  ```bash
   curl -X POST "http://$ALB_DNS/api/v1/auth/verify-otp" \
     -H "Content-Type: application/json" \
     -d '{"email":"loadtest@example.com","otp_code":"123456"}'
  ```
4. Resultado esperado: 200 con `access_token`. Demuestra que el OTP escrito por task A es legible por task B porque vive en Postgres compartido, no en memoria.

## Restaurar estado después del test

```bash
# 1. Restaurar RDS desde snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-snapshot-identifier mpf-74-pre-load \
  --db-instance-identifier <rds-id>-restored

# 2. Revertir overrides Terraform (vuelven a defaults: RDS t3.micro, min_capacity=1)
cd ../travelhub_terraform/stacks/compute && rm -f mpf-74.tfvars && terraform apply
cd ../data && rm -f mpf-74.tfvars && terraform apply

# 3. Borrar el snapshot una vez verificado
aws rds delete-db-snapshot --db-snapshot-identifier mpf-74-pre-load

# 4. Limpiar el secreto del shell
unset LOADTEST_JWT_SECRET
```

## Troubleshooting


| Síntoma                           | Causa probable                      | Mitigación                                     |
| --------------------------------- | ----------------------------------- | ---------------------------------------------- |
| Locust no alcanza 60 RPS          | NIC laptop saturada                 | Mover generador a EC2 t3.small en us-east-1    |
| 5xx en bursts iniciales           | Cold start de tasks nuevos          | Confirmar `min_capacity=2` antes de empezar    |
| `DatabaseConnections` sube lineal | Sesiones SQLAlchemy no se devuelven | Revisar `get_session()` del servicio que crece |
| ALB 504                           | Timeout downstream                  | Subir `SERVICE_REQUEST_TIMEOUT` temporalmente  |
| Booking siempre 401               | JWT secret incorrecto o vacío       | Re-cargar desde Secrets Manager                |


## Salida del test

- `report.html` — reporte HTML interactivo.
- `stats_*.csv` — métricas crudas por endpoint e intervalo.

## Criterios de éxito (últimos 5 minutos de la Fase de pico)

1. Tasa de éxito > 99,9 % global (excluyendo 401/423/429 esperados del flujo auth).
2. p95 de latencia plana — no debe crecer entre minuto 15 y minuto 20.
3. ECS `DesiredCount` por servicio: plano (sin crecimiento).
4. RDS `DatabaseConnections`: plano.
5. ECS `MemoryUtilization`: plano.

Si los 5 se cumplen, el test concluye **"se extrapola a 2 h"**.

## Limitaciones conocidas

- Carga generada desde la laptop con `--processes 4`. La p95 reportada incluye latencia de la red doméstica; se recomienda cable ethernet y cerrar otras apps. Si la NIC limita el RPS, mover el generador a una EC2 `t3.small` en la misma región.
- El JWT pre-firmado salta intencionalmente el flujo de OTP. La AC2 a escala se demuestra por la aceptación cross-task del JWT (cualquier task valida con el mismo secreto). El flujo de OTP real (login → correo → verify-otp → JWT emitido) se valida con el procedimiento manual descrito arriba ("Validación manual de sesión distribuida") con un usuario individual.

