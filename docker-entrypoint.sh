#!/bin/sh
set -e

python manage.py migrate --noinput

python manage.py collectstatic --noinput --clear

PORT=${PORT:-8000}

exec gunicorn \
    --bind 0.0.0.0:$PORT \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    latexgenius.wsgi:application
