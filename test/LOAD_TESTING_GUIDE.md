# Load Testing Guide for C Programming Learning Management System

This guide explains how to run load tests on the LMS-C application using Locust with different scenarios and configurations.

## Prerequisites

Before running load tests, ensure you have:
- Podman installed on your system
- The LMS-C application is properly configured with content and tokens
- The `tokens_siswa.csv` file contains student tokens (the load testing script will use these for realistic user simulation)

## Running Load Tests

### 1. Basic Load Test

To run a basic load test with the default configuration:

```bash
# Navigate to the test directory
cd /path/to/lms-c/elemes/test

# Run the load test with default settings (10 simulated users)
podman-compose -f podman-compose.yml up --build
```

Then access the Locust web interface at `http://localhost:8089` and configure your test parameters.

### 2. Distributed Load Test

For larger-scale testing, you can run a distributed test with multiple workers:

```bash
# Start the master node
podman-compose -f podman-compose.yml up --scale worker=3 master

# Or run with specific environment variables
TARGET_URL=http://your-lms-url.com LOCUST_NUM_STUDENTS=100 podman-compose -f podman-compose.yml up --scale worker=3 master
```

This will start 1 master and 3 worker nodes to distribute the load.

### 3. Environment Variables

The load testing configuration can be customized using these environment variables:

- `TARGET_URL`: The URL of the LMS-C application to test (default: `http://example.com`)
- `LOCUST_NUM_STUDENTS`: Number of simulated students/users (default: 10, but will automatically detect from tokens_siswa.csv)

Example:
```bash
TARGET_URL=http://192.168.1.100:5000 LOCUST_NUM_STUDENTS=50 podman-compose -f podman-compose.yml up --build
```

### 4. Customizing Test Scenarios

The `locustfile.py` implements several user behavior patterns:

#### WebsiteUser Class
- Simulates basic website visitors
- Performs tasks like viewing homepage, lessons, and compiling code
- Weight: 1 (less frequent)

#### AdvancedUser Class  
- Simulates engaged students who actively participate
- Performs more complex behaviors like lesson navigation and intensive code compilation
- Weight: 2 (twice as likely to be chosen as WebsiteUser)

#### Task Distribution
- `view_homepage`: Weight 3 (most common action)
- `compile_code`: Weight 4 (very common action)
- `view_lesson`: Weight 2 (common action)
- `login_student`: Weight 1 (less frequent but important)
- `validate_token`: Weight 1 (essential for tracking)
- `track_progress`: Weight 1 (important for completion tracking)

### 5. Realistic Student Simulation

The load testing script reads from `tokens_siswa.csv` to simulate real students:
- Each simulated user gets assigned a real student token from the CSV
- This ensures realistic progress tracking behavior
- The number of simulated users should match or be proportional to the number of tokens in the CSV

### 6. Monitoring and Analysis

Access the Locust web interface at `http://localhost:8089` to:
- Configure the number of users and spawn rate
- Monitor real-time statistics
- View response times, failure rates, and throughput
- Download test reports

### 7. Running Without the Web Interface

You can also run Locust in headless mode:

```bash
# Run with specific parameters without web UI
podman run -v $(pwd)/..:/mnt/locust \
  -e LOCUST_HOST=http://your-target-url.com \
  -e LOCUST_USERS=100 \
  -e LOCUST_SPAWN_RATE=10 \
  -e LOCUST_RUN_TIME=10m \
  locustio/locust -f /mnt/locust/elemes/test/locustfile.py --headless
```

### 8. Scaling Recommendations

- For 1-50 concurrent users: Single master node is sufficient
- For 50-200 concurrent users: Use 1 master + 2-3 worker nodes
- For 200+ concurrent users: Scale workers proportionally (1 master + 5+ workers)

### 9. Best Practices

- Always test against a staging environment that mirrors production
- Gradually increase the number of users to identify performance bottlenecks
- Monitor server resources (CPU, memory, disk I/O) during tests
- Run tests multiple times to account for variations
- Clean up resources after testing to avoid unnecessary resource consumption

### 10. Troubleshooting

If you encounter issues:
- Ensure the target LMS-C application is accessible from the Locust containers
- Check that the `tokens_siswa.csv` file is properly mounted and readable
- Verify that the content directory has lesson files for realistic testing
- Monitor container logs with `podman logs -f <container-name>`