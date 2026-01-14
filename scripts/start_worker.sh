#!/bin/bash
# Start Celery worker for EarthGazer processing
#
# This script starts a general-purpose Celery worker that listens to all queues.
# For production, consider using specialized workers (start_io_worker.sh, start_cpu_worker.sh).

set -e

echo "Starting EarthGazer Celery worker..."

# Start Celery worker
celery -A earthgazer.celery_app worker \
    --loglevel=info \
    --concurrency=4 \
    --max-tasks-per-child=100 \
    --time-limit=3600 \
    --soft-time-limit=3300 \
    -Q io_queue,cpu_queue,default \
    --hostname=worker@%h
