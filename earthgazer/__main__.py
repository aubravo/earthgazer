import json
from datetime import datetime
from pathlib import Path
import re

from google.cloud import bigquery
from google.oauth2 import service_account
from google.cloud import storage
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session

from .database.definitions import Location, CaptureData
from .settings import EarthGazerSettings

import rasterio
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.windows import from_bounds
import numpy as np
import os, glob

import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model  import LinearRegression

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

def get_capture_data():
    gcs_url_parser = re.compile(r"gs://(?P<bucket_name>.*?)/(?P<blobs_path_name>.*)")
    blob_finder = re.compile(r"^.*?(?:tiles.*?IMG_DATA.*?|/LC0[0-9]_.*?)_(?P<file_id>B[0-9A]{1,2}|MTL)\.(?P<format>TIF|jp2|txt)$")

    storage_client = storage.Client(credentials=service_account_credentials)
    destination_bucket = storage_client.bucket(GCLOUD_BUCKET)

    with Session(engine) as session:
        for data in session.query(CaptureData).where(CaptureData.backed_up == False, or_(CaptureData.mission_id.like("%LANDSAT_8%"), CaptureData.mission_id.like("SENTINEL-2%") )):
            parsed_base_url = gcs_url_parser.search(data.base_url).groupdict()
            source_bucket = storage_client.bucket(parsed_base_url["bucket_name"])


            for blob in storage_client.list_blobs(source_bucket, prefix=parsed_base_url["blobs_path_name"]):
                if selected_blob := blob_finder.search(blob.name):
                    source_blob = blob.name
                    destination_blob = blob.name.replace(parsed_base_url["blobs_path_name"], f"capture_data/{data.id}", 1)
                    blob_copy = source_bucket.copy_blob(blob, destination_bucket, destination_blob)

                    print(f"Backed up {data.main_id} from {source_blob} to {blob_copy.name} in {destination_bucket.name}")

                    data.backed_up = True
                    data.backup_date = datetime.now()
                    data.backup_location = f"gs://{destination_bucket.name}/{blob_copy.name}"
                    session.commit()

def get_capture_data_by_id_and_bands(id:int, bands:list[str]):
    storage_client = storage.Client(credentials=service_account_credentials)
    bucket = storage_client.bucket(GCLOUD_BUCKET)

    with Session(engine) as session:
        data = session.query(CaptureData).where(CaptureData.id == id).first()
        if not data:
            print(f"No capture data found for ID {id}")
            return None

        if not data.backed_up:
            print(f"Capture data with ID {id} has not been backed up yet.")
            return None

        backup_blob_base_path = f"capture_data/{id}/"
        print(f"Searching for files in bucket {GCLOUD_BUCKET} with prefix {backup_blob_base_path}")

        files = []
        for blob in storage_client.list_blobs(bucket, prefix=backup_blob_base_path):
            if any(blob.name.endswith(f"_{band}.TIF") or blob.name.endswith(f"_{band}.jp2") for band in bands):
                file_extension = blob.name.split(".")[-1]
                detected_band = re.search(r"_(B[0-9A]{1,2}|MTL)\.", blob.name)
                print(f"Detected band: {detected_band.group(1)} in file {blob.name}")
                file_name = blob.name.split("/")[-1]
                print(f"Found file: {file_name}")
                file_path = Path(f"./data/raw/{id}/")
                file_path.mkdir(parents=True, exist_ok=True)
                blob.download_to_filename(file_path / f"{detected_band.group(1)}.{file_extension}")

def load_and_stack_bands(scene_folder, bands=["B02", "B03", "B04", "B08"]):
    """
    Load and stack Sentinel-2 JP2 bands from a folder.
    Returns a stacked array (bands, height, width) and metadata.
    """
    band_files = []
    for b in bands:
        matches = glob.glob(os.path.join(scene_folder, f"*{b}*.jp2"))
        if not matches:
            raise FileNotFoundError(f"Band {b} not found in {scene_folder}")
        band_files.append(matches[0])

    band_data = []
    ref_meta = None

    for i, path in enumerate(band_files):
        with rasterio.open(path) as src:
            band = src.read(1).astype(np.float32)

            if ref_meta is None:
                ref_meta = src.meta.copy()
                band_ref = band
            else:
                # Align band resolution if needed
                if src.shape != (ref_meta['height'], ref_meta['width']):
                    resampled = np.empty((ref_meta['height'], ref_meta['width']), dtype=np.float32)
                    reproject(
                        source=rasterio.band(src, 1),
                        destination=resampled,
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=ref_meta['transform'],
                        dst_crs=ref_meta['crs'],
                        resampling=Resampling.bilinear
                    )
                    band = resampled
            band_data.append(band)

    stacked = np.stack(band_data, axis=0)
    return stacked, ref_meta

def crop_and_normalize(image, meta, bounds):
    """
    Crop and normalize (north-up) Sentinel-2 image to a given lat/lon bounding box.
    bounds = (min_lon, min_lat, max_lon, max_lat)
    """
    # Transform lat/lon bounds to the image CRS
    if meta["crs"].to_string() != "EPSG:4326":
        target_bounds = transform_bounds("EPSG:4326", meta["crs"], *bounds)
    else:
        target_bounds = bounds

    # Derive pixel window from geographic bounds
    window = from_bounds(*target_bounds, transform=meta["transform"])
    window = window.round_offsets().round_shape()

    cropped = image[:, int(window.row_off):int(window.row_off + window.height),
                       int(window.col_off):int(window.col_off + window.width)]

    meta_cropped = meta.copy()
    meta_cropped.update({
        "height": cropped.shape[1],
        "width": cropped.shape[2],
        "transform": rasterio.windows.transform(window, meta["transform"])
    })

    # Ensure north-up orientation
    if meta_cropped["transform"].a < 0 or meta_cropped["transform"].e > 0:
        cropped = np.flipud(cropped)

    return cropped, meta_cropped

def compute_ndvi_from_stack(stacked, bands=["B02", "B03", "B04", "B08"]):
    red_idx = bands.index("B04")
    nir_idx = bands.index("B08")

    red = stacked[red_idx]
    nir = stacked[nir_idx]
    ndvi = (nir - red) / (nir + red + 1e-10)
    return np.clip(ndvi, -1, 1)


def save_raster(output_path, array, meta):
    meta_out = meta.copy()
    meta_out.update({"count": 1, "dtype": "float32", "driver": "GTiff"})
    with rasterio.open(output_path, "w", **meta_out) as dst:
        dst.write(array.astype(np.float32), 1)

def create_rgb_from_stack(stacked, bands=["B02", "B03", "B04", "B08"]):
    """
    Create an RGB image from the stacked Sentinel-2 bands.
    Output is scaled 0-1 for visualization.
    """
    red = stacked[bands.index("B04")]
    green = stacked[bands.index("B03")]
    blue = stacked[bands.index("B02")]

    # Normalize each band (2nd–98th percentile stretch)
    def stretch(b):
        p2, p98 = np.percentile(b, (2, 98))
        return np.clip((b - p2) / (p98 - p2), 0, 1)

    rgb = np.dstack([stretch(red), stretch(green), stretch(blue)])
    return rgb

def save_rgb(output_path_tif, rgb_array, meta):
    meta_out = meta.copy()
    meta_out.update({
        "count": 3,
        "dtype": "float32",
        "driver": "GTiff"
    })
    with rasterio.open(output_path_tif, "w", **meta_out) as dst:
        for i in range(3):
            dst.write(rgb_array[:, :, i].astype(np.float32), i + 1)

def get_relevant_capture_data():
    with Session(engine) as session:
        return session.query(CaptureData).where(
            CaptureData.backed_up == True, 
            CaptureData.mission_id == "SENTINEL-2A"
            ).all()

if __name__ == "__main__":
    bounds = (-98.898926, 18.955649, -98.399734, 19.282628)

    check_for_new_images()
    get_capture_data()
    
    for capture in get_relevant_capture_data():
        id = capture.id

        scene_folder = f"data/raw/{id}/"
        bands = ["B02", "B03", "B04", "B08"]
        get_capture_data_by_id_and_bands(id, bands)

        stacked, meta = load_and_stack_bands(scene_folder, bands)
        cropped, meta_crop = crop_and_normalize(stacked, meta, bounds)

        ndvi = compute_ndvi_from_stack(cropped, bands)
        rgb = create_rgb_from_stack(cropped, bands)

        save_raster(f"data/features/ndvi_{id}.tif", ndvi, meta_crop)
        save_rgb(f"data/features/rgb_{id}.tif", rgb, meta_crop)
    
    ndvi_files = sorted(glob.glob("data/features/ndvi_*.tif"))

    # ------- Plotting NDVI over time ------- #
    records = []
    with Session(engine) as session:
        for file in ndvi_files:
            print(f"Processing file: {file}")
            match = re.search(r'(\d+)\.tif', file)
            id = match.group(1)
            capture = session.query(CaptureData).where(CaptureData.id == id).first()
            sensing_time = capture.sensing_time
            sensing_date = sensing_time.date()
            year = sensing_time.year
            with rasterio.open(file) as src:
                ndvi = src.read(1)
                # Mask invalid or zero values (common with clouds or water)
                ndvi = np.where((ndvi > -1) & (ndvi < 1), ndvi, np.nan)
                mean_ndvi = np.nanmean(ndvi)
                records.append({"sensing_date": sensing_date, "mean_ndvi": mean_ndvi})
    
    df = pd.DataFrame(records).sort_values("sensing_date")
    plt.figure(figsize=(8,5))
    plt.plot(df["sensing_date"], df["mean_ndvi"], "o-", color="green", lw=2)
    plt.title("Mean NDVI Over Time")
    plt.xlabel("")
    plt.ylabel("Mean NDVI")
    plt.grid(True)
    plt.savefig("ndvi_over_time.png", dpi=300)

    # ------- Plotting Trend map ------- #
    years = []
    stack = []
    meta_ref = None

    with Session(engine) as session:
        for file in ndvi_files:
            match = re.search(r'(\d+)\.tif', file)
            id = match.group(1)
            capture = session.query(CaptureData).where(CaptureData.id == id).first()
            sensing_time = capture.sensing_time
            year = sensing_time.year

            if year not in years:
                years.append(year)
                print(f"Processing file: {file} for year {year}")
                with rasterio.open(file) as src:
                    if meta_ref is None:
                        meta_ref = src.meta
                    stack.append(src.read(1))
                
    ndvi_stack = np.stack(stack, axis=0)  # shape: (years, height, width)

    # Fit a linear regression per pixel to get NDVI slope (trend)
    h, w = ndvi_stack.shape[1:]
    slopes = np.zeros((h, w), dtype=np.float32)

    for i in range(h):
        y_series = ndvi_stack[:, i, :]
        mask = ~np.isnan(y_series)
        for j in range(w):
            y = y_series[:, j]
            if np.count_nonzero(mask[:, j]) > 5:  # at least 5 valid years
                X = np.array(years).reshape(-1, 1)
                reg = LinearRegression().fit(X[mask[:, j]], y[mask[:, j]])
                slopes[i, j] = reg.coef_[0]
            else:
                slopes[i, j] = np.nan

    # Visualize trend
    plt.imshow(slopes, cmap="RdYlGn", vmin=-0.02, vmax=0.02)
    plt.colorbar(label="NDVI Trend per Year")
    plt.title("NDVI Trend Map (2015–2024)")
    plt.savefig("ndvi_trend_map.png", dpi=300)