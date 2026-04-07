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

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

EXPOSE 8002

CMD ["uvicorn", "entrypoints.api.main:app", "--host", "0.0.0.0", "--port", "8002"]
