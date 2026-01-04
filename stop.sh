#!/bin/bash

# Script to stop the C Programming Learning Management System

echo "Stopping C Programming Learning Management System..."

# Stop and remove the container
podman-compose down

echo "Application has been stopped."
