"""
Task orchestration workflows using Celery chains and groups.

This module provides high-level workflow functions that compose multiple
Celery tasks into complex processing pipelines.
"""

import logging
from typing import List, Optional, Tuple

from celery import chain, group, chord
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from earthgazer.database.definitions import Location, CaptureData
from earthgazer.settings import EarthGazerSettings
from earthgazer.tasks import (
    discover_images_task,
    backup_capture_task,
    download_bands_task,
    stack_and_crop_task,
    compute_ndvi_task,
    generate_rgb_task,
    temporal_analysis_task
)

logger = logging.getLogger(__name__)


def get_location_bounds(location_id: int) -> Tuple[float, float, float, float]:
    """
    Get the bounds for a specific location.

    Args:
        location_id: Location ID to get bounds for

    Returns:
        Tuple of (min_lon, min_lat, max_lon, max_lat)
    """
    settings = EarthGazerSettings()
    engine = create_engine(settings.database.url, echo=False)

    with Session(engine) as session:
        location = session.query(Location).where(Location.id == location_id).first()
        if location is None:
            raise ValueError(f"Location {location_id} not found")
        return location.bounds


def process_single_capture_workflow(
    capture_id: int,
    bands: List[str] = None,
    bounds: Tuple[float, float, float, float] = None
):
    """
    Workflow to process a single capture through the entire pipeline.

    Pipeline:
    1. Download bands
    2. Stack and crop
    3. Compute NDVI and RGB in parallel
    4. Return results

    Args:
        capture_id: CaptureData ID to process
        bands: List of band identifiers (default: ["B02", "B03", "B04", "B08"])
        bounds: Geographic bounds for cropping (min_lon, min_lat, max_lon, max_lat)

    Returns:
        AsyncResult for the workflow
    """
    if bands is None:
        bands = ["B02", "B03", "B04", "B08"]

    logger.info(f"Starting workflow for capture {capture_id}")

    # Build workflow chain
    workflow = chain(
        # Step 1: Download bands
        download_bands_task.si(capture_id, bands),

        # Step 2: Stack and crop
        stack_and_crop_task.si(capture_id, bands, bounds),

        # Step 3: Compute NDVI and RGB in parallel
        group(
            compute_ndvi_task.si(capture_id, bands),
            generate_rgb_task.si(capture_id, bands)
        )
    )

    # Execute workflow
    result = workflow.apply_async()
    logger.info(f"Workflow submitted for capture {capture_id}: {result.id}")

    return result


def process_multiple_captures_workflow(
    capture_ids: List[int],
    bands: List[str] = None,
    bounds: Tuple[float, float, float, float] = None,
    run_temporal_analysis: bool = True
):
    """
    Workflow to process multiple captures in parallel.

    Pipeline:
    1. Process each capture in parallel
    2. Optionally run temporal analysis after all captures complete

    Args:
        capture_ids: List of CaptureData IDs to process
        bands: List of band identifiers (default: ["B02", "B03", "B04", "B08"])
        bounds: Geographic bounds for cropping
        run_temporal_analysis: Whether to run temporal analysis after processing

    Returns:
        AsyncResult for the workflow
    """
    if bands is None:
        bands = ["B02", "B03", "B04", "B08"]

    logger.info(f"Starting workflow for {len(capture_ids)} captures")

    # Create parallel processing tasks for each capture
    capture_workflows = []
    for capture_id in capture_ids:
        # Each capture gets its own workflow chain
        capture_workflow = chain(
            download_bands_task.si(capture_id, bands),
            stack_and_crop_task.si(capture_id, bands, bounds),
            group(
                compute_ndvi_task.si(capture_id, bands),
                generate_rgb_task.si(capture_id, bands)
            )
        )
        capture_workflows.append(capture_workflow)

    if run_temporal_analysis:
        # Use chord to wait for all captures, then run temporal analysis
        workflow = chord(
            group(*capture_workflows),
            temporal_analysis_task.si()
        )
    else:
        # Just run captures in parallel without final callback
        workflow = group(*capture_workflows)

    # Execute workflow
    result = workflow.apply_async()
    logger.info(f"Workflow submitted for {len(capture_ids)} captures: {result.id}")

    return result


def discovery_and_backup_workflow(location_ids: Optional[List[int]] = None):
    """
    Workflow to discover new images and back them up.

    Pipeline:
    1. Discover new images from BigQuery
    2. Backup discovered images to project bucket

    Args:
        location_ids: Optional list of Location IDs to query

    Returns:
        AsyncResult for the workflow
    """
    logger.info("Starting discovery and backup workflow")

    # Chain discovery and backup
    workflow = chain(
        discover_images_task.si(location_ids),
        backup_capture_task.s()  # Pass discovered IDs to backup task
    )

    # Execute workflow
    result = workflow.apply_async()
    logger.info(f"Discovery and backup workflow submitted: {result.id}")

    return result


def full_pipeline_workflow(
    location_ids: Optional[List[int]] = None,
    bands: List[str] = None,
    bounds: Tuple[float, float, float, float] = None,
    mission_filter: Optional[str] = "SENTINEL-2A"
):
    """
    Complete end-to-end workflow: discovery → backup → processing → analysis.

    Pipeline:
    1. Discover new images
    2. Backup to project bucket
    3. Query backed-up captures
    4. Process all captures in parallel
    5. Run temporal analysis

    Args:
        location_ids: Optional list of Location IDs to query
        bands: List of band identifiers (default: ["B02", "B03", "B04", "B08"])
        bounds: Geographic bounds for cropping
        mission_filter: Filter captures by mission (e.g., "SENTINEL-2A")

    Returns:
        AsyncResult for the workflow
    """
    if bands is None:
        bands = ["B02", "B03", "B04", "B08"]

    logger.info("Starting full pipeline workflow")

    # Step 1 & 2: Discovery and backup
    discovery_result = discovery_and_backup_workflow(location_ids)

    # Wait for discovery/backup to complete, then get backed-up captures
    # Note: In production, you'd use a callback task here
    # For now, this demonstrates the workflow structure

    # Get captures to process
    settings = EarthGazerSettings()
    engine = create_engine(settings.database.url, echo=False)

    with Session(engine) as session:
        query = session.query(CaptureData).where(CaptureData.backed_up == True)

        if mission_filter:
            query = query.where(CaptureData.mission_id == mission_filter)

        captures = query.all()
        capture_ids = [c.id for c in captures]

    logger.info(f"Found {len(capture_ids)} backed-up captures to process")

    # Step 3, 4, 5: Process all captures and run analysis
    if capture_ids:
        processing_result = process_multiple_captures_workflow(
            capture_ids,
            bands,
            bounds,
            run_temporal_analysis=True
        )
        return processing_result
    else:
        logger.warning("No captures found to process")
        return None


def reprocess_existing_captures_workflow(
    mission_filter: Optional[str] = "SENTINEL-2A",
    bands: List[str] = None,
    bounds: Tuple[float, float, float, float] = None,
    limit: Optional[int] = None
):
    """
    Workflow to reprocess existing backed-up captures.

    Useful for regenerating features with different parameters or
    processing captures that were backed up but never processed.

    Args:
        mission_filter: Filter captures by mission
        bands: List of band identifiers (default: ["B02", "B03", "B04", "B08"])
        bounds: Geographic bounds for cropping
        limit: Optional limit on number of captures to process

    Returns:
        AsyncResult for the workflow
    """
    if bands is None:
        bands = ["B02", "B03", "B04", "B08"]

    logger.info("Starting reprocessing workflow for existing captures")

    # Get backed-up captures
    settings = EarthGazerSettings()
    engine = create_engine(settings.database.url, echo=False)

    with Session(engine) as session:
        query = session.query(CaptureData).where(CaptureData.backed_up == True)

        if mission_filter:
            query = query.where(CaptureData.mission_id == mission_filter)

        if limit:
            query = query.limit(limit)

        captures = query.all()
        capture_ids = [c.id for c in captures]

    logger.info(f"Reprocessing {len(capture_ids)} captures")

    if capture_ids:
        return process_multiple_captures_workflow(
            capture_ids,
            bands,
            bounds,
            run_temporal_analysis=True
        )
    else:
        logger.warning("No captures found to reprocess")
        return None


def process_location_captures_workflow(
    location_id: int,
    bands: List[str] = None,
    mission_filter: Optional[str] = None,
    limit: Optional[int] = None,
    run_temporal_analysis: bool = True
):
    """
    Workflow to process all backed-up captures for a specific location.

    Uses the location's region bounds for cropping automatically.

    Pipeline:
    1. Get location bounds from database
    2. Find all backed-up captures
    3. Process captures using location bounds
    4. Optionally run temporal analysis

    Args:
        location_id: Location ID to process captures for
        bands: List of band identifiers (default: ["B02", "B03", "B04", "B08"])
        mission_filter: Optional filter by mission (e.g., "SENTINEL-2A")
        limit: Optional limit on number of captures to process
        run_temporal_analysis: Whether to run temporal analysis after processing

    Returns:
        AsyncResult for the workflow
    """
    if bands is None:
        bands = ["B02", "B03", "B04", "B08"]

    logger.info(f"Starting workflow for location {location_id}")

    # Get location bounds
    bounds = get_location_bounds(location_id)
    logger.info(f"Using location bounds: {bounds}")

    # Get backed-up captures
    settings = EarthGazerSettings()
    engine = create_engine(settings.database.url, echo=False)

    with Session(engine) as session:
        query = session.query(CaptureData).where(CaptureData.backed_up == True)

        if mission_filter:
            query = query.where(CaptureData.mission_id == mission_filter)

        query = query.order_by(CaptureData.sensing_time.desc())

        if limit:
            query = query.limit(limit)

        captures = query.all()
        capture_ids = [c.id for c in captures]

    logger.info(f"Found {len(capture_ids)} backed-up captures to process")

    if capture_ids:
        return process_multiple_captures_workflow(
            capture_ids,
            bands,
            bounds,
            run_temporal_analysis=run_temporal_analysis
        )
    else:
        logger.warning("No captures found to process for location")
        return None
