FROM python:3.11-slim

# Install necessary packages
RUN apt-get update && \
    apt-get install -y gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY test/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port for Locust web interface
EXPOSE 8089

# Set the working directory to test
WORKDIR /app/test

# Run Locust
CMD ["locust", "-f", "load_test.py", "--host=http://lms-c:5000"]