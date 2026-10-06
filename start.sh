#!/bin/sh
set -e

python ensure_db.py
python manage.py migrate --noinput
python manage.py crear_admin

exec gunicorn gateway.wsgi:application --bind 0.0.0.0:${PORT:-8000} \
    --worker-class gthread --threads 8 --timeout 120
