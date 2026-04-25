"""
Database tracking for processed satellite images.

This module provides functions to register, query, and verify processed images
in the database, enabling caching and smart reprocessing.
"""

import hashlib
import json
import logging
import os
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from earthgazer.database.definitions import ImageType
from earthgazer.database.definitions import ProcessedImage
from earthgazer.database.session import get_session

logger = logging.getLogger(__name__)


def _get_image_type_enum(image_type: str) -> ImageType:
    """Convert string image type to ImageType enum."""
    type_map = {
        "ndvi": ImageType.NDVI,
        "rgb": ImageType.RGB,
        "stacked": ImageType.STACKED,
    }
    if image_type.lower() not in type_map:
        raise ValueError(f"Invalid image type: {image_type}. Must be one of: ndvi, rgb, stacked")
    return type_map[image_type.lower()]


def calculate_file_hash(file_path: str) -> str:
    """
    Calculate SHA256 hash of a file.

    Args:
        file_path: Path to file

    Returns:
        Hex string of SHA256 hash
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in chunks to handle large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def register_processed_image(
    capture_id: int,
    image_type: str,
    local_path: str,
    gcloud_path: str | None = None,
    bands_used: list | None = None,
    bounds_used: dict | None = None,
    file_size: int | None = None,
    file_hash: str | None = None,
    processing_version: str = "1.0",
) -> ProcessedImage:
    """
    Register a processed image in the database.

    Creates a new ProcessedImage record or updates existing one if found.

    Args:
        capture_id: Capture ID
        image_type: Type of image ('ndvi', 'rgb', or 'stacked')
        local_path: Relative path from /app/data/ or absolute path
        gcloud_path: GCS bucket path (optional)
        bands_used: List of bands used (e.g., ['B02', 'B03', 'B04', 'B08'])
        bounds_used: Dict with bounds (e.g., {'min_lon': ..., 'min_lat': ..., ...})
        file_size: File size in bytes (calculated if not provided)
        file_hash: SHA256 hash (calculated if not provided)
        processing_version: Version of processing pipeline

    Returns:
        ProcessedImage record
    """
    session: Session = next(get_session())

    # Calculate file metadata if not provided
    if os.path.exists(local_path):
        if file_size is None:
            file_size = os.path.getsize(local_path)
        if file_hash is None:
            file_hash = calculate_file_hash(local_path)

    # Serialize bands and bounds to JSON
    bands_json = json.dumps(bands_used) if bands_used else None
    bounds_json = json.dumps(bounds_used) if bounds_used else None

    # Convert string to enum
    image_type_enum = _get_image_type_enum(image_type)

    # Check if record already exists
    stmt = select(ProcessedImage).where(
        ProcessedImage.capture_id == capture_id,
        ProcessedImage.image_type == image_type_enum,
        ProcessedImage.bands_used == bands_json,
        ProcessedImage.bounds_used == bounds_json,
    )
    existing = session.execute(stmt).scalar_one_or_none()

    if existing:
        # Update existing record
        logger.info(f"Updating existing ProcessedImage record for capture {capture_id}, type {image_type}")
        existing.local_path = local_path
        existing.gcloud_path = gcloud_path or existing.gcloud_path
        existing.file_size_bytes = file_size
        existing.file_hash = file_hash
        existing.local_available = os.path.exists(local_path)
        existing.gcloud_available = gcloud_path is not None
        existing.processing_version = processing_version
        existing.last_verified = datetime.now()
        session.commit()
        session.refresh(existing)
        return existing
    else:
        # Create new record
        logger.info(f"Creating new ProcessedImage record for capture {capture_id}, type {image_type}")
        processed_image = ProcessedImage(
            capture_id=capture_id,
            image_type=image_type_enum,
            local_path=local_path,
            gcloud_path=gcloud_path,
            bands_used=bands_json,
            bounds_used=bounds_json,
            processing_version=processing_version,
            file_size_bytes=file_size,
            file_hash=file_hash,
            local_available=os.path.exists(local_path),
            gcloud_available=gcloud_path is not None,
        )
        session.add(processed_image)
        session.commit()
        session.refresh(processed_image)
        return processed_image


def get_processed_image(capture_id: int, image_type: str, bands: list | None = None, bounds: dict | None = None) -> ProcessedImage | None:
    """
    Get processed image record matching parameters.

    Args:
        capture_id: Capture ID
        image_type: Type of image ('ndvi', 'rgb', or 'stacked')
        bands: List of bands used (for matching)
        bounds: Dict with bounds (for matching)

    Returns:
        ProcessedImage record if found, None otherwise
    """
    session: Session = next(get_session())

    # Convert string to enum
    image_type_enum = _get_image_type_enum(image_type)

    # Serialize bands and bounds to JSON for comparison
    bands_json = json.dumps(bands) if bands else None
    bounds_json = json.dumps(bounds) if bounds else None

    # Query for matching record
    stmt = select(ProcessedImage).where(ProcessedImage.capture_id == capture_id, ProcessedImage.image_type == image_type_enum)

    # Add bands filter if provided
    if bands_json:
        stmt = stmt.where(ProcessedImage.bands_used == bands_json)

    # Add bounds filter if provided (or both None)
    if bounds_json:
        stmt = stmt.where(ProcessedImage.bounds_used == bounds_json)
    else:
        # If no bounds specified, only match records with no bounds
        stmt = stmt.where(ProcessedImage.bounds_used == None)

    result = session.execute(stmt).scalar_one_or_none()
    return result


def verify_local_file_exists(processed_image: ProcessedImage) -> bool:
    """
    Check if local file exists and matches hash.

    Updates local_available field and last_verified timestamp.

    Args:
        processed_image: ProcessedImage record

    Returns:
        True if file exists and hash matches, False otherwise
    """
    session: Session = next(get_session())

    local_path = processed_image.local_path
    exists = os.path.exists(local_path)

    if exists and processed_image.file_hash:
        # Verify hash matches
        current_hash = calculate_file_hash(local_path)
        hash_matches = current_hash == processed_image.file_hash
        logger.debug(f"File {local_path} hash check: {hash_matches}")
        exists = exists and hash_matches

    # Update record
    processed_image.local_available = exists
    processed_image.last_verified = datetime.now()
    session.commit()

    return exists


def mark_uploaded_to_gcloud(processed_image_id: int, gcloud_path: str) -> bool:
    """
    Mark image as uploaded to GCloud.

    Args:
        processed_image_id: ProcessedImage record ID
        gcloud_path: GCS bucket path

    Returns:
        True if successful, False otherwise
    """
    session: Session = next(get_session())

    stmt = select(ProcessedImage).where(ProcessedImage.id == processed_image_id)
    processed_image = session.execute(stmt).scalar_one_or_none()

    if not processed_image:
        logger.error(f"ProcessedImage with ID {processed_image_id} not found")
        return False

    processed_image.gcloud_path = gcloud_path
    processed_image.gcloud_available = True
    processed_image.uploaded_at = datetime.now()
    session.commit()

    logger.info(f"Marked ProcessedImage {processed_image_id} as uploaded to {gcloud_path}")
    return True


def get_all_processed_for_capture(capture_id: int) -> list[ProcessedImage]:
    """
    Get all processed images for a given capture.

    Args:
        capture_id: Capture ID

    Returns:
        List of ProcessedImage records
    """
    session: Session = next(get_session())

    stmt = select(ProcessedImage).where(ProcessedImage.capture_id == capture_id)
    results = session.execute(stmt).scalars().all()
    return list(results)


def cleanup_missing_local_files() -> int:
    """
    Update local_available for all records where files are missing.

    Returns:
        Number of records updated
    """
    session: Session = next(get_session())

    stmt = select(ProcessedImage).where(ProcessedImage.local_available)
    all_records = session.execute(stmt).scalars().all()

    updated_count = 0
    for record in all_records:
        if not os.path.exists(record.local_path):
            record.local_available = False
            record.last_verified = datetime.now()
            updated_count += 1

    if updated_count > 0:
        session.commit()
        logger.info(f"Marked {updated_count} files as locally unavailable")

    return updated_count
