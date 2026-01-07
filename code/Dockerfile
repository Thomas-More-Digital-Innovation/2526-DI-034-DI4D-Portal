FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python deps
COPY pyproject.toml README.md ./
RUN python -m pip install --upgrade pip && \
    pip install ".[dev]"

# Copy app code
COPY DI4D_Portal ./DI4D_Portal

EXPOSE 8000

CMD ["python", "DI4D_Portal/manage.py", "runserver", "0.0.0.0:8000"]
