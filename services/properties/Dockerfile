FROM public.ecr.aws/docker/library/python:3.11-slim AS base

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["uvicorn", "entrypoints.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
