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

Local cada servicio está expuesto en su propio puerto (`users:8000`, `security:8001`, `reservations:8002`, `payments:8003`, `notifications:8004`, `properties:8005`, `search:8006`) — no hay ALB que enrute por path. Para que el mix de Locust funcione contra un host único, levanta un mini-gateway nginx que reproduce el path-routing del ALB:

```bash
make docker-up

cat > /tmp/loadtest-nginx.conf <<'CONF'
events { worker_connections 4096; }
http {
  upstream users        { server host.docker.internal:8000; }
  upstream security     { server host.docker.internal:8001; }
  upstream reservations { server host.docker.internal:8002; }
  upstream payments     { server host.docker.internal:8003; }
  upstream notifications{ server host.docker.internal:8004; }
  upstream properties   { server host.docker.internal:8005; }
  upstream search       { server host.docker.internal:8006; }
  server {
    listen 80;
    location /api/v1/users         { proxy_pass http://users; }
    location /api/v1/auth          { proxy_pass http://security; }
    location /api/v1/reservations  { proxy_pass http://reservations; }
    location /api/v1/payments      { proxy_pass http://payments; }
    location /api/v1/notifications { proxy_pass http://notifications; }
    location /api/v1/properties    { proxy_pass http://properties; }
    location /api/v1/search        { proxy_pass http://search; }
  }
}
CONF

docker run -d --name loadtest-gw \
  --add-host=host.docker.internal:host-gateway \
  -p 127.0.0.1:8080:80 \
  -v /tmp/loadtest-nginx.conf:/etc/nginx/nginx.conf:ro \
  nginx:1.27-alpine

cd services/load-tests
export LOADTEST_PROPERTY_ID=<uuid-de-propiedad-seed>
export LOADTEST_JWT_SECRET=$(grep ^JWT_SECRET_KEY ../../.env | cut -d= -f2)
# Acorta el escenario para humo local (ver "Duración: --run-time vs LoadTestShape" abajo)
export LOADTEST_RAMP_SECONDS=20 LOADTEST_PEAK_SECONDS=40
export LOADTEST_PEAK_USERS=10 LOADTEST_START_USERS=2
mkdir -p ../../docs/load-tests/MPF-74/local-smoke
locust -f locustfile.py --host http://localhost:8080 --headless \
  --html ../../docs/load-tests/MPF-74/local-smoke/report.html \
  --csv ../../docs/load-tests/MPF-74/local-smoke/stats
```

Los artefactos del humo quedan en `docs/load-tests/MPF-74/local-smoke/` (ignorado por git vía `.gitignore`). El reporte HTML se abre con `xdg-open docs/load-tests/MPF-74/local-smoke/report.html`.

Al terminar: `docker rm -f loadtest-gw`.

### Duración: `--run-time` vs `LoadTestShape`

`locustfile.py` define una `LoadTestShape` (`RampThenPeak`). **Cuando hay shape, Locust ignora `--run-time`** — la duración se controla por las env vars `LOADTEST_RAMP_SECONDS` (default `300`) y `LOADTEST_PEAK_SECONDS` (default `900`). Si invocas con `--run-time 60s` sin overrides, la corrida durará los 20 min del escenario completo y tendrás que matarla con Ctrl-C.

### Limitación del OTP / envío de correo bajo carga

El servicio `security` envía el OTP por **Gmail SMTP** (`SmtpOtpSender` cuando `SMTP_HOST` está configurado, único modo soportado hoy tanto en local como en AWS dev). Gmail desconecta sesiones cuando varios `auth/login` autentican concurrentemente desde la misma cuenta/IP, lo que produce `500` esporádicos en `POST /api/v1/auth/login` bajo carga sostenida. **No es un bug del código** — es la cuota del provider SMTP.

Migrar este flujo a AWS SES no resuelve el problema de inmediato porque la cuenta SES está en **Sandbox**: solo admite enviar a destinatarios previamente verificados (los emails sintéticos `loadtest+<uuid>@…` del test no lo están) y tope de ~200 correos/día. Migrar requiere solicitar Production Access a AWS — pendiente como deuda técnica fuera del alcance de MPF-74.

**Cómo se sortea para validar MPF-74 sin tocar el provider de correo:**

El locustfile expone `LOADTEST_REAL_LOGIN_RATIO` (default `0.3`). Es la fracción de tasks `auth_login` que usan credenciales propias del VU (path 200 → envía OTP) vs un email aleatorio (path 401 → escribe `login_attempt` pero **no toca SMTP**). Poniéndolo en `0.0` el load test sigue ejercitando el path crítico de auth (verificación de credenciales, escritura concurrente sobre `login_attempt`, evaluación de IP-block distribuido) sin generar correos:

```bash
export LOADTEST_REAL_LOGIN_RATIO=0.0
locust -f locustfile.py --host http://<dns-del-alb> ...
```

La AC2 ("almacenamiento de sesiones distribuido") se valida por separado con el **procedimiento manual** documentado más abajo (sección "Validación manual de sesión distribuida"): un único usuario hace `login` → recibe OTP → `verify-otp` desde otro task → 200 con `access_token`. Eso demuestra que el OTP persistido por el task A se lee desde el task B porque vive en Postgres compartido, sin depender de la capacidad del provider de correo.

Para humo local sin SMTP ruido (alternativa): deja vacías `SMTP_HOST/SMTP_USER/SMTP_PASSWORD` en `.env` y `security` cae a `LogOtpSender` (loguea el OTP a stdout, responde 200). En AWS dev esa misma combinación se logra dejando vacíos los campos SMTP del `data` tfvars antes de un `terraform apply` puntual; no se recomienda para uso normal.

## Ejecución en AWS (corrida real)

```bash
cd services/load-tests
export LOADTEST_PROPERTY_ID=<uuid>
export LOADTEST_JWT_SECRET=<secreto-de-secrets-manager>
# SES está en sandbox y Gmail tiene cuota baja → desactivar logins reales
# para que el SMTP no se vuelva el cuello de botella. La AC2 se demuestra
# con el procedimiento manual al final de este README.
export LOADTEST_REAL_LOGIN_RATIO=0.0

locust -f locustfile.py --host http://<dns-del-alb> \
  --processes 4 \
  --users 60 --spawn-rate 0.2 \
  --headless --html ../../docs/load-tests/MPF-74/report.html \
  --csv ../../docs/load-tests/MPF-74/stats
```

`--processes 4` distribuye los VUs entre 4 procesos worker locales (evita el GIL de Python). `--run-time` se omite porque la `LoadTestShape` (5 min ramp + 15 min peak) controla la duración.

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

