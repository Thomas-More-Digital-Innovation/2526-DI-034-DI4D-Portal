FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy enough source for packaging metadata
COPY pyproject.toml README.md ./
COPY DI4D_Portal ./DI4D_Portal

# Install Python deps
RUN python -m pip install --upgrade pip && \
    pip install ".[dev]"

EXPOSE 8000

CMD ["python", "DI4D_Portal/manage.py", "runserver", "0.0.0.0:8000"]
