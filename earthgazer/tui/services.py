"""
Services module - Data access and Celery interactions for the TUI.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def get_system_status() -> Dict[str, Any]:
    """Get overall system status including Redis, Celery, and database."""
    status = {
        "redis": False,
        "celery_workers": 0,
        "database": False,
        "locations": 0,
        "captures": 0,
        "backed_up": 0,
        "recent_tasks": 0,
    }

    # Check Redis
    try:
        import redis
        r = redis.Redis(host="redis", port=6379, socket_timeout=2)
        status["redis"] = r.ping()
    except Exception as e:
        logger.debug(f"Redis check failed: {e}")

    # Check Celery workers
    try:
        from earthgazer.celery_app import app
        inspect = app.control.inspect(timeout=2)
        ping = inspect.ping()
        if ping:
            status["celery_workers"] = len(ping)
    except Exception as e:
        logger.debug(f"Celery check failed: {e}")

    # Check database
    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import Session
        from earthgazer.settings import EarthGazerSettings
        from earthgazer.database.definitions import Location, CaptureData, TaskExecution

        settings = EarthGazerSettings()
        engine = create_engine(settings.database.url, echo=False)

        with Session(engine) as session:
            status["database"] = True
            status["locations"] = session.query(Location).count()
            status["captures"] = session.query(CaptureData).count()
            status["backed_up"] = session.query(CaptureData).filter(
                CaptureData.backed_up == True
            ).count()
            status["recent_tasks"] = session.query(TaskExecution).count()

    except Exception as e:
        logger.debug(f"Database check failed: {e}")

    return status


def get_active_tasks() -> List[Dict[str, Any]]:
    """Get list of currently active Celery tasks."""
    tasks = []

    try:
        from earthgazer.celery_app import app
        inspect = app.control.inspect(timeout=2)
        active = inspect.active()

        if active:
            for worker, worker_tasks in active.items():
                for task in worker_tasks:
                    tasks.append({
                        "id": task.get("id"),
                        "name": task.get("name"),
                        "worker": worker,
                        "args": task.get("args"),
                    })
    except Exception as e:
        logger.debug(f"Failed to get active tasks: {e}")

    return tasks


def get_queued_tasks() -> Dict[str, int]:
    """Get count of tasks in each queue."""
    queues = {"io_queue": 0, "cpu_queue": 0, "default": 0}

    try:
        import redis
        r = redis.Redis(host="redis", port=6379, db=0)

        for queue in queues:
            queues[queue] = r.llen(queue)
    except Exception as e:
        logger.debug(f"Failed to get queue status: {e}")

    return queues


def get_task_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent task execution history from database."""
    tasks = []

    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from earthgazer.settings import EarthGazerSettings
        from earthgazer.database.definitions import TaskExecution

        settings = EarthGazerSettings()
        engine = create_engine(settings.database.url, echo=False)

        with Session(engine) as session:
            executions = session.query(TaskExecution).order_by(
                TaskExecution.created_at.desc()
            ).limit(limit).all()

            for ex in executions:
                tasks.append({
                    "id": ex.task_id,
                    "name": ex.task_name,
                    "status": ex.status.value if ex.status else "UNKNOWN",
                    "capture_id": ex.capture_id,
                    "created_at": ex.created_at,
                    "duration": ex.duration,
                    "error": ex.error,
                })
    except Exception as e:
        logger.debug(f"Failed to get task history: {e}")

    return tasks


def get_captures(
    backed_up_only: bool = False,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Get list of captures from database."""
    captures = []

    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from earthgazer.settings import EarthGazerSettings
        from earthgazer.database.definitions import CaptureData

        settings = EarthGazerSettings()
        engine = create_engine(settings.database.url, echo=False)

        with Session(engine) as session:
            query = session.query(CaptureData)

            if backed_up_only:
                query = query.filter(CaptureData.backed_up == True)

            query = query.order_by(CaptureData.sensing_time.desc()).limit(limit)

            for cap in query.all():
                captures.append({
                    "id": cap.id,
                    "main_id": cap.main_id,
                    "mission_id": cap.mission_id,
                    "sensing_time": cap.sensing_time,
                    "cloud_cover": cap.cloud_cover,
                    "backed_up": cap.backed_up,
                    "backup_location": cap.backup_location,
                })
    except Exception as e:
        logger.debug(f"Failed to get captures: {e}")

    return captures


def get_locations() -> List[Dict[str, Any]]:
    """Get list of locations from database."""
    locations = []

    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from earthgazer.settings import EarthGazerSettings
        from earthgazer.database.definitions import Location

        settings = EarthGazerSettings()
        engine = create_engine(settings.database.url, echo=False)

        with Session(engine) as session:
            for loc in session.query(Location).all():
                locations.append({
                    "id": loc.id,
                    "name": loc.name,
                    "latitude": loc.latitude,
                    "longitude": loc.longitude,
                    "active": loc.active,
                })
    except Exception as e:
        logger.debug(f"Failed to get locations: {e}")

    return locations


def run_discover_workflow(location_ids: Optional[List[int]] = None) -> str:
    """Start the discovery workflow and return task ID."""
    from earthgazer.tasks import discover_images_task

    result = discover_images_task.delay(location_ids)
    return result.id


def run_backup_workflow(capture_ids: Optional[List[int]] = None) -> str:
    """Start the backup workflow and return task ID."""
    from earthgazer.tasks import backup_capture_task

    result = backup_capture_task.delay(capture_ids)
    return result.id


def run_single_capture_workflow(
    capture_id: int,
    bands: List[str] = None,
    bounds: tuple = None
) -> str:
    """Start single capture processing workflow and return task ID."""
    from earthgazer.workflows import process_single_capture_workflow

    result = process_single_capture_workflow(
        capture_id=capture_id,
        bands=bands,
        bounds=bounds
    )
    return result.id


def run_discovery_and_backup_workflow(
    location_ids: Optional[List[int]] = None
) -> str:
    """Start discovery and backup workflow and return task ID."""
    from earthgazer.workflows import discovery_and_backup_workflow

    result = discovery_and_backup_workflow(location_ids)
    return result.id


def get_task_result(task_id: str) -> Dict[str, Any]:
    """Get the result of a task by ID."""
    try:
        from celery.result import AsyncResult
        from earthgazer.celery_app import app

        result = AsyncResult(task_id, app=app)
        return {
            "id": task_id,
            "status": result.status,
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else None,
            "result": result.result if result.ready() else None,
        }
    except Exception as e:
        logger.debug(f"Failed to get task result: {e}")
        return {"id": task_id, "status": "UNKNOWN", "error": str(e)}
