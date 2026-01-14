#!/bin/sh
set -e

echo "Running migrations..."
cd /app/DI4D_Portal
python manage.py migrate --noinput

echo "Starting application..."
exec "$@"
