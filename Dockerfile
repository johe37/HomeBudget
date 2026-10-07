FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=0 \
    DJANGO_ALLOWED_HOSTS=* \
    DJANGO_DB_PATH=/data/db.sqlite3 \
    PORT=8000

WORKDIR /app

RUN useradd --create-home --uid 1000 --shell /bin/sh app \
    && mkdir -p /data \
    && chown app:app /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/docker/entrypoint.sh \
    && DJANGO_SECRET_KEY=collectstatic python manage.py collectstatic --noinput \
    && chown -R app:app /app

VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/accounts/login/' % os.environ.get('PORT', '8000'), timeout=4)"]

ENTRYPOINT ["/app/docker/entrypoint.sh"]
