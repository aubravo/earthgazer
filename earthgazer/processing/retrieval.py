"""
Smart retrieval module for processed satellite images.

This module implements intelligent retrieval logic that:
1. Checks database for existing processed images
2. Verifies local file existence
3. Downloads from GCloud if not available locally
4. Returns None if processing is needed
"""

import logging
from pathlib import Path

from earthgazer.processing.tracking import get_processed_image
from earthgazer.processing.tracking import verify_local_file_exists
from earthgazer.processing.upload import download_processed_image_from_bucket
from earthgazer.settings import EarthGazerSettings

logger = logging.getLogger(__name__)


def ensure_processed_image_available(
    capture_id: int,
    image_type: str,
    bands: list | None = None,
    bounds: dict | None = None,
    force: bool = False,
    settings: EarthGazerSettings | None = None,
) -> str | None:
    """
    Ensure processed image is available locally.

    This function implements the smart retrieval strategy:
    1. If force=True: return None (trigger reprocessing)
    2. Check database for matching processed image
    3. If found and local file exists: return path
    4. If found but local file missing: download from GCloud
    5. If not found: return None (trigger processing)

    Args:
        capture_id: Capture ID
        image_type: Image type ('ndvi', 'rgb', or 'stacked')
        bands: Bands used in processing (for matching)
        bounds: Bounds used in processing (for matching)
        force: Force reprocessing even if exists
        settings: Optional settings instance

    Returns:
        Local path if available, None if needs processing
    """
    # If force=True, skip cache and trigger reprocessing
    if force:
        logger.info(f"Force reprocessing requested for capture {capture_id}, type {image_type}")
        return None

    # Check database for matching processed image
    logger.debug(f"Checking database for processed image: capture={capture_id}, type={image_type}")
    processed_image = get_processed_image(capture_id=capture_id, image_type=image_type, bands=bands, bounds=bounds)

    if not processed_image:
        logger.info(f"No matching processed image found for capture {capture_id}, type {image_type}")
        return None

    logger.debug(f"Found ProcessedImage record: ID={processed_image.id}, local_path={processed_image.local_path}")

    # Verify local file exists
    local_available = verify_local_file_exists(processed_image)

    if local_available:
        logger.info(f"Using cached processed image: {processed_image.local_path}")
        return processed_image.local_path

    # Local file missing - try to download from GCloud
    if processed_image.gcloud_available and processed_image.gcloud_path:
        logger.info(f"Local file missing, attempting download from GCloud: {processed_image.gcloud_path}")

        # Create parent directory if needed
        local_path = Path(processed_image.local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # Attempt download
        success = download_processed_image_from_bucket(
            capture_id=capture_id, image_type=image_type, local_path=str(local_path), settings=settings
        )

        if success:
            # Verify downloaded file
            local_available = verify_local_file_exists(processed_image)
            if local_available:
                logger.info(f"Successfully downloaded from GCloud: {processed_image.local_path}")
                return processed_image.local_path
            else:
                logger.warning(f"Downloaded file verification failed: {processed_image.local_path}")
                return None
        else:
            logger.warning("Failed to download from GCloud, will trigger reprocessing")
            return None

    # No GCloud backup available
    logger.info(f"No GCloud backup available for capture {capture_id}, type {image_type}")
    return None


def check_if_processing_needed(
    capture_id: int,
    image_types: list[str],
    bands: list | None = None,
    bounds: dict | None = None,
    force: bool = False,
    settings: EarthGazerSettings | None = None,
) -> dict[str, bool]:
    """
    Check which image types need processing for a capture.

    Args:
        capture_id: Capture ID
        image_types: List of image types to check (e.g., ['ndvi', 'rgb', 'stacked'])
        bands: Bands used in processing (for matching)
        bounds: Bounds used in processing (for matching)
        force: Force reprocessing even if exists
        settings: Optional settings instance

    Returns:
        Dict mapping image_type -> needs_processing (bool)
    """
    result = {}

    for image_type in image_types:
        path = ensure_processed_image_available(
            capture_id=capture_id, image_type=image_type, bands=bands, bounds=bounds, force=force, settings=settings
        )
        result[image_type] = path is None

    return result


def get_cached_image_path(capture_id: int, image_type: str, bands: list | None = None, bounds: dict | None = None) -> str | None:
    """
    Get path to cached processed image if it exists locally.

    Does NOT attempt to download from GCloud.

    Args:
        capture_id: Capture ID
        image_type: Image type ('ndvi', 'rgb', or 'stacked')
        bands: Bands used in processing (for matching)
        bounds: Bounds used in processing (for matching)

    Returns:
        Local path if available, None otherwise
    """
    processed_image = get_processed_image(capture_id=capture_id, image_type=image_type, bands=bands, bounds=bounds)

    if not processed_image:
        return None

    # Check if local file exists
    local_available = verify_local_file_exists(processed_image)

    if local_available:
        return processed_image.local_path

    return None
