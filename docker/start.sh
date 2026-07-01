#!/bin/bash
set -e

echo "========================================="
echo "  Img2Video Application Server Starting"
echo "========================================="

# Create necessary directories
mkdir -p /var/log/supervisor
mkdir -p /var/run

# Wait for dependent services using Python (reliable across slim images)
if [ -n "$WAIT_FOR" ]; then
    echo "[WAIT] Checking dependent services..."
    for service in $WAIT_FOR; do
        host=$(echo $service | cut -d: -f1)
        port=$(echo $service | cut -d: -f2)
        echo "[WAIT] Waiting for $host:$port..."
        python -c "
import socket, time
while True:
    try:
        s = socket.create_connection(('$host', $port), timeout=2)
        s.close()
        break
    except (OSError, socket.error):
        time.sleep(1)
print('Ready: $host:$port')
"
        echo "[WAIT] $host:$port is available"
    done
    echo "[WAIT] All dependent services are ready."
fi

# Initialize database tables
python -c "
import asyncio
from app.database import init_db
asyncio.run(init_db())
print('[DB] Database tables initialized successfully.')
"

# Initialize MinIO bucket
python -c "
from app.config import settings
from minio import Minio
client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE
)
bucket = settings.MINIO_BUCKET
if not client.bucket_exists(bucket):
    client.make_bucket(bucket)
    print(f'[MinIO] Bucket \"{bucket}\" created.')
else:
    print(f'[MinIO] Bucket \"{bucket}\" already exists.')
"

echo "========================================="
echo "  Starting all services via Supervisor"
echo "========================================="

# Start supervisor
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
