"""
Monitoring and logging setup for Celery tasks.

This module configures Celery signals to track task execution and
optionally store task information in the database for monitoring.
"""

import logging
from datetime import datetime
from typing import Optional

from celery import signals
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from earthgazer.database.definitions import TaskExecution, TaskStatus
from earthgazer.settings import EarthGazerSettings

logger = logging.getLogger(__name__)


# Global flag to enable/disable database tracking
ENABLE_DB_TRACKING = True


def get_capture_id_from_task(task, args, kwargs) -> Optional[int]:
    """
    Extract capture_id from task arguments if present.

    Args:
        task: Celery task instance
        args: Task positional arguments
        kwargs: Task keyword arguments

    Returns:
        capture_id if found, else None
    """
    # Check kwargs first
    if 'capture_id' in kwargs:
        return kwargs['capture_id']

    # Check first positional argument for single capture tasks
    if args and len(args) > 0 and isinstance(args[0], int):
        return args[0]

    return None


@signals.task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    """
    Signal handler called before a task executes.

    Logs task start and optionally creates database record.
    """
    logger.info(f"Task {task.name}[{task_id}] starting", extra={
        'task_id': task_id,
        'task_name': task.name,
        'args': args,
        'kwargs': kwargs,
    })

    if not ENABLE_DB_TRACKING:
        return

    try:
        settings = EarthGazerSettings()
        engine = create_engine(settings.database.url, echo=False)

        capture_id = get_capture_id_from_task(task, args, kwargs)

        with Session(engine) as session:
            # Check if task execution already exists (for retries)
            existing = session.query(TaskExecution).filter_by(task_id=task_id).first()

            if existing:
                # Update existing record (retry case)
                existing.status = TaskStatus.STARTED
                existing.started_at = datetime.now()
                existing.retries += 1
            else:
                # Create new task execution record
                task_exec = TaskExecution(
                    task_id=task_id,
                    task_name=task.name,
                    capture_id=capture_id,
                    status=TaskStatus.STARTED,
                    started_at=datetime.now()
                )
                session.add(task_exec)

            session.commit()

    except Exception as e:
        logger.warning(f"Failed to record task start in database: {e}")


@signals.task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None,
                         retval=None, state=None, **extra):
    """
    Signal handler called after a task executes (success or failure).

    Logs task completion and updates database record.
    """
    runtime = extra.get('runtime', 0)

    logger.info(f"Task {task.name}[{task_id}] completed with state {state}", extra={
        'task_id': task_id,
        'task_name': task.name,
        'state': state,
        'runtime': runtime,
        'result': str(retval)[:500] if retval else None,  # Truncate long results
    })

    if not ENABLE_DB_TRACKING:
        return

    try:
        settings = EarthGazerSettings()
        engine = create_engine(settings.database.url, echo=False)

        with Session(engine) as session:
            task_exec = session.query(TaskExecution).filter_by(task_id=task_id).first()

            if task_exec:
                task_exec.status = TaskStatus.SUCCESS if state == 'SUCCESS' else TaskStatus.FAILURE
                task_exec.completed_at = datetime.now()
                task_exec.duration = runtime
                task_exec.result = str(retval)[:1000] if retval else None  # Store result (truncated)

                session.commit()

    except Exception as e:
        logger.warning(f"Failed to update task completion in database: {e}")


@signals.task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, args=None,
                         kwargs=None, traceback=None, einfo=None, **extra):
    """
    Signal handler called when a task fails.

    Logs error details and updates database record.
    """
    logger.error(f"Task {sender.name}[{task_id}] failed with exception: {exception}", extra={
        'task_id': task_id,
        'task_name': sender.name,
        'exception': str(exception),
        'traceback': str(traceback)[:1000] if traceback else None,
    })

    if not ENABLE_DB_TRACKING:
        return

    try:
        settings = EarthGazerSettings()
        engine = create_engine(settings.database.url, echo=False)

        with Session(engine) as session:
            task_exec = session.query(TaskExecution).filter_by(task_id=task_id).first()

            if task_exec:
                task_exec.status = TaskStatus.FAILURE
                task_exec.completed_at = datetime.now()
                task_exec.error = str(exception)[:2000]  # Store error (truncated)

                session.commit()

    except Exception as e:
        logger.warning(f"Failed to record task failure in database: {e}")


@signals.task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, einfo=None, **extra):
    """
    Signal handler called when a task is retried.

    Logs retry information and updates database record.
    """
    logger.warning(f"Task {sender.name}[{task_id}] retrying due to: {reason}", extra={
        'task_id': task_id,
        'task_name': sender.name,
        'reason': str(reason),
    })

    if not ENABLE_DB_TRACKING:
        return

    try:
        settings = EarthGazerSettings()
        engine = create_engine(settings.database.url, echo=False)

        with Session(engine) as session:
            task_exec = session.query(TaskExecution).filter_by(task_id=task_id).first()

            if task_exec:
                task_exec.status = TaskStatus.RETRY
                task_exec.error = str(reason)[:2000]

                session.commit()

    except Exception as e:
        logger.warning(f"Failed to record task retry in database: {e}")


@signals.task_revoked.connect
def task_revoked_handler(sender=None, request=None, terminated=None, signum=None,
                         expired=None, **extra):
    """
    Signal handler called when a task is revoked (cancelled).

    Logs revocation and updates database record.
    """
    task_id = request.id if request else None
    task_name = sender.name if sender else "unknown"

    logger.warning(f"Task {task_name}[{task_id}] revoked", extra={
        'task_id': task_id,
        'task_name': task_name,
        'terminated': terminated,
        'expired': expired,
    })

    if not ENABLE_DB_TRACKING or not task_id:
        return

    try:
        settings = EarthGazerSettings()
        engine = create_engine(settings.database.url, echo=False)

        with Session(engine) as session:
            task_exec = session.query(TaskExecution).filter_by(task_id=task_id).first()

            if task_exec:
                task_exec.status = TaskStatus.REVOKED
                task_exec.completed_at = datetime.now()
                task_exec.error = f"Task revoked (terminated={terminated}, expired={expired})"

                session.commit()

    except Exception as e:
        logger.warning(f"Failed to record task revocation in database: {e}")


def configure_monitoring(enable_db_tracking: bool = True):
    """
    Configure monitoring settings.

    Args:
        enable_db_tracking: Whether to enable database tracking of task executions
    """
    global ENABLE_DB_TRACKING
    ENABLE_DB_TRACKING = enable_db_tracking

    logger.info(f"Task monitoring configured (DB tracking: {ENABLE_DB_TRACKING})")


# Auto-configure on import
logger.info("Celery task monitoring initialized")
