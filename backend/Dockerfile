FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng poppler-utils fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
# Keep tool caches writable when /app is a host-owned or read-only bind mount.
ENV RUFF_CACHE_DIR=/tmp/subtrack-ruff-cache \
    PYTEST_ADDOPTS="-o cache_dir=/tmp/subtrack-pytest-cache"
COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY . .
RUN useradd --create-home appuser && chown -R appuser:appuser /app
RUN mkdir -p /var/subtrack/outbox && chown -R appuser:appuser /var/subtrack
RUN mkdir -p /var/subtrack/extractor && chown appuser:appuser /var/subtrack/extractor
ENV OUTBOX_DIR=/var/subtrack/outbox
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

