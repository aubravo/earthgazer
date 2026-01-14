"""
Raster I/O module for reading and writing GeoTIFF files.
"""

import logging
from pathlib import Path
from typing import Dict

import numpy as np
import rasterio

logger = logging.getLogger(__name__)


def save_raster(
    output_path: str,
    array: np.ndarray,
    meta: Dict
) -> None:
    """
    Save a single-band raster array as a GeoTIFF file.

    Args:
        output_path: Path to output GeoTIFF file
        array: 2D numpy array (height, width)
        meta: Rasterio metadata dict from source image
    """
    logger.info(f"Saving single-band raster to {output_path}")

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    meta_out = meta.copy()
    meta_out.update({
        "count": 1,
        "dtype": "float32",
        "driver": "GTiff"
    })

    with rasterio.open(output_path, "w", **meta_out) as dst:
        dst.write(array.astype(np.float32), 1)

    logger.info(f"Raster saved successfully: {output_path}")


def save_rgb(
    output_path: str,
    rgb_array: np.ndarray,
    meta: Dict
) -> None:
    """
    Save an RGB composite as a 3-band GeoTIFF file.

    Args:
        output_path: Path to output GeoTIFF file
        rgb_array: 3D numpy array (height, width, 3) with RGB channels
        meta: Rasterio metadata dict from source image
    """
    logger.info(f"Saving RGB composite to {output_path}")

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    meta_out = meta.copy()
    meta_out.update({
        "count": 3,
        "dtype": "float32",
        "driver": "GTiff"
    })

    with rasterio.open(output_path, "w", **meta_out) as dst:
        for i in range(3):
            dst.write(rgb_array[:, :, i].astype(np.float32), i + 1)

    logger.info(f"RGB composite saved successfully: {output_path}")


def load_raster(file_path: str) -> tuple[np.ndarray, Dict]:
    """
    Load a raster file and return the array and metadata.

    Args:
        file_path: Path to the raster file

    Returns:
        Tuple of (array, metadata dict)
    """
    logger.debug(f"Loading raster from {file_path}")

    with rasterio.open(file_path) as src:
        array = src.read(1)
        meta = src.meta.copy()

    return array, meta
