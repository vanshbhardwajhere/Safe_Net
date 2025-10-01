#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
export DJANGO_SETTINGS_MODULE=safenet.settings

python -m pip install --upgrade pip
pip install -r requirements.txt

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec gunicorn safenet.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --timeout 120


