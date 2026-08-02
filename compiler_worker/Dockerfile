FROM python:3.11-slim

# Install GCC and other build tools
RUN apt-get update && apt-get install -y \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir flask gunicorn

COPY app.py .
COPY session_manager.py .

EXPOSE 8080

# A1 config: single process + 32 threads (shared session registry)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--worker-class", "gthread", "--workers", "1", "--threads", "32", "--timeout", "30", "--graceful-timeout", "10", "app:app"]
