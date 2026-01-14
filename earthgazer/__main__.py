import json
from pathlib import Path

from google.cloud import bigquery
from google.oauth2 import service_account
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from .database.definitions import Location, CaptureData
from .settings import EarthGazerSettings

# Load settings
SETTINGS = EarthGazerSettings()
GCLOUD_BUCKET = SETTINGS.gcloud.bucket_name

service_account_credentials = service_account.Credentials.from_service_account_info(
    SETTINGS.gcloud.service_account, scopes=["https://www.googleapis.com/auth/cloud-platform"])

# Load definitions
PLATFORMS = json.load(Path.open("earthgazer/definitions/platforms.json"))
COMPOSITES = json.load(Path.open("earthgazer/definitions/composites.json"))
BANDS = json.load(Path.open("earthgazer/definitions/bands.json"))

# Initialize database connection
DATABASE_URL = SETTINGS.database.url
engine = create_engine(DATABASE_URL, echo=False)


with Session(engine) as session:
    LOCATIONS = session.query(Location).where(Location.active).all()


def check_for_new_images():
    print(f"Loaded {len(LOCATIONS)} locations from the database.")

    queries = []
    for location in LOCATIONS:
        print(f"Loading location: {location.id} - {location.name} ({location.latitude}, {location.longitude})")
        for platform in PLATFORMS:
            print(f"Loading platform: {platform}")
            query = f"""SELECT
                    {PLATFORMS[platform]['main_id']} AS main_id,
                    {PLATFORMS[platform]['secondary_id']} AS secondary_id,
                    {PLATFORMS[platform]['mission_id']} AS mission_id,
                    {PLATFORMS[platform]['sensing_time']} AS sensing_time,
                    {PLATFORMS[platform]['cloud_cover']} AS cloud_cover,
                    {PLATFORMS[platform]['north_lat']} AS north_lat,
                    {PLATFORMS[platform]['south_lat']} AS south_lat,
                    {PLATFORMS[platform]['west_lon']} AS west_lon,
                    {PLATFORMS[platform]['east_lon']} AS east_lon,
                    {PLATFORMS[platform]['base_url']} AS base_url,
                    {PLATFORMS[platform]['mgrs_tile']} AS mgrs_tile,
                    {PLATFORMS[platform]['radiometric_measure']} AS radiometric_measure,
                    {PLATFORMS[platform]['athmospheric_reference_level']} AS athmospheric_reference_level,
                    {PLATFORMS[platform]['wrs_path']} AS wrs_path,
                    {PLATFORMS[platform]['wrs_row']} AS wrs_row,
                    {PLATFORMS[platform]['data_type']} AS data_type
                    FROM {PLATFORMS[platform]['bigquery_path']}
                    WHERE
                    {PLATFORMS[platform]['sensing_time']} >= '{location.from_date}' AND
                    {PLATFORMS[platform]['sensing_time']} <= '{location.to_date}' AND
                    {PLATFORMS[platform]['north_lat']} >= {location.latitude} AND
                    {PLATFORMS[platform]['south_lat']} <= {location.latitude} AND
                    {PLATFORMS[platform]['west_lon']} <= {location.longitude} AND
                    {PLATFORMS[platform]['east_lon']} >= {location.longitude} AND
                    {PLATFORMS[platform]['base_url']} IS NOT NULL
            """
            print(f"Generated query for {platform}: {query}")
            queries.append(query)

    print(f"Total queries generated: {len(queries)}")

    bigquery_client = bigquery.Client(credentials=service_account_credentials)

    with Session(engine) as session:
        for query in queries:
            for result in bigquery_client.query(query):
                if session.query(CaptureData).where(CaptureData.main_id == result.main_id,CaptureData.mission_id == result.mission_id).scalar():
                    print(f"CaptureData with main_id {result.main_id} and mission_id {result.mission_id} already exists in the database.")
                    continue
                CaptureData(
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
                ).add(session)


if __name__ == "__main__":
    check_for_new_images()