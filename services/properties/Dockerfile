FROM public.ecr.aws/docker/library/python:3.11-slim AS base

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

ENV PYTHONPATH=/app/src
ENV NEW_RELIC_CONFIG_FILE=/app/newrelic.ini
ENV NEW_RELIC_LOG=stdout
ENV NEW_RELIC_LOG_LEVEL=warning

EXPOSE 8000

CMD ["newrelic-admin", "run-program", "uvicorn", "entrypoints.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
