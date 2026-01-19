FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy enough source for packaging metadata
COPY pyproject.toml README.md ./
COPY DI4D_Portal ./DI4D_Portal

# Install Python deps (dev for tailwind build, prod for runtime)
RUN python -m pip install --upgrade pip && \
    pip install ".[dev,prod]"

# Build Tailwind CSS
RUN cd DI4D_Portal && \
    DJANGO_SETTINGS_MODULE=DI4D_Portal.settings \
    SECRET_KEY_DJANGO=build-time-key \
    DJANGO_DEBUG=True \
    python manage.py tailwind build

# Collect static files (includes compiled Tailwind CSS)
RUN cd DI4D_Portal && \
    DJANGO_SETTINGS_MODULE=DI4D_Portal.settings \
    SECRET_KEY_DJANGO=build-time-key \
    python manage.py collectstatic --noinput --clear

EXPOSE 8000

# Use entrypoint script to run migrations then start gunicorn
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--chdir", "DI4D_Portal", "DI4D_Portal.wsgi:application"]
