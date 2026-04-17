#!/bin/bash

# Pastikan berada di dalam folder load-test
cd "$(dirname "$0")"

echo "Menutup proses locust yang mungkin sedang berjalan..."
pkill -f "locust -f" 2>/dev/null
sleep 1

echo "Memulai Locust Master pada http://localhost:8089 ..."
locust -f locustfile.py --master > master.log 2>&1 &

sleep 2

echo "Memulai 5 Locust Workers..."
for i in {1..5}; do
  locust -f locustfile.py --worker > worker_$i.log 2>&1 &
  echo "Worker $i berjalan..."
done

echo ""
echo "Selesai! 1 Master dan 5 Worker sudah berjalan di latar belakang."
echo "Silakan buka kembali http://localhost:8089 di Chrome Anda."
echo "Catatan: Untuk mematikan semuanya nanti, gunakan perintah: ./stop_locust.sh atau ketik 'pkill -f locust'."
