#!/bin/sh
set -eu

case "${DJANGO_SECRET_KEY:-}" in
  ""|change-me|dev-only-homebudget-key|collectstatic)
    echo "Set DJANGO_SECRET_KEY to a long random value." >&2
    exit 1
    ;;
esac

db_dir=$(dirname "${DJANGO_DB_PATH:-/data/db.sqlite3}")
mkdir -p "$db_dir"
chown -R app:app "$db_dir"

runuser -u app -- python manage.py migrate --noinput
exec runuser -u app -- gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-1}" \
  --threads "${WEB_THREADS:-4}" \
  --access-logfile - \
  --error-logfile -
