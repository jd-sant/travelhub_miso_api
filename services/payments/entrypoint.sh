#!/bin/sh
set -eu

MODE="${SERVICE_MODE:-api}"

case "$MODE" in
  api)
    exec uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 8000
    ;;
  worker)
    exec python -m entrypoints.worker.payments_consumer
    ;;
  *)
    echo "SERVICE_MODE invalido: $MODE (use 'api' o 'worker')" >&2
    exit 1
    ;;
esac
