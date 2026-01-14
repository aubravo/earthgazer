"""
Celery tasks for EarthGazer hyperspectral image processing.

This module defines Celery tasks that wrap the processing functions
from the earthgazer.processing package. Each task is designed to be
independently executable and retryable.
"""

import logging
from typing import List, Optional, Tuple

from celery import Task
from celery.exceptions import Reject
from google.oauth2 import service_account

from earthgazer.celery_app import app
from earthgazer.processing import discovery, download, preprocessing, features, io, analysis
from earthgazer.settings import EarthGazerSettings

logger = logging.getLogger(__name__)


def get_service_account_credentials():
    """Get Google Cloud service account credentials from settings."""
    settings = EarthGazerSettings()
    return service_account.Credentials.from_service_account_info(
        settings.gcloud.service_account,
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )


@app.task(
    bind=True,
    name='earthgazer.tasks.discover_images_task',
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def discover_images_task(self: Task, location_ids: Optional[List[int]] = None) -> List[int]:
    """
    Celery task: Discover new satellite images from BigQuery.

    Args:
        location_ids: Optional list of Location IDs to query (if None, queries all active)

    Returns:
        List of newly discovered CaptureData IDs
    """
    logger.info(f"Task {self.request.id}: Starting image discovery")

    try:
        settings = EarthGazerSettings()
        creds = get_service_account_credentials()

        # If location_ids provided, load those specific locations
        locations = None
        if location_ids:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import Session
            from earthgazer.database.definitions import Location

            engine = create_engine(settings.database.url, echo=False)
            with Session(engine) as session:
                locations = session.query(Location).where(Location.id.in_(location_ids)).all()

        new_capture_ids = discovery.check_for_new_images(settings, creds, locations)

        logger.info(f"Task {self.request.id}: Discovered {len(new_capture_ids)} new captures")
        return new_capture_ids

    except Exception as e:
        logger.error(f"Task {self.request.id}: Error discovering images: {e}")
        raise


@app.task(
    bind=True,
    name='earthgazer.tasks.backup_capture_task',
    max_retries=5,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def backup_capture_task(self: Task, capture_ids: Optional[List[int]] = None) -> List[int]:
    """
    Celery task: Backup captures from public GCS to project bucket.

    Args:
        capture_ids: Optional list of CaptureData IDs to backup (if None, backs up all)

    Returns:
        List of successfully backed up CaptureData IDs
    """
    logger.info(f"Task {self.request.id}: Starting capture backup")

    try:
        settings = EarthGazerSettings()
        creds = get_service_account_credentials()

        backed_up_ids = download.backup_capture_to_project_bucket(settings, creds, capture_ids)

        logger.info(f"Task {self.request.id}: Backed up {len(backed_up_ids)} captures")
        return backed_up_ids

    except Exception as e:
        logger.error(f"Task {self.request.id}: Error backing up captures: {e}")
        raise


@app.task(
    bind=True,
    name='earthgazer.tasks.download_bands_task',
    max_retries=5,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def download_bands_task(
    self: Task,
    capture_id: int,
    bands: List[str] = None
) -> Optional[str]:
    """
    Celery task: Download specific bands for a capture.

    Args:
        capture_id: CaptureData ID to download
        bands: List of band identifiers (default: ["B02", "B03", "B04", "B08"])

    Returns:
        Path to downloaded scene folder, or None if download failed
    """
    if bands is None:
        bands = ["B02", "B03", "B04", "B08"]

    logger.info(f"Task {self.request.id}: Downloading bands {bands} for capture {capture_id}")

    try:
        settings = EarthGazerSettings()
        creds = get_service_account_credentials()

        scene_folder = download.download_capture_bands(settings, creds, capture_id, bands)

        if scene_folder is None:
            raise ValueError(f"Failed to download bands for capture {capture_id}")

        logger.info(f"Task {self.request.id}: Downloaded bands to {scene_folder}")
        return scene_folder

    except Exception as e:
        logger.error(f"Task {self.request.id}: Error downloading bands: {e}")
        raise


@app.task(
    bind=True,
    name='earthgazer.tasks.stack_and_crop_task',
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True
)
def stack_and_crop_task(
    self: Task,
    capture_id: int,
    bands: List[str] = None,
    bounds: Tuple[float, float, float, float] = None
) -> dict:
    """
    Celery task: Load, stack, and crop bands for a capture.

    Args:
        capture_id: CaptureData ID to process
        bands: List of band identifiers (default: ["B02", "B03", "B04", "B08"])
        bounds: Geographic bounds (min_lon, min_lat, max_lon, max_lat)

    Returns:
        Dict with keys: capture_id, bands, shape
    """
    if bands is None:
        bands = ["B02", "B03", "B04", "B08"]

    logger.info(f"Task {self.request.id}: Stacking and cropping capture {capture_id}")

    try:
        scene_folder = f"data/raw/{capture_id}/"

        # Load and stack bands
        stacked, meta = preprocessing.load_and_stack_bands(scene_folder, bands)

        # Crop if bounds provided
        if bounds:
            stacked, meta = preprocessing.crop_and_normalize(stacked, meta, bounds)

        # Store temporarily for next task (in production, could use shared storage)
        import numpy as np
        temp_path = f"data/processed/stacked_{capture_id}.npz"
        np.savez_compressed(temp_path, stacked=stacked, **meta)

        logger.info(f"Task {self.request.id}: Stacked shape {stacked.shape}, saved to {temp_path}")

        return {
            "capture_id": capture_id,
            "bands": bands,
            "shape": stacked.shape,
            "temp_path": temp_path
        }

    except Exception as e:
        logger.error(f"Task {self.request.id}: Error stacking/cropping: {e}")
        raise


@app.task(
    bind=True,
    name='earthgazer.tasks.compute_ndvi_task',
    max_retries=3
)
def compute_ndvi_task(
    self: Task,
    capture_id: int,
    bands: List[str] = None
) -> str:
    """
    Celery task: Compute NDVI for a capture.

    Args:
        capture_id: CaptureData ID to process
        bands: List of band identifiers (default: ["B02", "B03", "B04", "B08"])

    Returns:
        Path to saved NDVI GeoTIFF
    """
    if bands is None:
        bands = ["B02", "B03", "B04", "B08"]

    logger.info(f"Task {self.request.id}: Computing NDVI for capture {capture_id}")

    try:
        import numpy as np

        # Load stacked data
        temp_path = f"data/processed/stacked_{capture_id}.npz"
        data = np.load(temp_path, allow_pickle=True)
        stacked = data['stacked']

        # Reconstruct metadata
        meta = {k: data[k].item() if data[k].shape == () else data[k] for k in data.files if k != 'stacked'}

        # Compute NDVI
        ndvi = features.compute_ndvi_from_stack(stacked, bands)

        # Save NDVI
        output_path = f"data/features/ndvi_{capture_id}.tif"
        io.save_raster(output_path, ndvi, meta)

        logger.info(f"Task {self.request.id}: NDVI saved to {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Task {self.request.id}: Error computing NDVI: {e}")
        raise


@app.task(
    bind=True,
    name='earthgazer.tasks.generate_rgb_task',
    max_retries=3
)
def generate_rgb_task(
    self: Task,
    capture_id: int,
    bands: List[str] = None
) -> str:
    """
    Celery task: Generate RGB composite for a capture.

    Args:
        capture_id: CaptureData ID to process
        bands: List of band identifiers (default: ["B02", "B03", "B04", "B08"])

    Returns:
        Path to saved RGB GeoTIFF
    """
    if bands is None:
        bands = ["B02", "B03", "B04", "B08"]

    logger.info(f"Task {self.request.id}: Generating RGB for capture {capture_id}")

    try:
        import numpy as np

        # Load stacked data
        temp_path = f"data/processed/stacked_{capture_id}.npz"
        data = np.load(temp_path, allow_pickle=True)
        stacked = data['stacked']

        # Reconstruct metadata
        meta = {k: data[k].item() if data[k].shape == () else data[k] for k in data.files if k != 'stacked'}

        # Generate RGB
        rgb = features.create_rgb_from_stack(stacked, bands)

        # Save RGB
        output_path = f"data/features/rgb_{capture_id}.tif"
        io.save_rgb(output_path, rgb, meta)

        logger.info(f"Task {self.request.id}: RGB saved to {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Task {self.request.id}: Error generating RGB: {e}")
        raise


@app.task(
    bind=True,
    name='earthgazer.tasks.temporal_analysis_task',
    max_retries=3
)
def temporal_analysis_task(
    self: Task,
    ndvi_files_pattern: str = "data/features/ndvi_*.tif"
) -> dict:
    """
    Celery task: Perform temporal analysis on NDVI time series.

    Args:
        ndvi_files_pattern: Glob pattern for NDVI files

    Returns:
        Dict with paths to generated plots
    """
    logger.info(f"Task {self.request.id}: Starting temporal analysis")

    try:
        settings = EarthGazerSettings()

        # Compute time series
        df = analysis.compute_ndvi_time_series(
            settings,
            ndvi_files_pattern,
            "ndvi_over_time.png"
        )

        # Compute trend map
        slopes = analysis.compute_ndvi_trend_map(
            settings,
            ndvi_files_pattern,
            "ndvi_trend_map.png"
        )

        logger.info(f"Task {self.request.id}: Temporal analysis complete")

        return {
            "time_series_plot": "ndvi_over_time.png",
            "trend_map_plot": "ndvi_trend_map.png",
            "num_records": len(df)
        }

    except Exception as e:
        logger.error(f"Task {self.request.id}: Error in temporal analysis: {e}")
        raise
