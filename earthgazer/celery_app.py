"""
Celery application configuration for EarthGazer.

This module initializes the Celery app with Redis as the message broker
and result backend. It provides task routing for separating I/O-bound and
CPU-bound tasks into different queues.
"""

import logging
from celery import Celery
from earthgazer.settings import EarthGazerSettings

logger = logging.getLogger(__name__)

# Initialize settings
settings = EarthGazerSettings()

# Create Celery app
app = Celery('earthgazer')

# Configure Celery from settings
app.conf.update(
    broker_url=settings.celery.broker_url,
    result_backend=settings.celery.result_backend,
    task_serializer=settings.celery.task_serializer,
    result_serializer=settings.celery.result_serializer,
    accept_content=settings.celery.accept_content,
    timezone=settings.celery.timezone,
    enable_utc=settings.celery.enable_utc,
    worker_concurrency=settings.celery.worker_concurrency,
    worker_prefetch_multiplier=settings.celery.worker_prefetch_multiplier,
    task_acks_late=settings.celery.task_acks_late,
    task_reject_on_worker_lost=settings.celery.task_reject_on_worker_lost,
    result_expires=settings.celery.result_expires,

    # Task routing - separate queues for different workload types
    task_routes={
        'earthgazer.tasks.discover_images_task': {'queue': 'io_queue'},
        'earthgazer.tasks.backup_image_task': {'queue': 'io_queue'},
        'earthgazer.tasks.download_bands_task': {'queue': 'io_queue'},
        'earthgazer.tasks.stack_and_crop_task': {'queue': 'cpu_queue'},
        'earthgazer.tasks.compute_ndvi_task': {'queue': 'cpu_queue'},
        'earthgazer.tasks.generate_rgb_task': {'queue': 'cpu_queue'},
        'earthgazer.tasks.save_outputs_task': {'queue': 'io_queue'},
        'earthgazer.tasks.temporal_analysis_task': {'queue': 'cpu_queue'},
    },

    # Default queue for tasks not explicitly routed
    task_default_queue='default',

    # Task result extended details
    result_extended=True,

    # Enable task events for monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

logger.info(f"Celery app initialized with broker: {settings.celery.broker_url}")
logger.info(f"Task queues configured: io_queue, cpu_queue, default")

# Auto-discover tasks from tasks.py module
app.autodiscover_tasks(['earthgazer'])

if __name__ == '__main__':
    app.start()
