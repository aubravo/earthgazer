#!/bin/bash
# Start CPU-specialized Celery worker
#
# This worker is optimized for CPU-bound tasks (image processing, NDVI computation)
# with lower concurrency to avoid resource contention.

set -e

echo "Starting CPU-specialized Celery worker..."

# Start worker with lower concurrency for CPU tasks
celery -A earthgazer.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --max-tasks-per-child=20 \
    --time-limit=3600 \
    --soft-time-limit=3300 \
    -Q cpu_queue \
    --hostname=cpu-worker@%h
