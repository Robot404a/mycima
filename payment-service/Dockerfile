# Build from the REPOSITORY ROOT (same pattern as the other services):
#   docker build -f payment-service/Dockerfile .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# shared/auth.py and shared/logging_config.py are imported by this service.
COPY shared /app/shared
COPY payment-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Runtime code, generated protobuf modules and the source .proto file.
COPY payment-service /app

EXPOSE 8000 50051

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

# REST_PORT is read by this shell expression; GRPC_PORT is read by app.config.
CMD ["sh", "-c", "uvicorn app.main:app --host ${REST_HOST:-0.0.0.0} --port ${REST_PORT:-8000}"]
