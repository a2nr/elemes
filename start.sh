#!/bin/bash

# Script to start the C Programming Learning Management System

echo "Starting C Programming Learning Management System..."

# Check if container is already running
if [ "$(podman ps -q -f name=elemes-container)" ]; then
  echo "Container is already running. Access the application at http://localhost:5000"
  exit 0
fi

# Check if container exists but is stopped
if [ "$(podman ps -aq -f name=elemes-container)" ]; then
  echo "Starting existing container..."
  podman start elemes-container
else
  # Build and run the container
  echo "Building and starting container..."
  podman-compose up --build -d
fi

echo "Application is now running. Access at http://localhost:5000"
echo "To stop the application, run: ./stop.sh"
