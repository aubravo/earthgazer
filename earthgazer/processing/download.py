"""
Download module for retrieving satellite imagery from Google Cloud Storage.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from google.cloud import storage
from google.oauth2 import service_account
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session

from earthgazer.database.definitions import CaptureData
from earthgazer.settings import EarthGazerSettings

logger = logging.getLogger(__name__)


def backup_capture_to_project_bucket(
    settings: EarthGazerSettings,
    service_account_creds: service_account.Credentials,
    capture_ids: List[int] = None
) -> List[int]:
    """
    Back up raw imagery from public GCS buckets to project bucket.

    Args:
        settings: EarthGazer settings instance
        service_account_creds: Google Cloud service account credentials
        capture_ids: List of CaptureData IDs to backup (if None, backs up all un-backed-up captures)

    Returns:
        List of CaptureData IDs that were successfully backed up
    """
    logger.info("Starting capture backup process")

    gcs_url_parser = re.compile(r"gs://(?P<bucket_name>.*?)/(?P<blobs_path_name>.*)")
    blob_finder = re.compile(
        r"^.*?(?:tiles.*?IMG_DATA.*?|/LC0[0-9]_.*?)_(?P<file_id>B[0-9A]{1,2}|MTL)\.(?P<format>TIF|jp2|txt)$"
    )

    storage_client = storage.Client(credentials=service_account_creds)
    destination_bucket = storage_client.bucket(settings.gcloud.bucket_name)

    engine = create_engine(settings.database.url, echo=False)
    backed_up_ids = []

    with Session(engine) as session:
        # Build query for captures to backup
        query = session.query(CaptureData).where(
            CaptureData.backed_up == False,
            or_(
                CaptureData.mission_id.like("%LANDSAT_8%"),
                CaptureData.mission_id.like("SENTINEL-2%")
            )
        )

        # Filter by specific IDs if provided
        if capture_ids is not None:
            query = query.where(CaptureData.id.in_(capture_ids))

        captures = query.all()
        logger.info(f"Found {len(captures)} captures to backup")

        for data in captures:
            try:
                logger.info(f"Backing up capture ID {data.id}: {data.main_id}")

                parsed_base_url = gcs_url_parser.search(data.base_url).groupdict()
                source_bucket = storage_client.bucket(parsed_base_url["bucket_name"])

                # Copy all relevant band files
                blobs_copied = 0
                for blob in storage_client.list_blobs(source_bucket, prefix=parsed_base_url["blobs_path_name"]):
                    if selected_blob := blob_finder.search(blob.name):
                        source_blob = blob.name
                        destination_blob = blob.name.replace(
                            parsed_base_url["blobs_path_name"],
                            f"capture_data/{data.id}",
                            1
                        )
                        blob_copy = source_bucket.copy_blob(blob, destination_bucket, destination_blob)
                        blobs_copied += 1

                        logger.debug(f"Copied {source_blob} to {blob_copy.name}")

                # Mark as backed up
                if blobs_copied > 0:
                    data.backed_up = True
                    data.backup_date = datetime.now()
                    data.backup_location = f"gs://{destination_bucket.name}/capture_data/{data.id}"
                    session.commit()
                    backed_up_ids.append(data.id)
                    logger.info(f"Successfully backed up capture ID {data.id} ({blobs_copied} files)")
                else:
                    logger.warning(f"No files found for capture ID {data.id}")

            except Exception as e:
                logger.error(f"Error backing up capture ID {data.id}: {e}")
                continue

    logger.info(f"Backup complete. Backed up {len(backed_up_ids)} captures")
    return backed_up_ids


def download_capture_bands(
    settings: EarthGazerSettings,
    service_account_creds: service_account.Credentials,
    capture_id: int,
    bands: List[str]
) -> Optional[str]:
    """
    Download specific bands for a capture from project bucket to local storage.

    Args:
        settings: EarthGazer settings instance
        service_account_creds: Google Cloud service account credentials
        capture_id: CaptureData ID to download
        bands: List of band identifiers (e.g., ["B02", "B03", "B04", "B08"])

    Returns:
        Path to the downloaded scene folder, or None if download failed
    """
    logger.info(f"Downloading bands {bands} for capture ID {capture_id}")

    storage_client = storage.Client(credentials=service_account_creds)
    bucket = storage_client.bucket(settings.gcloud.bucket_name)

    engine = create_engine(settings.database.url, echo=False)

    with Session(engine) as session:
        data = session.query(CaptureData).where(CaptureData.id == capture_id).first()

        if not data:
            logger.error(f"No capture data found for ID {capture_id}")
            return None

        if not data.backed_up:
            logger.error(f"Capture data ID {capture_id} has not been backed up yet")
            return None

        backup_blob_base_path = f"capture_data/{capture_id}/"
        logger.debug(f"Searching for files in {settings.gcloud.bucket_name}/{backup_blob_base_path}")

        # Create local directory
        file_path = Path(f"./data/raw/{capture_id}/")
        file_path.mkdir(parents=True, exist_ok=True)

        downloaded_files = 0
        for blob in storage_client.list_blobs(bucket, prefix=backup_blob_base_path):
            # Check if blob matches requested bands
            if any(blob.name.endswith(f"_{band}.TIF") or blob.name.endswith(f"_{band}.jp2") for band in bands):
                file_extension = blob.name.split(".")[-1]
                detected_band = re.search(r"_(B[0-9A]{1,2}|MTL)\.", blob.name)

                if detected_band:
                    band_id = detected_band.group(1)
                    local_file_path = file_path / f"{band_id}.{file_extension}"

                    logger.debug(f"Downloading band {band_id} from {blob.name}")
                    blob.download_to_filename(local_file_path)
                    downloaded_files += 1

        if downloaded_files > 0:
            logger.info(f"Downloaded {downloaded_files} bands for capture ID {capture_id}")
            return str(file_path)
        else:
            logger.warning(f"No bands downloaded for capture ID {capture_id}")
            return None
