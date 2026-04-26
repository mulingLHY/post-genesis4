from typing import Tuple

import numpy as np

def fwhm(x: np.ndarray, data: np.ndarray) -> Tuple[float, float, float]:
    """
    Calculate Full Width at Half Maximum (FWHM) of a peak.

    Args:
        x: X-axis data array.
        data: Y-axis data array containing the peak.

    Returns:
        A tuple of (peak_x, peak_value, fwhm_value) where:
            - peak_x: X coordinate of the peak
            - peak_value: Maximum value of the data
            - fwhm_value: Full width at half maximum
    """
    peak_index = np.argmax(data)
    peak_value = data[peak_index]
    half_max = peak_value / 2.0

    # Left boundary: find index where data crosses half_max
    left_idx = np.where(data[:peak_index] < half_max)[0]
    if len(left_idx) == 0:
        left_boundary = x[0]
    else:
        left_idx1 = left_idx[-1]
        left_idx2 = left_idx1 + 1
        left_boundary = x[left_idx1] + (half_max - data[left_idx1]) / (data[left_idx2] - data[left_idx1]) * (x[left_idx2] - x[left_idx1])

    # Right boundary: find index where data crosses half_max
    right_idx = np.where(data[peak_index:] < half_max)[0]
    if len(right_idx) == 0:
        right_boundary = x[-1]
    else:
        right_idx1 = right_idx[0] + peak_index  # First index below half_max
        right_idx2 = right_idx1 - 1  # Last index above half_max
        # Linear interpolation for right boundary
        right_boundary = x[right_idx1] - (half_max - data[right_idx1]) / (data[right_idx2] - data[right_idx1]) * (x[right_idx1] - x[right_idx2])

    # Calculate FWHM
    fwhm_value = right_boundary - left_boundary

    return x[peak_index], peak_value, fwhm_value