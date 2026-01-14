"""
Image discovery module for querying satellite imagery from BigQuery.
"""

import json
import logging
from pathlib import Path
from typing import List

from google.cloud import bigquery
from google.oauth2 import service_account
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from earthgazer.database.definitions import Location, CaptureData
from earthgazer.settings import EarthGazerSettings

logger = logging.getLogger(__name__)


def load_platform_definitions() -> dict:
    """Load platform definitions from JSON file."""
    platforms_path = Path("earthgazer/definitions/platforms.json")
    with platforms_path.open() as f:
        return json.load(f)


def check_for_new_images(
    settings: EarthGazerSettings,
    service_account_creds: service_account.Credentials,
    locations: List[Location] = None
) -> List[int]:
    """
    Query BigQuery for new satellite imagery and store in database.

    Args:
        settings: EarthGazer settings instance
        service_account_creds: Google Cloud service account credentials
        locations: List of Location objects to query (if None, queries all active locations)

    Returns:
        List of CaptureData IDs that were newly added to the database
    """
    logger.info("Starting image discovery process")

    # Load definitions
    platforms = load_platform_definitions()

    # Initialize database connection
    engine = create_engine(settings.database.url, echo=False)

    # Get locations if not provided
    if locations is None:
        with Session(engine) as session:
            locations = session.query(Location).where(Location.active).all()

    logger.info(f"Loaded {len(locations)} locations from the database")

    # Build queries
    queries = []
    for location in locations:
        logger.info(f"Processing location: {location.id} - {location.name} ({location.latitude}, {location.longitude})")

        for platform_name, platform in platforms.items():
            logger.debug(f"Building query for platform: {platform_name}")

            query = f"""SELECT
                {platform['main_id']} AS main_id,
                {platform['secondary_id']} AS secondary_id,
                {platform['mission_id']} AS mission_id,
                {platform['sensing_time']} AS sensing_time,
                {platform['cloud_cover']} AS cloud_cover,
                {platform['north_lat']} AS north_lat,
                {platform['south_lat']} AS south_lat,
                {platform['west_lon']} AS west_lon,
                {platform['east_lon']} AS east_lon,
                {platform['base_url']} AS base_url,
                {platform['mgrs_tile']} AS mgrs_tile,
                {platform['radiometric_measure']} AS radiometric_measure,
                {platform['athmospheric_reference_level']} AS athmospheric_reference_level,
                {platform['wrs_path']} AS wrs_path,
                {platform['wrs_row']} AS wrs_row,
                {platform['data_type']} AS data_type
                FROM {platform['bigquery_path']}
                WHERE
                {platform['sensing_time']} >= '{location.from_date}' AND
                {platform['sensing_time']} <= '{location.to_date}' AND
                {platform['north_lat']} >= {location.latitude} AND
                {platform['south_lat']} <= {location.latitude} AND
                {platform['west_lon']} <= {location.longitude} AND
                {platform['east_lon']} >= {location.longitude} AND
                {platform['base_url']} IS NOT NULL
            """
            queries.append(query)

    logger.info(f"Total queries generated: {len(queries)}")

    # Execute queries and store results
    bigquery_client = bigquery.Client(credentials=service_account_creds)
    new_capture_ids = []

    with Session(engine) as session:
        for query in queries:
            try:
                for result in bigquery_client.query(query):
                    # Check if capture already exists
                    existing = session.query(CaptureData).where(
                        CaptureData.main_id == result.main_id,
                        CaptureData.mission_id == result.mission_id
                    ).scalar()

                    if existing:
                        logger.debug(f"CaptureData {result.main_id} ({result.mission_id}) already exists")
                        continue

                    # Create new capture data entry
                    capture = CaptureData(
                        main_id=result.main_id,
                        secondary_id=result.secondary_id,
                        mission_id=result.mission_id,
                        sensing_time=result.sensing_time,
                        north_lat=result.north_lat,
                        south_lat=result.south_lat,
                        west_lon=result.west_lon,
                        east_lon=result.east_lon,
                        base_url=result.base_url,
                        cloud_cover=result.cloud_cover,
                        radiometric_measure=result.radiometric_measure,
                        athmospheric_reference_level=result.athmospheric_reference_level,
                        mgrs_tile=result.mgrs_tile,
                        wrs_path=result.wrs_path,
                        wrs_row=result.wrs_row,
                        data_type=result.data_type
                    )
                    capture.add(session)
                    session.flush()

                    new_capture_ids.append(capture.id)
                    logger.info(f"Added new capture: {capture.main_id} (ID: {capture.id})")

            except Exception as e:
                logger.error(f"Error executing query: {e}")
                continue

    logger.info(f"Discovery complete. Added {len(new_capture_ids)} new captures")
    return new_capture_ids
