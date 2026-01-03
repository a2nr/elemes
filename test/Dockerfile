FROM python:3.11-slim

# Install gcc compiler for C code compilation (needed for communication with LMS)
RUN apt-get update && \
    apt-get install -y gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /locust

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy locustfile
COPY locustfile.py .

# Expose port for Locust web interface
EXPOSE 8089

# Command to run Locust
CMD ["locust", "-f", "locustfile.py"]