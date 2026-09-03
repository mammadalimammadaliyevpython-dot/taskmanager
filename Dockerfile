# Production-style image: gunicorn serving the Django app as an unprivileged user.
# Build:  docker build -t taskmanager:local .
# Run:    docker run --rm -p 8000:8000 -v taskmanager-data:/data taskmanager:local
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TASKMANAGER_DATA_DIR=/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY taskmanager/ .

# Code stays owned by root (read-only for the service user); only /data is writable.
RUN useradd --create-home --uid 10001 taskmanager \
    && mkdir -p /data \
    && chown taskmanager:taskmanager /data

USER taskmanager
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/', timeout=2).status == 200 else 1)"

# Migrations run on start so a fresh volume works out of the box.
CMD ["sh", "-c", "if [ \"${TASKMANAGER_MIGRATE_ON_START:-true}\" = true ]; then python manage.py migrate --noinput; fi && exec gunicorn taskmanager.wsgi --bind 0.0.0.0:8000 --workers ${WEB_CONCURRENCY:-4} --timeout 60 --graceful-timeout 60 --access-logfile - --error-logfile -"]
