#!/bin/bash

# Script to start the C Programming Learning Management System

echo "Starting C Programming Learning Management System..."

# Check if container is already running
if [ "$(podman ps -q -f name=lms-c-container)" ]; then
    echo "Container is already running. Access the application at http://localhost:5000"
    exit 0
fi

# Check if container exists but is stopped
if [ "$(podman ps -aq -f name=lms-c-container)" ]; then
    echo "Starting existing container..."
    podman start lms-c-container
else
    # Build and run the container
    echo "Building and starting container..."
    podman build -t lms-c . && podman run -d -p 5000:5000 --name lms-c-container lms-c
fi

echo "Application is now running. Access at http://localhost:5000"
echo "To stop the application, run: ./stop.sh"