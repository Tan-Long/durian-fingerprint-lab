"""Pure math for the throwaway canonical pattern-map matcher."""

from __future__ import annotations

import numpy as np
from scipy import ndimage


def pattern_features(atlas: np.ndarray, valid: np.ndarray) -> np.ndarray:
    gray = atlas.astype(np.float32).mean(axis=2)
    detail = ndimage.gaussian_filter(gray, 1) - ndimage.gaussian_filter(gray, 6)
    features = np.hypot(ndimage.sobel(detail, axis=0), ndimage.sobel(detail, axis=1))
    features[~valid] = 0
    return features


def circular_ncc(reference: np.ndarray, query: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Score every horizontal circular shift of a partial canonical map."""
    mask = valid.astype(np.float32)
    count = mask.sum()
    centered = (query - query[valid].mean()) * mask
    query_energy = np.square(centered).sum()

    mask_fft = np.fft.rfft(mask, axis=1)
    reference_fft = np.fft.rfft(reference, axis=1)
    centered_fft = np.fft.rfft(centered, axis=1)
    cross = np.fft.irfft(
        np.sum(np.conj(centered_fft) * reference_fft, axis=0),
        n=reference.shape[1],
    )
    local_sum = np.fft.irfft(
        np.sum(np.conj(mask_fft) * reference_fft, axis=0),
        n=reference.shape[1],
    )
    local_square_sum = np.fft.irfft(
        np.sum(np.conj(mask_fft) * np.fft.rfft(np.square(reference), axis=1), axis=0),
        n=reference.shape[1],
    )
    local_energy = np.maximum(local_square_sum - np.square(local_sum) / count, 1e-9)
    return cross / np.sqrt(query_energy * local_energy)


def circular_difference(first: float, second: float) -> float:
    difference = abs(first - second) % 360
    return min(difference, 360 - difference)

