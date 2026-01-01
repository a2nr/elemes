#!/bin/bash

# Script to access the LMS-C container for development
# This script will start the container (if not running) and open a shell

echo "Starting LMS-C container and opening shell..."

# Check if container is already running
if [ "$(podman ps -q -f name=lms-c-container)" ]; then
    echo "Container is already running. Opening shell..."
    podman exec -it lms-c-container /bin/bash
else
    # Check if container exists but is stopped
    if [ "$(podman ps -aq -f name=lms-c-container)" ]; then
        echo "Starting existing container..."
        podman start lms-c-container
        sleep 2
        podman exec -it lms-c-container /bin/bash
    else
        echo "Building and starting container..."
        podman build -t lms-c . && podman run -d -p 5000:5000 --name lms-c-container lms-c
        sleep 5  # Wait for the application to start
        podman exec -it lms-c-container /bin/bash
    fi
fi