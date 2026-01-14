#!/bin/bash
# Start I/O-specialized Celery worker
#
# This worker is optimized for I/O-bound tasks (downloads, uploads, file operations)
# with higher concurrency.

set -e

echo "Starting I/O-specialized Celery worker..."

# Start worker with high concurrency for I/O tasks
celery -A earthgazer.celery_app worker \
    --loglevel=info \
    --concurrency=8 \
    --max-tasks-per-child=50 \
    --time-limit=7200 \
    --soft-time-limit=7000 \
    -Q io_queue \
    --hostname=io-worker@%h
