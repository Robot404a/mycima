# Build from the REPO ROOT (same pattern as gateway/Dockerfile):
#   docker build -f reservation-service/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY reservation-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# When the team's shared/ folder exists, uncomment the next line. auth.py and
# logging_setup.py pick it up automatically (until then they use local fallbacks).
# COPY shared /app/shared

COPY reservation-service/*.py /app/

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
