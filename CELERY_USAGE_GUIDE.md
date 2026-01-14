# Celery Task Queue Usage Guide

This guide covers how to use the Celery task queue system for parallel hyperspectral image processing in EarthGazer.

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture Overview](#architecture-overview)
- [Running Workers](#running-workers)
- [Submitting Tasks](#submitting-tasks)
- [Monitoring](#monitoring)
- [Production Deployment](#production-deployment)
- [Troubleshooting](#troubleshooting)

## Quick Start

### Development Environment

The devcontainer automatically starts a Celery worker when you open the project. You can start processing immediately:

```python
from earthgazer.workflows import process_single_capture_workflow

# Process a single capture
result = process_single_capture_workflow(
    capture_id=123,
    bands=["B02", "B03", "B04", "B08"],
    bounds=(-98.898926, 18.955649, -98.399734, 19.282628)
)

# Check result
print(result.get())
```

### Manual Worker Start

If you need to start a worker manually:

```bash
# General worker (all queues)
./scripts/start_worker.sh

# I/O-specialized worker (downloads/uploads)
./scripts/start_io_worker.sh

# CPU-specialized worker (image processing)
./scripts/start_cpu_worker.sh
```

## Architecture Overview

### Task Queues

EarthGazer uses three separate queues to optimize task execution:

1. **io_queue**: I/O-bound tasks (downloads, uploads, database queries)
   - High concurrency (8 workers)
   - Tasks: `discover_images_task`, `backup_capture_task`, `download_bands_task`

2. **cpu_queue**: CPU-bound tasks (image processing, NDVI computation)
   - Lower concurrency (2-4 workers)
   - Tasks: `stack_and_crop_task`, `compute_ndvi_task`, `generate_rgb_task`, `temporal_analysis_task`

3. **default**: Miscellaneous tasks not specifically routed

### Processing Pipeline

```
┌─────────────┐
│  Discovery  │ (io_queue)
└──────┬──────┘
       │
┌──────▼──────┐
│   Backup    │ (io_queue)
└──────┬──────┘
       │
┌──────▼──────┐
│  Download   │ (io_queue)
└──────┬──────┘
       │
┌──────▼──────┐
│Stack & Crop │ (cpu_queue)
└──────┬──────┘
       │
    ┌──▼──┐
    │Split│
    └┬───┬┘
┌────▼─┐ ┌▼────┐
│ NDVI │ │ RGB │ (parallel, cpu_queue)
└────┬─┘ └┬────┘
     └────┬┘
    ┌─────▼─────┐
    │  Analysis │ (cpu_queue)
    └───────────┘
```

## Running Workers

### Development

Workers auto-start in devcontainer. To restart or run additional workers:

```bash
# View worker logs
docker logs -f earthgazer-celery-worker-1

# Restart worker
docker restart earthgazer-celery-worker-1

# Run additional worker in separate terminal
celery -A earthgazer.celery_app worker --loglevel=info -Q io_queue
```

### Production

Start the full production stack:

```bash
# Copy environment template
cp .env.prod.example .env.prod

# Edit .env.prod with your credentials
nano .env.prod

# Start all services
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f celery-io-worker
docker-compose -f docker-compose.prod.yml logs -f celery-cpu-worker

# Scale workers
docker-compose -f docker-compose.prod.yml up -d --scale celery-io-worker=4
```

## Submitting Tasks

### Individual Tasks

Execute single tasks directly:

```python
from earthgazer.tasks import (
    discover_images_task,
    download_bands_task,
    compute_ndvi_task
)

# Discover new images
result = discover_images_task.delay()
new_capture_ids = result.get(timeout=300)  # Wait up to 5 minutes
print(f"Found {len(new_capture_ids)} new captures")

# Download bands for a specific capture
result = download_bands_task.delay(
    capture_id=123,
    bands=["B02", "B03", "B04", "B08"]
)
scene_folder = result.get()

# Compute NDVI
result = compute_ndvi_task.delay(
    capture_id=123,
    bands=["B02", "B03", "B04", "B08"]
)
ndvi_path = result.get()
```

### Workflows

Use pre-built workflows for complex operations:

```python
from earthgazer.workflows import (
    process_single_capture_workflow,
    process_multiple_captures_workflow,
    full_pipeline_workflow,
    reprocess_existing_captures_workflow
)

# Process one capture end-to-end
result = process_single_capture_workflow(
    capture_id=123,
    bands=["B02", "B03", "B04", "B08"],
    bounds=(-98.898926, 18.955649, -98.399734, 19.282628)
)

# Process multiple captures in parallel
result = process_multiple_captures_workflow(
    capture_ids=[120, 121, 122, 123, 124],
    bands=["B02", "B03", "B04", "B08"],
    bounds=(-98.898926, 18.955649, -98.399734, 19.282628),
    run_temporal_analysis=True
)

# Full pipeline: discover → backup → process → analyze
result = full_pipeline_workflow(
    location_ids=[1],
    bands=["B02", "B03", "B04", "B08"],
    bounds=(-98.898926, 18.955649, -98.399734, 19.282628),
    mission_filter="SENTINEL-2A"
)

# Reprocess existing backed-up captures
result = reprocess_existing_captures_workflow(
    mission_filter="SENTINEL-2A",
    limit=10  # Process first 10 captures
)
```

### Checking Task Status

```python
from celery.result import AsyncResult

# Get result by task ID
task_id = "550e8400-e29b-41d4-a716-446655440000"
result = AsyncResult(task_id)

# Check status
print(f"State: {result.state}")
print(f"Ready: {result.ready()}")
print(f"Successful: {result.successful()}")

# Get result (blocks until complete)
if result.ready():
    print(f"Result: {result.result}")

# Get traceback on failure
if result.failed():
    print(f"Error: {result.traceback}")
```

## Monitoring

### Flower Web UI

Flower provides a real-time web interface for monitoring Celery tasks.

**Development:**
```bash
# Start Flower
celery -A earthgazer.celery_app flower --port=5555

# Access at http://localhost:5555
```

**Production:**
Flower is automatically started on port 5555 with basic authentication.
- URL: `http://your-server:5555`
- Credentials: Set in `.env.prod` (FLOWER_USER, FLOWER_PASSWORD)

### Database Monitoring

Query the `task_executions` table for detailed task history:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from earthgazer.database.definitions import TaskExecution, TaskStatus
from earthgazer.settings import EarthGazerSettings

settings = EarthGazerSettings()
engine = create_engine(settings.database.url)

with Session(engine) as session:
    # Get recent tasks
    recent = session.query(TaskExecution).order_by(
        TaskExecution.created_at.desc()
    ).limit(10).all()

    for task in recent:
        print(f"{task.task_name}: {task.status} ({task.duration}s)")

    # Count tasks by status
    from sqlalchemy import func
    counts = session.query(
        TaskExecution.status,
        func.count(TaskExecution.id)
    ).group_by(TaskExecution.status).all()

    for status, count in counts:
        print(f"{status}: {count}")

    # Find failed tasks
    failed = session.query(TaskExecution).filter_by(
        status=TaskStatus.FAILURE
    ).all()

    for task in failed:
        print(f"{task.task_name} failed: {task.error}")
```

### Command Line

```bash
# Inspect active tasks
celery -A earthgazer.celery_app inspect active

# View registered tasks
celery -A earthgazer.celery_app inspect registered

# View worker statistics
celery -A earthgazer.celery_app inspect stats

# Revoke a task
celery -A earthgazer.celery_app control revoke <task-id>

# Purge all tasks from queue
celery -A earthgazer.celery_app purge
```

## Production Deployment

### Environment Setup

1. **Create production environment file:**
   ```bash
   cp .env.prod.example .env.prod
   ```

2. **Configure credentials:**
   ```bash
   # Generate secure passwords
   openssl rand -base64 32  # For DB_PASSWORD
   openssl rand -base64 32  # For REDIS_PASSWORD

   # Edit .env.prod
   nano .env.prod
   ```

3. **Set up Google Cloud credentials:**
   ```bash
   # Encode service account JSON to base64
   cat service-account.json | base64 -w 0 > service-account.b64
   # Copy content to GCLOUD_SERVICE_ACCOUNT in .env.prod
   ```

### Starting Services

```bash
# Build images
docker-compose -f docker-compose.prod.yml build

# Start all services
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# Run database migrations
docker-compose -f docker-compose.prod.yml exec app alembic upgrade head

# Check service health
docker-compose -f docker-compose.prod.yml ps
```

### Scaling

```bash
# Scale I/O workers for high download throughput
docker-compose -f docker-compose.prod.yml up -d --scale celery-io-worker=5

# Scale CPU workers for intensive processing
docker-compose -f docker-compose.prod.yml up -d --scale celery-cpu-worker=8

# View resource usage
docker stats
```

### Maintenance

```bash
# View logs
docker-compose -f docker-compose.prod.yml logs -f --tail=100

# Restart workers (to apply code changes)
docker-compose -f docker-compose.prod.yml restart celery-io-worker celery-cpu-worker

# Update code
git pull
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# Backup database
docker-compose -f docker-compose.prod.yml exec db pg_dump -U earthgazer earthgazer_prod > backup.sql
```

## Troubleshooting

### Workers Not Starting

**Check logs:**
```bash
docker-compose logs celery-worker
```

**Common issues:**
- Redis connection failed: Verify `EARTHGAZER__CELERY__BROKER_URL`
- Database connection failed: Check `EARTHGAZER__DATABASE__*` variables
- Import errors: Ensure all dependencies are installed

### Tasks Stuck in Pending

**Possible causes:**
1. No workers listening to the queue
2. Workers crashed
3. Redis connection lost

**Solutions:**
```bash
# Check worker status
celery -A earthgazer.celery_app inspect active

# Restart workers
docker restart earthgazer-celery-worker-1

# Purge stale tasks
celery -A earthgazer.celery_app purge
```

### High Memory Usage

**CPU workers** processing large images may consume significant memory.

**Solutions:**
- Reduce `--concurrency` for CPU workers
- Set `--max-tasks-per-child` to restart workers periodically
- Increase available RAM or use swap
- Process smaller batches

### Task Failures

**Check task execution records:**
```python
from earthgazer.database.definitions import TaskExecution, TaskStatus

failed_tasks = session.query(TaskExecution).filter_by(
    status=TaskStatus.FAILURE
).order_by(TaskExecution.completed_at.desc()).limit(10).all()

for task in failed_tasks:
    print(f"Task: {task.task_name}")
    print(f"Error: {task.error}")
    print(f"Capture ID: {task.capture_id}")
    print("---")
```

**Common errors:**
- **FileNotFoundError**: Band files missing, re-run download
- **NetworkError**: Transient network issue, task will auto-retry
- **MemoryError**: Reduce worker concurrency

### Redis Out of Memory

**Check Redis memory:**
```bash
docker exec earthgazer-redis-1 redis-cli INFO memory
```

**Solutions:**
- Reduce `result_expires` in settings (currently 1 hour)
- Increase Redis max memory in docker-compose
- Use Redis persistence (already configured with AOF)

### Performance Optimization

**Slow processing:**
1. Check worker concurrency matches your CPU cores
2. Ensure I/O and CPU workers are on separate queues
3. Monitor system resources (CPU, RAM, disk I/O)
4. Consider horizontal scaling (more workers)

**Profiling:**
```python
# Enable task time limits
from earthgazer.celery_app import app

app.conf.update(
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3300  # 55 min soft limit
)
```

## Best Practices

1. **Always use workflows** for multi-step operations to ensure proper ordering
2. **Monitor task executions** in the database to identify bottlenecks
3. **Set appropriate concurrency** for your hardware (I/O: 8+, CPU: 2-4 per core)
4. **Use `delay()` not `apply()`** to run tasks asynchronously
5. **Handle task failures** gracefully with retry logic (already configured)
6. **Scale horizontally** by adding more worker containers
7. **Regular maintenance**: restart workers periodically to prevent memory leaks
8. **Backup Redis** if task results are critical

## Additional Resources

- [Celery Documentation](https://docs.celeryq.dev/)
- [Flower Documentation](https://flower.readthedocs.io/)
- [Redis Documentation](https://redis.io/docs/)
- [Implementation Plan](CELERY_IMPLEMENTATION_PLAN.md)
