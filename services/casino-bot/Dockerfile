FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STATUS_HOST=0.0.0.0 \
    STATUS_PORT=8011 \
    DB_PATH=/app/data/bebra.db

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.docker.txt /app/requirements.docker.txt
RUN pip install --no-cache-dir -r /app/requirements.docker.txt

COPY . /app
RUN mkdir -p /app/data \
    && ln -sfn /app/data/bebra.db /app/bebra.db

EXPOSE 8011
CMD ["python", "run.py"]
