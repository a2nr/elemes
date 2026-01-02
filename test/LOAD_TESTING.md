# Load Testing Documentation for C Programming Learning Management System

## Overview
This document describes how to perform load testing on the C Programming Learning Management System to ensure it can handle at least 50 concurrent students accessing the application.

## Requirements
- Python 3.7+
- Locust (installed via pip)
- The LMS application running on your local machine or a test server

## Setup

### 1. Install Locust
```bash
pip install locust
```

Alternatively, install from the requirements file in the test directory:
```bash
cd /path/to/lms-c/test
pip install -r requirements.txt
```

### 2. Ensure the LMS Application is Running
Start your LMS application:
```bash
cd /path/to/lms-c
./start.sh
```
Or if running directly:
```bash
python app.py
```

By default, the application runs on `http://localhost:5000`.

## Running the Load Test

### Basic Load Test
To run a load test simulating 50 users with a hatch rate of 2 users per second:
```bash
cd /path/to/lms-c/test
locust -f load_test.py --host=http://localhost:5000
```

Then open your browser and go to `http://localhost:8089` to configure the load test.

### Command Line Load Test
To run the load test directly from the command line without the web interface:
```bash
locust -f load_test.py --host=http://localhost:5000 --users=50 --spawn-rate=2 --run-time=5m --headless
```

This command will:
- Simulate 50 users (`--users=50`)
- Spawn 2 users per second (`--spawn-rate=2`)
- Run for 5 minutes (`--run-time=5m`)
- Run in headless mode without the web interface (`--headless`)

## Test Scenarios

The load test script simulates the following student behaviors:

1. **Viewing the homepage** (30% of requests) - Students browsing available lessons
2. **Viewing lesson pages** (40% of requests) - Students reading lesson content
3. **Compiling code** (20% of requests) - Students submitting C code for compilation
4. **Logging in** (10% of requests) - Students authenticating with tokens
5. **Validating tokens** (10% of requests) - Students validating their access tokens
6. **Tracking progress** (10% of requests) - Students saving their lesson progress

## Monitoring and Metrics

During the load test, Locust provides the following metrics:

- **Users**: Number of concurrent users
- **Failures**: Number of failed requests
- **Requests per second**: Average request rate
- **Average response time**: Mean response time across all requests
- **95th percentile response time**: Response time below which 95% of requests complete
- **99th percentile response time**: Response time below which 99% of requests complete
- **Total requests**: Total number of requests made during the test

## Performance Benchmarks

For the application to be considered capable of handling 50 students simultaneously, it should meet these benchmarks:

- Less than 1% failure rate
- Average response time under 2 seconds
- 95th percentile response time under 5 seconds
- No significant degradation in performance as user count increases

## Customizing the Load Test

You can modify the `load_test.py` file to adjust:

- The number of users simulated
- The distribution of different types of requests
- The wait time between requests
- The sample code used for compilation tests
- The tokens used for authentication

## Troubleshooting

### Common Issues:

1. **Connection Refused**: Ensure the LMS application is running on the specified host/port
2. **High Failure Rate**: Check application logs for errors during the load test
3. **Memory Issues**: Monitor system resources during the test
4. **GCC Compilation Errors**: The application compiles C code, which may consume resources

### Resource Monitoring:
Consider monitoring system resources (CPU, memory, disk I/O) during the test using tools like `htop`, `iostat`, or `vmstat`.

## Conclusion

This load testing setup allows you to verify that the C Programming Learning Management System can handle at least 50 concurrent students. Regular load testing should be performed, especially after major updates, to ensure the application continues to meet performance requirements.