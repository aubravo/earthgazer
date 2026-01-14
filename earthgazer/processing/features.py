"""
Feature extraction module for computing NDVI and RGB composites.
"""

import logging
from typing import List

import numpy as np

logger = logging.getLogger(__name__)


def compute_ndvi_from_stack(
    stacked: np.ndarray,
    bands: List[str] = None
) -> np.ndarray:
    """
    Compute Normalized Difference Vegetation Index (NDVI) from stacked bands.

    NDVI = (NIR - RED) / (NIR + RED + epsilon)

    Args:
        stacked: Numpy array with shape (bands, height, width)
        bands: List of band identifiers corresponding to stacked array channels
               (e.g., ["B02", "B03", "B04", "B08"])

    Returns:
        NDVI array with shape (height, width), values clipped to [-1, 1]
    """
    if bands is None:
        bands = ["B02", "B03", "B04", "B08"]

    logger.info("Computing NDVI from stacked bands")

    try:
        red_idx = bands.index("B04")
        nir_idx = bands.index("B08")
    except ValueError as e:
        raise ValueError(f"Required bands B04 (red) and B08 (NIR) not found in {bands}") from e

    red = stacked[red_idx]
    nir = stacked[nir_idx]

    # Compute NDVI with small epsilon to avoid division by zero
    ndvi = (nir - red) / (nir + red + 1e-10)

    # Clip to valid range
    ndvi = np.clip(ndvi, -1, 1)

    logger.info(f"NDVI computed. Range: [{np.nanmin(ndvi):.3f}, {np.nanmax(ndvi):.3f}], Mean: {np.nanmean(ndvi):.3f}")

    return ndvi


def create_rgb_from_stack(
    stacked: np.ndarray,
    bands: List[str] = None
) -> np.ndarray:
    """
    Create an RGB true-color composite from stacked bands.

    Applies 2nd-98th percentile stretch for contrast enhancement.
    Output is scaled to [0, 1] for visualization.

    Args:
        stacked: Numpy array with shape (bands, height, width)
        bands: List of band identifiers corresponding to stacked array channels
               (e.g., ["B02", "B03", "B04", "B08"])

    Returns:
        RGB array with shape (height, width, 3), values in [0, 1]
    """
    if bands is None:
        bands = ["B02", "B03", "B04", "B08"]

    logger.info("Creating RGB composite from stacked bands")

    try:
        red_idx = bands.index("B04")
        green_idx = bands.index("B03")
        blue_idx = bands.index("B02")
    except ValueError as e:
        raise ValueError(f"Required RGB bands (B02, B03, B04) not found in {bands}") from e

    red = stacked[red_idx]
    green = stacked[green_idx]
    blue = stacked[blue_idx]

    def stretch(band):
        """Apply percentile stretch for contrast enhancement."""
        p2, p98 = np.percentile(band, (2, 98))
        return np.clip((band - p2) / (p98 - p2 + 1e-10), 0, 1)

    # Stack RGB channels
    rgb = np.dstack([stretch(red), stretch(green), stretch(blue)])

    logger.info(f"RGB composite created with shape {rgb.shape}")

    return rgb
