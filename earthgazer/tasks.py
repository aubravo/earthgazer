"""
Celery tasks for EarthGazer hyperspectral image processing.

This module defines Celery tasks that wrap the processing functions
from the earthgazer.processing package. Each task is designed to be
independently executable and retryable.
"""

import logging

from celery import Task
from google.oauth2 import service_account

from earthgazer.celery_app import app
from earthgazer.processing import analysis
from earthgazer.processing import discovery
from earthgazer.processing import download
from earthgazer.processing import features
from earthgazer.processing import io
from earthgazer.processing import preprocessing
from earthgazer.settings import EarthGazerSettings

logger = logging.getLogger(__name__)


def get_service_account_credentials():
    """Get Google Cloud service account credentials from settings."""
    settings = EarthGazerSettings()

    # Check if service_account is properly configured
    if not settings.gcloud.service_account:
        raise ValueError("GCloud service account is not configured")

    if isinstance(settings.gcloud.service_account, str):
        raise ValueError(
            "GCloud service account is still a string. Check that EARTHGAZER__GCLOUD__SERVICE_ACCOUNT is properly base64-encoded JSON."
        )

    if not isinstance(settings.gcloud.service_account, dict):
        raise ValueError(f"GCloud service account must be a dict, got {type(settings.gcloud.service_account)}")

    return service_account.Credentials.from_service_account_info(
        settings.gcloud.service_account, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )


@app.task(
    bind=True,
    name="earthgazer.tasks.discover_images_task",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def discover_images_task(self: Task, location_ids: list[int] | None = None) -> list[int]:
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
            from earthgazer.database.definitions import Location
            from earthgazer.database.session import get_session

            session = next(get_session())
            try:
                locations = session.query(Location).where(Location.id.in_(location_ids)).all()
            finally:
                session.close()

        new_capture_ids = discovery.check_for_new_images(settings, creds, locations)

        logger.info(f"Task {self.request.id}: Discovered {len(new_capture_ids)} new captures")
        return new_capture_ids

    except Exception as e:
        logger.error(f"Task {self.request.id}: Error discovering images: {e}")
        raise


@app.task(
    bind=True,
    name="earthgazer.tasks.backup_capture_task",
    max_retries=5,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def backup_capture_task(self: Task, capture_ids: list[int] | None = None) -> list[int]:
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
    name="earthgazer.tasks.backup_single_capture_task",
    max_retries=5,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def backup_single_capture_task(self: Task, capture_id: int) -> int:
    """
    Celery task: Backup a single capture from public GCS to project bucket.

    This task processes one capture at a time, allowing for better parallelization
    across multiple Celery workers.

    Args:
        capture_id: CaptureData ID to backup

    Returns:
        The capture_id if successful
    """
    logger.info(f"Task {self.request.id}: Backing up capture {capture_id}")

    try:
        settings = EarthGazerSettings()
        creds = get_service_account_credentials()

        # Backup single capture
        backed_up_ids = download.backup_capture_to_project_bucket(settings, creds, [capture_id])

        if backed_up_ids and capture_id in backed_up_ids:
            logger.info(f"Task {self.request.id}: Successfully backed up capture {capture_id}")
            return capture_id
        else:
            raise ValueError(f"Failed to backup capture {capture_id}")

    except Exception as e:
        logger.error(f"Task {self.request.id}: Error backing up capture {capture_id}: {e}")
        raise


@app.task(
    bind=True,
    name="earthgazer.tasks.download_bands_task",
    max_retries=5,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def download_bands_task(self: Task, capture_id: int, bands: list[str] = None) -> str | None:
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


@app.task(bind=True, name="earthgazer.tasks.stack_and_crop_task", max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def stack_and_crop_task(
    self: Task, capture_id: int, bands: list[str] = None, bounds: tuple[float, float, float, float] = None, force: bool = False
) -> dict:
    """
    Celery task: Load, stack, and crop bands for a capture.

    Args:
        capture_id: CaptureData ID to process
        bands: List of band identifiers (default: ["B02", "B03", "B04", "B08"])
        bounds: Geographic bounds (min_lon, min_lat, max_lon, max_lat)
        force: Force reprocessing even if output exists

    Returns:
        Dict with keys: capture_id, bands, shape, output_path, gcloud_path
    """
    if bands is None:
        bands = ["B02", "B03", "B04", "B08"]

    logger.info(f"Task {self.request.id}: Stacking and cropping capture {capture_id} (force={force})")

    try:
        import json
        from pathlib import Path

        import numpy as np

        from earthgazer.processing.retrieval import ensure_processed_image_available
        from earthgazer.processing.tracking import register_processed_image
        from earthgazer.processing.upload import upload_processed_image_to_bucket

        # Convert bounds to dict for database storage
        bounds_dict = None
        if bounds:
            bounds_dict = {"min_lon": bounds[0], "min_lat": bounds[1], "max_lon": bounds[2], "max_lat": bounds[3]}

        # Check if already processed
        existing_path = ensure_processed_image_available(
            capture_id=capture_id, image_type="stacked", bands=bands, bounds=bounds_dict, force=force
        )

        if existing_path:
            logger.info(f"Task {self.request.id}: Using cached stacked data: {existing_path}")
            # Load cached file to get shape
            data = np.load(existing_path, allow_pickle=True)
            stacked = data["stacked"]
            return {"capture_id": capture_id, "bands": bands, "shape": stacked.shape, "output_path": existing_path, "cached": True}

        # Process from scratch
        scene_folder = f"data/raw/{capture_id}/"

        # Load and stack bands
        stacked, meta = preprocessing.load_and_stack_bands(scene_folder, bands)

        # Crop if bounds provided
        if bounds:
            stacked, meta = preprocessing.crop_and_normalize(stacked, meta, bounds)

        # Save to persistent location
        output_dir = Path(f"data/features/{capture_id}")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / "stacked.npz")

        # Serialize metadata properly for npz storage
        meta_serialized = {
            "driver": meta.get("driver", "GTiff"),
            "dtype": str(meta.get("dtype", "float32")),
            "width": meta.get("width"),
            "height": meta.get("height"),
            "count": meta.get("count", 1),
            "crs": meta["crs"].to_string() if meta.get("crs") else None,
            "transform": json.dumps(list(meta["transform"])) if meta.get("transform") else None,
            "nodata": meta.get("nodata"),
        }
        np.savez_compressed(output_path, stacked=stacked, meta_json=json.dumps(meta_serialized))

        logger.info(f"Task {self.request.id}: Stacked shape {stacked.shape}, saved to {output_path}")

        # Upload to GCloud
        gcloud_path = None
        try:
            gcloud_path = upload_processed_image_to_bucket(local_path=output_path, capture_id=capture_id, image_type="stacked")
            logger.info(f"Task {self.request.id}: Uploaded to {gcloud_path}")
        except Exception as e:
            logger.warning(f"Task {self.request.id}: Failed to upload to GCloud: {e}")

        # Register in database
        try:
            register_processed_image(
                capture_id=capture_id,
                image_type="stacked",
                local_path=output_path,
                gcloud_path=gcloud_path,
                bands_used=bands,
                bounds_used=bounds_dict,
            )
            logger.info(f"Task {self.request.id}: Registered in database")
        except Exception as e:
            logger.warning(f"Task {self.request.id}: Failed to register in database: {e}")

        return {
            "capture_id": capture_id,
            "bands": bands,
            "shape": stacked.shape,
            "output_path": output_path,
            "gcloud_path": gcloud_path,
            "cached": False,
        }

    except Exception as e:
        logger.error(f"Task {self.request.id}: Error stacking/cropping: {e}")
        raise


@app.task(bind=True, name="earthgazer.tasks.compute_ndvi_task", max_retries=3)
def compute_ndvi_task(
    self: Task, capture_id: int, bands: list[str] = None, bounds: tuple[float, float, float, float] = None, force: bool = False
) -> str:
    """
    Celery task: Compute NDVI for a capture.

    Args:
        capture_id: CaptureData ID to process
        bands: List of band identifiers (default: ["B02", "B03", "B04", "B08"])
        bounds: Geographic bounds (for cache matching)
        force: Force reprocessing even if output exists

    Returns:
        Path to saved NDVI GeoTIFF
    """
    if bands is None:
        bands = ["B02", "B03", "B04", "B08"]

    logger.info(f"Task {self.request.id}: Computing NDVI for capture {capture_id} (force={force})")

    try:
        import json
        from pathlib import Path

        import numpy as np
        from rasterio.crs import CRS
        from rasterio.transform import Affine

        from earthgazer.processing.retrieval import ensure_processed_image_available
        from earthgazer.processing.tracking import register_processed_image
        from earthgazer.processing.upload import upload_processed_image_to_bucket

        # Convert bounds to dict for database storage
        bounds_dict = None
        if bounds:
            bounds_dict = {"min_lon": bounds[0], "min_lat": bounds[1], "max_lon": bounds[2], "max_lat": bounds[3]}

        # Check if already processed
        existing_path = ensure_processed_image_available(
            capture_id=capture_id, image_type="ndvi", bands=bands, bounds=bounds_dict, force=force
        )

        if existing_path:
            logger.info(f"Task {self.request.id}: Using cached NDVI: {existing_path}")
            return existing_path

        # Load stacked data (check both new and old paths for backward compatibility)
        stacked_path = f"data/features/{capture_id}/stacked.npz"
        if not Path(stacked_path).exists():
            # Fallback to old path
            stacked_path = f"data/processed/stacked_{capture_id}.npz"

        data = np.load(stacked_path, allow_pickle=True)
        stacked = data["stacked"]

        # Reconstruct metadata from JSON
        meta_json = json.loads(str(data["meta_json"]))
        meta = {
            "driver": meta_json.get("driver", "GTiff"),
            "dtype": meta_json.get("dtype", "float32"),
            "width": meta_json.get("width"),
            "height": meta_json.get("height"),
            "count": 1,  # NDVI is single band
            "crs": CRS.from_string(meta_json["crs"]) if meta_json.get("crs") else None,
            "transform": Affine(*json.loads(meta_json["transform"])[:6]) if meta_json.get("transform") else None,
            "nodata": meta_json.get("nodata"),
        }

        # Compute NDVI
        ndvi = features.compute_ndvi_from_stack(stacked, bands)

        # Save to new persistent location
        output_dir = Path(f"data/features/{capture_id}")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / "ndvi.tif")

        io.save_raster(output_path, ndvi, meta)

        logger.info(f"Task {self.request.id}: NDVI saved to {output_path}")

        # Upload to GCloud
        gcloud_path = None
        try:
            gcloud_path = upload_processed_image_to_bucket(local_path=output_path, capture_id=capture_id, image_type="ndvi")
            logger.info(f"Task {self.request.id}: Uploaded to {gcloud_path}")
        except Exception as e:
            logger.warning(f"Task {self.request.id}: Failed to upload to GCloud: {e}")

        # Register in database
        try:
            register_processed_image(
                capture_id=capture_id,
                image_type="ndvi",
                local_path=output_path,
                gcloud_path=gcloud_path,
                bands_used=bands,
                bounds_used=bounds_dict,
            )
            logger.info(f"Task {self.request.id}: Registered in database")
        except Exception as e:
            logger.warning(f"Task {self.request.id}: Failed to register in database: {e}")

        return output_path

    except Exception as e:
        logger.error(f"Task {self.request.id}: Error computing NDVI: {e}")
        raise


@app.task(bind=True, name="earthgazer.tasks.generate_rgb_task", max_retries=3)
def generate_rgb_task(
    self: Task, capture_id: int, bands: list[str] = None, bounds: tuple[float, float, float, float] = None, force: bool = False
) -> str:
    """
    Celery task: Generate RGB composite for a capture.

    Args:
        capture_id: CaptureData ID to process
        bands: List of band identifiers (default: ["B02", "B03", "B04", "B08"])
        bounds: Geographic bounds (for cache matching)
        force: Force reprocessing even if output exists

    Returns:
        Path to saved RGB GeoTIFF
    """
    if bands is None:
        bands = ["B02", "B03", "B04", "B08"]

    logger.info(f"Task {self.request.id}: Generating RGB for capture {capture_id} (force={force})")

    try:
        import json
        from pathlib import Path

        import numpy as np
        from rasterio.crs import CRS
        from rasterio.transform import Affine

        from earthgazer.processing.retrieval import ensure_processed_image_available
        from earthgazer.processing.tracking import register_processed_image
        from earthgazer.processing.upload import upload_processed_image_to_bucket

        # Convert bounds to dict for database storage
        bounds_dict = None
        if bounds:
            bounds_dict = {"min_lon": bounds[0], "min_lat": bounds[1], "max_lon": bounds[2], "max_lat": bounds[3]}

        # Check if already processed
        existing_path = ensure_processed_image_available(
            capture_id=capture_id, image_type="rgb", bands=bands, bounds=bounds_dict, force=force
        )

        if existing_path:
            logger.info(f"Task {self.request.id}: Using cached RGB: {existing_path}")
            return existing_path

        # Load stacked data (check both new and old paths for backward compatibility)
        stacked_path = f"data/features/{capture_id}/stacked.npz"
        if not Path(stacked_path).exists():
            # Fallback to old path
            stacked_path = f"data/processed/stacked_{capture_id}.npz"

        data = np.load(stacked_path, allow_pickle=True)
        stacked = data["stacked"]

        # Reconstruct metadata from JSON
        meta_json = json.loads(str(data["meta_json"]))
        meta = {
            "driver": meta_json.get("driver", "GTiff"),
            "dtype": meta_json.get("dtype", "float32"),
            "width": meta_json.get("width"),
            "height": meta_json.get("height"),
            "count": 3,  # RGB is 3 bands
            "crs": CRS.from_string(meta_json["crs"]) if meta_json.get("crs") else None,
            "transform": Affine(*json.loads(meta_json["transform"])[:6]) if meta_json.get("transform") else None,
            "nodata": meta_json.get("nodata"),
        }

        # Generate RGB
        rgb = features.create_rgb_from_stack(stacked, bands)

        # Save to new persistent location
        output_dir = Path(f"data/features/{capture_id}")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / "rgb.tif")

        io.save_rgb(output_path, rgb, meta)

        logger.info(f"Task {self.request.id}: RGB saved to {output_path}")

        # Upload to GCloud
        gcloud_path = None
        try:
            gcloud_path = upload_processed_image_to_bucket(local_path=output_path, capture_id=capture_id, image_type="rgb")
            logger.info(f"Task {self.request.id}: Uploaded to {gcloud_path}")
        except Exception as e:
            logger.warning(f"Task {self.request.id}: Failed to upload to GCloud: {e}")

        # Register in database
        try:
            register_processed_image(
                capture_id=capture_id,
                image_type="rgb",
                local_path=output_path,
                gcloud_path=gcloud_path,
                bands_used=bands,
                bounds_used=bounds_dict,
            )
            logger.info(f"Task {self.request.id}: Registered in database")
        except Exception as e:
            logger.warning(f"Task {self.request.id}: Failed to register in database: {e}")

        return output_path

    except Exception as e:
        logger.error(f"Task {self.request.id}: Error generating RGB: {e}")
        raise


@app.task(bind=True, name="earthgazer.tasks.temporal_analysis_task", max_retries=3)
def temporal_analysis_task(self: Task, ndvi_files_pattern: str = "data/features/ndvi_*.tif") -> dict:
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
        df = analysis.compute_ndvi_time_series(settings, ndvi_files_pattern, "ndvi_over_time.png")

        # Compute trend map
        slopes = analysis.compute_ndvi_trend_map(settings, ndvi_files_pattern, "ndvi_trend_map.png")

        logger.info(f"Task {self.request.id}: Temporal analysis complete")

        return {"time_series_plot": "ndvi_over_time.png", "trend_map_plot": "ndvi_trend_map.png", "num_records": len(df)}

    except Exception as e:
        logger.error(f"Task {self.request.id}: Error in temporal analysis: {e}")
        raise
