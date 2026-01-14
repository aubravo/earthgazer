"""
Preprocessing module for band stacking, cropping, and normalization.
"""

import glob
import logging
import os
from typing import Dict, List, Tuple

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.windows import from_bounds

logger = logging.getLogger(__name__)


def load_and_stack_bands(
    scene_folder: str,
    bands: List[str] = None
) -> Tuple[np.ndarray, Dict]:
    """
    Load and stack multi-spectral bands from a folder.

    Args:
        scene_folder: Path to folder containing band files
        bands: List of band identifiers (e.g., ["B02", "B03", "B04", "B08"])

    Returns:
        Tuple of (stacked array with shape (bands, height, width), metadata dict)
    """
    if bands is None:
        bands = ["B02", "B03", "B04", "B08"]

    logger.info(f"Loading and stacking bands {bands} from {scene_folder}")

    # Find band files
    band_files = []
    for b in bands:
        matches = glob.glob(os.path.join(scene_folder, f"*{b}*.jp2"))
        if not matches:
            # Try TIF extension
            matches = glob.glob(os.path.join(scene_folder, f"*{b}*.TIF"))

        if not matches:
            raise FileNotFoundError(f"Band {b} not found in {scene_folder}")

        band_files.append(matches[0])
        logger.debug(f"Found {b}: {matches[0]}")

    # Load and stack bands
    band_data = []
    ref_meta = None

    for i, path in enumerate(band_files):
        with rasterio.open(path) as src:
            band = src.read(1).astype(np.float32)

            if ref_meta is None:
                # Use first band as reference
                ref_meta = src.meta.copy()
                band_ref = band
            else:
                # Resample band if resolution differs
                if src.shape != (ref_meta['height'], ref_meta['width']):
                    logger.debug(f"Resampling band {bands[i]} from {src.shape} to reference shape")
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
    logger.info(f"Stacked bands into array with shape {stacked.shape}")

    return stacked, ref_meta


def crop_and_normalize(
    image: np.ndarray,
    meta: Dict,
    bounds: Tuple[float, float, float, float]
) -> Tuple[np.ndarray, Dict]:
    """
    Crop and normalize (north-up) image to a given lat/lon bounding box.

    Args:
        image: Numpy array with shape (bands, height, width)
        meta: Rasterio metadata dict
        bounds: Geographic bounds as (min_lon, min_lat, max_lon, max_lat)

    Returns:
        Tuple of (cropped array, updated metadata dict)
    """
    logger.info(f"Cropping image to bounds: {bounds}")

    # Transform lat/lon bounds to image CRS
    if meta["crs"].to_string() != "EPSG:4326":
        target_bounds = transform_bounds("EPSG:4326", meta["crs"], *bounds)
    else:
        target_bounds = bounds

    # Derive pixel window from geographic bounds
    window = from_bounds(*target_bounds, transform=meta["transform"])
    window = window.round_offsets().round_shape()

    # Crop image
    cropped = image[
        :,
        int(window.row_off):int(window.row_off + window.height),
        int(window.col_off):int(window.col_off + window.width)
    ]

    # Update metadata
    meta_cropped = meta.copy()
    meta_cropped.update({
        "height": cropped.shape[1],
        "width": cropped.shape[2],
        "transform": rasterio.windows.transform(window, meta["transform"])
    })

    # Ensure north-up orientation
    if meta_cropped["transform"].a < 0 or meta_cropped["transform"].e > 0:
        logger.debug("Flipping image to north-up orientation")
        cropped = np.flipud(cropped)

    logger.info(f"Cropped image to shape {cropped.shape}")

    return cropped, meta_cropped
