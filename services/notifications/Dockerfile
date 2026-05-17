FROM public.ecr.aws/docker/library/python:3.11-slim AS base
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ src/

FROM public.ecr.aws/docker/library/python:3.11-slim AS runner
WORKDIR /app
COPY --from=base /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=base /usr/local/bin /usr/local/bin
COPY --from=base /app/src/ /app/src/
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV NEW_RELIC_LOG=stdout
ENV NEW_RELIC_LOG_LEVEL=info
ENV NEW_RELIC_DISTRIBUTED_TRACING_ENABLED=true
ENV NEW_RELIC_SPAN_EVENTS_ENABLED=true
ENV NEW_RELIC_TRANSACTION_TRACER_RECORD_SQL=obfuscated
ENV NEW_RELIC_ATTRIBUTES_ENABLED=false
ENV NEW_RELIC_RUNTIME_METRICS_ENABLED=true

EXPOSE 8000
ENTRYPOINT ["newrelic-admin", "run-program", "/app/entrypoint.sh"]
