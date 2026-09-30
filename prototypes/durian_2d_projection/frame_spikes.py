"""Detect visible durian spike tips and feet directly in one RGB frame."""

from __future__ import annotations

import numpy as np
from scipy import ndimage


def _groove_analysis(frame: np.ndarray, mask: np.ndarray, min_spacing: int):
    rgb = frame.astype(np.float32)
    red, green = rgb[..., 0], rgb[..., 1]
    brightness = rgb.mean(axis=2)
    local_darkness = ndimage.gaussian_filter(brightness, min_spacing / 4) - brightness
    groove_score = np.maximum(red - green, 0) + np.maximum(local_darkness, 0) * 0.6
    valid = ndimage.binary_erosion(mask, iterations=2)
    values = groove_score[valid]
    threshold = float(np.median(values) + values.std())
    grooves = valid & (groove_score > threshold)
    grooves = ndimage.binary_dilation(ndimage.binary_closing(grooves, iterations=1))
    return rgb, brightness, valid, groove_score, grooves


def detect_grooves_2d(
    frame: np.ndarray, mask: np.ndarray, *, min_spacing: int = 16
) -> np.ndarray:
    return _groove_analysis(frame, mask, min_spacing)[-1]


def detect_spikes_2d(
    frame: np.ndarray, mask: np.ndarray, *, min_spacing: int = 16
) -> list[dict]:
    rgb, brightness, valid, groove_score, grooves = _groove_analysis(
        frame, mask, min_spacing
    )
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    values = groove_score[valid]

    distance = ndimage.distance_transform_edt(valid & ~grooves)
    peaks = valid & (distance == ndimage.maximum_filter(distance, 2 * min_spacing + 1))
    peaks &= distance >= min_spacing * 0.3
    peak_labels, count = ndimage.label(peaks)
    markers = np.zeros(mask.shape, dtype=np.int32)
    markers[~valid] = -1
    tips = []
    for identifier in range(1, count + 1):
        rows, columns = np.where(peak_labels == identifier)
        if not len(rows):
            continue
        index = np.argmax(distance[rows, columns])
        tip = (int(rows[index]), int(columns[index]))
        tips.append(tip)
        markers[tip] = len(tips)
    if not tips:
        return []

    low, high = np.percentile(values, (2, 98))
    elevation = np.clip((groove_score - low) * 255 / max(high - low, 1e-9), 0, 255).astype(np.uint8)
    regions = ndimage.watershed_ift(elevation, markers)
    brownness = np.maximum(red - green, 0) + 0.35 * np.maximum(red - blue, 0)
    dark_blob = np.maximum(ndimage.gaussian_filter(brightness, 2.5) - brightness, 0)
    tip_score = ndimage.gaussian_filter(brownness + dark_blob * 0.8, 1)
    detections = []
    for identifier, seed in enumerate(tips, 1):
        region = (regions == identifier) & valid
        area = int(region.sum())
        if area < min_spacing**2 // 4 or area > min_spacing**2 * 12:
            continue
        inside = ndimage.binary_erosion(region, iterations=max(2, min_spacing // 8))
        if not inside.any():
            inside = region
        rows, columns = np.where(inside)
        distance_from_seed = np.hypot(rows - seed[0], columns - seed[1])
        evidence = tip_score[rows, columns] - 12 * np.square(
            distance_from_seed / max(np.sqrt(area), 1)
        )
        best = int(np.argmax(evidence))
        tip = (int(rows[best]), int(columns[best]))
        boundary = region & ~ndimage.binary_erosion(region)
        points = np.argwhere(boundary)
        tip_confidence = float(
            (evidence[best] - np.median(evidence)) / (np.std(evidence) + 1e-6)
        )
        detections.append(
            {
                "tip": [tip[0], tip[1]],
                "base_boundary": [[int(row), int(column)] for row, column in points],
                "area_pixels": area,
                "tip_confidence": round(tip_confidence, 4),
            }
        )
    return detections
