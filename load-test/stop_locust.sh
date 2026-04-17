#!/bin/bash
echo "Mematikan server dan seluruh worker Locust..."
pkill -f "locust"
echo "Locust berhasil dihentikan."
