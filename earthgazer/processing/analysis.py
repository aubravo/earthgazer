"""
Temporal analysis module for NDVI time series and trend analysis.
"""

import glob
import logging
import re
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from sklearn.linear_model import LinearRegression
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from earthgazer.database.definitions import CaptureData
from earthgazer.settings import EarthGazerSettings

logger = logging.getLogger(__name__)


def compute_ndvi_time_series(
    settings: EarthGazerSettings,
    ndvi_files_pattern: str = "data/features/ndvi_*.tif",
    output_path: str = "ndvi_over_time.png"
) -> pd.DataFrame:
    """
    Compute mean NDVI over time from a series of NDVI GeoTIFF files.

    Args:
        settings: EarthGazer settings instance
        ndvi_files_pattern: Glob pattern for NDVI files
        output_path: Path to save the time series plot

    Returns:
        DataFrame with columns: sensing_date, mean_ndvi
    """
    logger.info("Computing NDVI time series")

    ndvi_files = sorted(glob.glob(ndvi_files_pattern))
    logger.info(f"Found {len(ndvi_files)} NDVI files")

    if not ndvi_files:
        logger.warning("No NDVI files found")
        return pd.DataFrame()

    engine = create_engine(settings.database.url, echo=False)
    records = []

    with Session(engine) as session:
        for file in ndvi_files:
            logger.debug(f"Processing {file}")

            # Extract capture ID from filename
            match = re.search(r'(\d+)\.tif', file)
            if not match:
                logger.warning(f"Could not extract ID from filename: {file}")
                continue

            capture_id = int(match.group(1))

            # Get sensing time from database
            capture = session.query(CaptureData).where(CaptureData.id == capture_id).first()
            if not capture:
                logger.warning(f"No capture data found for ID {capture_id}")
                continue

            sensing_time = capture.sensing_time
            sensing_date = sensing_time.date()

            # Compute mean NDVI
            with rasterio.open(file) as src:
                ndvi = src.read(1)
                # Mask invalid values (common with clouds or water)
                ndvi = np.where((ndvi > -1) & (ndvi < 1), ndvi, np.nan)
                mean_ndvi = np.nanmean(ndvi)

            records.append({
                "sensing_date": sensing_date,
                "mean_ndvi": mean_ndvi
            })

    # Create DataFrame
    df = pd.DataFrame(records).sort_values("sensing_date")
    logger.info(f"Computed {len(df)} NDVI time series records")

    # Plot time series
    if not df.empty:
        plt.figure(figsize=(8, 5))
        plt.plot(df["sensing_date"], df["mean_ndvi"], "o-", color="green", lw=2)
        plt.title("Mean NDVI Over Time")
        plt.xlabel("")
        plt.ylabel("Mean NDVI")
        plt.grid(True)

        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=300)
        plt.close()
        logger.info(f"Time series plot saved to {output_path}")

    return df


def compute_ndvi_trend_map(
    settings: EarthGazerSettings,
    ndvi_files_pattern: str = "data/features/ndvi_*.tif",
    output_path: str = "ndvi_trend_map.png",
    min_valid_years: int = 5
) -> np.ndarray:
    """
    Compute pixel-wise NDVI trend (slope) over time using linear regression.

    Args:
        settings: EarthGazer settings instance
        ndvi_files_pattern: Glob pattern for NDVI files
        output_path: Path to save the trend map visualization
        min_valid_years: Minimum number of valid years required for trend calculation

    Returns:
        2D array of NDVI slopes (trend per year)
    """
    logger.info("Computing NDVI trend map")

    ndvi_files = sorted(glob.glob(ndvi_files_pattern))
    logger.info(f"Found {len(ndvi_files)} NDVI files")

    if not ndvi_files:
        logger.warning("No NDVI files found")
        return np.array([])

    engine = create_engine(settings.database.url, echo=False)
    years = []
    stack = []
    meta_ref = None

    with Session(engine) as session:
        for file in ndvi_files:
            # Extract capture ID
            match = re.search(r'(\d+)\.tif', file)
            if not match:
                continue

            capture_id = int(match.group(1))

            # Get year from database
            capture = session.query(CaptureData).where(CaptureData.id == capture_id).first()
            if not capture:
                continue

            year = capture.sensing_time.year

            # Load one NDVI per year (skip duplicates)
            if year not in years:
                years.append(year)
                logger.debug(f"Loading {file} for year {year}")

                with rasterio.open(file) as src:
                    if meta_ref is None:
                        meta_ref = src.meta

                    stack.append(src.read(1))

    if not stack:
        logger.warning("No valid NDVI data loaded")
        return np.array([])

    ndvi_stack = np.stack(stack, axis=0)  # shape: (years, height, width)
    logger.info(f"Stacked {len(years)} years of NDVI data: {ndvi_stack.shape}")

    # Fit linear regression per pixel
    h, w = ndvi_stack.shape[1:]
    slopes = np.zeros((h, w), dtype=np.float32)

    logger.info("Fitting linear regression per pixel...")
    for i in range(h):
        if i % 100 == 0:
            logger.debug(f"Processing row {i}/{h}")

        y_series = ndvi_stack[:, i, :]
        mask = ~np.isnan(y_series)

        for j in range(w):
            y = y_series[:, j]

            # Only fit if enough valid years
            if np.count_nonzero(mask[:, j]) >= min_valid_years:
                X = np.array(years).reshape(-1, 1)
                reg = LinearRegression().fit(X[mask[:, j]], y[mask[:, j]])
                slopes[i, j] = reg.coef_[0]
            else:
                slopes[i, j] = np.nan

    logger.info("Trend computation complete")

    # Visualize trend map
    plt.figure(figsize=(10, 8))
    plt.imshow(slopes, cmap="RdYlGn", vmin=-0.02, vmax=0.02)
    plt.colorbar(label="NDVI Trend per Year")
    plt.title(f"NDVI Trend Map ({min(years)}–{max(years)})")

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300)
    plt.close()
    logger.info(f"Trend map saved to {output_path}")

    return slopes
