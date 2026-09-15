# ParaSail API service - slim image.
# Installs only what the FastAPI service needs to boot and serve; the full
# modelling/retrieval stack (torch, transformers, ultralytics, open-clip)
# lives in requirements.txt for training and corpus-seeding environments.
FROM python:3.11-slim

WORKDIR /app

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY src/ ./src/
COPY config.yaml ./config.yaml

ENV PYTHONPATH=/app/src \
    PARASAIL_CONFIG=/app/config.yaml \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "parasail.api:app", "--host", "0.0.0.0", "--port", "8000"]
