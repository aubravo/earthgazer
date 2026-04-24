"""
Upload and download module for processed satellite images to/from Google Cloud Storage.
"""

import logging
from pathlib import Path
from typing import Optional

from google.cloud import storage
from google.oauth2 import service_account

from earthgazer.settings import EarthGazerSettings

logger = logging.getLogger(__name__)


def get_gcs_client(
    settings: Optional[EarthGazerSettings] = None
) -> tuple[storage.Client, str]:
    """
    Get Google Cloud Storage client and bucket name from settings.

    Args:
        settings: EarthGazer settings instance (creates new if None)

    Returns:
        Tuple of (storage.Client, bucket_name)
    """
    if settings is None:
        settings = EarthGazerSettings()

    # Validate service account configuration
    if not settings.gcloud.service_account:
        raise ValueError("GCloud service account is not configured")

    if isinstance(settings.gcloud.service_account, str):
        raise ValueError(
            "GCloud service account is still a string. "
            "Check that EARTHGAZER__GCLOUD__SERVICE_ACCOUNT is properly base64-encoded JSON."
        )

    if not isinstance(settings.gcloud.service_account, dict):
        raise ValueError(
            f"GCloud service account must be a dict, got {type(settings.gcloud.service_account)}"
        )

    # Create service account credentials
    service_account_creds = service_account.Credentials.from_service_account_info(
        settings.gcloud.service_account,
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    storage_client = storage.Client(credentials=service_account_creds)
    bucket_name = settings.gcloud.bucket_name

    return storage_client, bucket_name


def upload_processed_image_to_bucket(
    local_path: str,
    capture_id: int,
    image_type: str,
    bucket_name: Optional[str] = None,
    settings: Optional[EarthGazerSettings] = None
) -> str:
    """
    Upload processed image to GCloud bucket.

    Args:
        local_path: Path to local file (relative or absolute)
        capture_id: Capture ID
        image_type: Image type ('ndvi', 'rgb', or 'stacked')
        bucket_name: Optional bucket name override
        settings: Optional settings instance

    Returns:
        GCS path (gs://bucket/processed_data/{capture_id}/{filename})

    Raises:
        FileNotFoundError: If local file doesn't exist
        ValueError: If upload fails
    """
    # Verify file exists
    local_file = Path(local_path)
    if not local_file.exists():
        raise FileNotFoundError(f"Local file not found: {local_path}")

    # Get GCS client and bucket
    storage_client, default_bucket_name = get_gcs_client(settings)
    bucket_name = bucket_name or default_bucket_name
    bucket = storage_client.bucket(bucket_name)

    # Determine file extension
    extension = local_file.suffix  # e.g., .tif, .npz

    # Construct GCS blob name
    blob_name = f"processed_data/{capture_id}/{image_type}{extension}"

    logger.info(f"Uploading {local_path} to gs://{bucket_name}/{blob_name}")

    try:
        # Upload file
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(local_file))

        gcs_path = f"gs://{bucket_name}/{blob_name}"
        logger.info(f"Successfully uploaded to {gcs_path}")
        return gcs_path

    except Exception as e:
        logger.error(f"Failed to upload {local_path}: {e}")
        raise ValueError(f"Upload failed: {e}") from e


def download_processed_image_from_bucket(
    capture_id: int,
    image_type: str,
    local_path: str,
    bucket_name: Optional[str] = None,
    settings: Optional[EarthGazerSettings] = None
) -> bool:
    """
    Download processed image from GCloud bucket.

    Args:
        capture_id: Capture ID
        image_type: Image type ('ndvi', 'rgb', or 'stacked')
        local_path: Destination path for downloaded file
        bucket_name: Optional bucket name override
        settings: Optional settings instance

    Returns:
        True if download successful, False otherwise
    """
    # Get GCS client and bucket
    storage_client, default_bucket_name = get_gcs_client(settings)
    bucket_name = bucket_name or default_bucket_name
    bucket = storage_client.bucket(bucket_name)

    # Determine file extension from local path
    extension = Path(local_path).suffix

    # Construct GCS blob name
    blob_name = f"processed_data/{capture_id}/{image_type}{extension}"

    logger.info(f"Downloading gs://{bucket_name}/{blob_name} to {local_path}")

    try:
        # Check if blob exists
        blob = bucket.blob(blob_name)
        if not blob.exists():
            logger.warning(f"Blob not found in bucket: {blob_name}")
            return False

        # Create parent directory if it doesn't exist
        local_file = Path(local_path)
        local_file.parent.mkdir(parents=True, exist_ok=True)

        # Download file
        blob.download_to_filename(str(local_file))

        logger.info(f"Successfully downloaded to {local_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to download {blob_name}: {e}")
        return False


def check_processed_image_exists_in_bucket(
    capture_id: int,
    image_type: str,
    extension: str = ".tif",
    bucket_name: Optional[str] = None,
    settings: Optional[EarthGazerSettings] = None
) -> bool:
    """
    Check if processed image exists in GCloud bucket.

    Args:
        capture_id: Capture ID
        image_type: Image type ('ndvi', 'rgb', or 'stacked')
        extension: File extension (e.g., '.tif', '.npz')
        bucket_name: Optional bucket name override
        settings: Optional settings instance

    Returns:
        True if blob exists, False otherwise
    """
    # Get GCS client and bucket
    storage_client, default_bucket_name = get_gcs_client(settings)
    bucket_name = bucket_name or default_bucket_name
    bucket = storage_client.bucket(bucket_name)

    # Construct GCS blob name
    blob_name = f"processed_data/{capture_id}/{image_type}{extension}"

    logger.debug(f"Checking if gs://{bucket_name}/{blob_name} exists")

    try:
        blob = bucket.blob(blob_name)
        exists = blob.exists()
        logger.debug(f"Blob exists: {exists}")
        return exists

    except Exception as e:
        logger.error(f"Error checking blob existence: {e}")
        return False


def get_gcs_url_for_processed_image(
    capture_id: int,
    image_type: str,
    extension: str = ".tif",
    bucket_name: Optional[str] = None,
    settings: Optional[EarthGazerSettings] = None
) -> str:
    """
    Get GCS URL for a processed image without checking if it exists.

    Args:
        capture_id: Capture ID
        image_type: Image type ('ndvi', 'rgb', or 'stacked')
        extension: File extension (e.g., '.tif', '.npz')
        bucket_name: Optional bucket name override
        settings: Optional settings instance

    Returns:
        GCS URL (gs://bucket/processed_data/{capture_id}/{image_type}{extension})
    """
    if settings is None:
        settings = EarthGazerSettings()

    bucket_name = bucket_name or settings.gcloud.bucket_name
    blob_name = f"processed_data/{capture_id}/{image_type}{extension}"

    return f"gs://{bucket_name}/{blob_name}"
