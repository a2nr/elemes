FROM python:3.11-slim

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash app

# Install gcc compiler for C code compilation and other production dependencies
RUN apt-get update && \
    apt-get install -y gcc build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code only with non-root ownership
COPY --chown=app:app app.py config.py extensions.py gunicorn.conf.py alembic.ini pytest.ini ./
COPY --chown=app:app routes/ ./routes/
COPY --chown=app:app services/ ./services/
COPY --chown=app:app scripts/ ./scripts/
COPY --chown=app:app migrations/ ./migrations/
COPY --chown=app:app docs/ ./docs/
COPY --chown=app:app help/ ./help/
COPY --chown=app:app compiler/ ./compiler/

USER app

# Expose port 5000
EXPOSE 5000

# Run the application with Gunicorn in production mode using config file
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:create_app()"]
