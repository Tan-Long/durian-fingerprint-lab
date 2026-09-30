"""Read exact-frame RGB/depth/confidence diagnostic layers; never write sources.

read_depth_layers(camera_dir, frame_index, rgb, include_exterior=False) accepts
the caller's unrotated full RGB frame (possibly resized, but NOT cropped).
The caller must decode that exact zero-based frame; this helper cannot establish
pairing from an RGB array alone. Depth uint16 millimetres and confidence uint8
classes 0/1/2 come from the matching six-digit PNG names.

Confidence >= 1 follows test_video/rgbd_mesh.py's diagnostic validity convention;
depth zero and low-confidence pixels are excluded, including after hole filling.
Confidence is categorical, NOT a probability, match score, or fractional weight.
Nearest-neighbour resizing assumes the export's depth/RGB pixel registration;
no distortion correction, camera fusion, ARKit pose, or metric accuracy claim.

Layers are RGBA uint8 at RGB resolution; raw depth/confidence/validity are also
returned. Foreground and optional groove/spike layers describe OBSERVED EXTERIOR
features, never hidden locules/arils. Enable the existing RGB groove/spike
heuristics only on selected winner frames, not every ranking frame.

Dependencies: existing numpy, scipy and OpenCV in test_video/.venv. Authority:
docs/stray-scanner/format.md and the source session's README_AGENT.md/sync.json.
No CLI or output writer: the caller owns any derived diagnostic artifacts.
"""

from __future__ import annotations

import csv
import hashlib
import math
from pathlib import Path

import cv2
import numpy as np
from scipy import ndimage

from prototypes.durian_2d_projection.prototype_pattern_match import registration_mask
from prototypes.durian_2d_projection.frame_spikes import detect_grooves_2d, detect_spikes_2d


def source_info(path):
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def frame_row(path, frame_index):
    if not path.is_file():
        return None
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.DictReader(handle, skipinitialspace=True)
                if row.get("frame", "").strip().isdigit() and int(row["frame"]) == frame_index]
    if len(rows) > 1:
        raise ValueError(f"{path}: duplicate metadata rows for frame {frame_index}")
    return rows[0] if rows else None


def numeric_fields(row, fields, path):
    if row is None:
        return None
    try:
        values = {key: float(row[key]) for key in fields}
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{path}: missing/nonnumeric exact-frame metadata {fields}") from error
    if not all(math.isfinite(value) for value in values.values()):
        raise ValueError(f"{path}: nonfinite exact-frame metadata")
    return values


def rgba(mask, color, alpha=170):
    layer = np.zeros((*mask.shape, 4), np.uint8)
    layer[mask, :3] = color
    layer[mask, 3] = alpha
    return layer


def read_depth_layers(camera_dir: Path, frame_index: int, rgb: np.ndarray, *, include_exterior=False):
    if isinstance(frame_index, bool) or not isinstance(frame_index, int) or frame_index < 0:
        raise ValueError("frame_index must be a nonnegative integer, not a bool")
    if (not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8 or rgb.ndim != 3 or
            rgb.shape[2] != 3 or min(rgb.shape[:2]) < 1):
        raise ValueError("rgb must be a nonempty HxWx3 uint8 RGB frame")
    camera_dir = Path(camera_dir)
    paths = {name: camera_dir / name / f"{frame_index:06d}.png" for name in ("depth", "confidence")}
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(f"Missing exact-frame source: {path}; no nearest-frame substitution")
    depth = cv2.imread(str(paths["depth"]), cv2.IMREAD_UNCHANGED)
    confidence = cv2.imread(str(paths["confidence"]), cv2.IMREAD_UNCHANGED)
    if depth is None or depth.dtype != np.uint16 or depth.shape != (192, 256):
        raise ValueError("depth must be native 192x256 uint16 millimetres for the existing registration_mask")
    if confidence is None or confidence.dtype != np.uint8 or confidence.shape != depth.shape:
        raise ValueError("confidence must be uint8 and match the native depth shape")
    if not np.isin(confidence, [0, 1, 2]).all():
        raise ValueError("confidence classes must be 0/1/2 per docs/stray-scanner/format.md")
    sources = {key: source_info(path) for key, path in paths.items()}
    native_valid = (depth > 0) & (confidence >= 1)
    filtered_depth = np.where(native_valid, depth, 0).astype(np.uint16)
    zoom = (rgb.shape[0] / depth.shape[0], rgb.shape[1] / depth.shape[1])
    # Same nearest-neighbour grid convention as prototype registration_mask.
    resized_depth = ndimage.zoom(depth, zoom, order=0)
    resized_confidence = ndimage.zoom(confidence, zoom, order=0)
    valid = (resized_depth > 0) & (resized_confidence >= 1)
    mask = np.zeros(rgb.shape[:2], bool)
    issues = []
    patch = filtered_depth[62:130, 72:184]
    if np.any((patch > 0) & (patch < 2000)):
        try:
            mask = registration_mask(rgb, filtered_depth) & valid
        except RuntimeError as error:
            issues.append(str(error))
    else:
        issues.append("No valid central depth below 2000mm for existing foreground heuristic; no RGB-only fallback")

    confidence_rgb = np.array([[225, 55, 55], [240, 180, 45], [55, 200, 105]], np.uint8)[resized_confidence]
    confidence_layer = np.dstack((confidence_rgb, np.full(mask.shape, 180, np.uint8)))
    depth_layer = np.zeros((*mask.shape, 4), np.uint8)
    display_range = None
    if valid.any():
        low, high = int(resized_depth[valid].min()), int(resized_depth[valid].max())
        display_range = [low, high]
        normalized = np.clip((resized_depth.astype(np.float32) - low) * 255 / max(high - low, 1), 0, 255).astype(np.uint8)
        colors = cv2.cvtColor(cv2.applyColorMap(normalized, cv2.COLORMAP_TURBO), cv2.COLOR_BGR2RGB)
        depth_layer[valid, :3] = colors[valid]
        depth_layer[valid, 3] = 200
    layers = {"mask": rgba(mask, (40, 215, 120)), "depth": depth_layer, "confidence": confidence_layer}
    stats = {"frame_index_zero_based": frame_index, "native_depth_size_wh": [256, 192],
             "rgb_size_wh": [rgb.shape[1], rgb.shape[0]],
             "resampling": "nearest neighbour (scipy.ndimage.zoom order=0), same grid as registration_mask",
             "validity_rule": "depth_mm > 0 AND confidence >= 1; no confidence probabilities/weights",
             "confidence_native_counts": {str(c): int((confidence == c).sum()) for c in (0, 1, 2)},
             "valid_depth_pixels": int(valid.sum()), "foreground_pixels": int(mask.sum()),
             "depth_display_range_mm": display_range,
             "foreground_median_depth_mm": float(np.median(resized_depth[mask])) if mask.any() else None,
             "exterior_features_computed": bool(include_exterior), "issues": issues,
             "limits": "Observed exterior foreground/depth only, NOT internal anatomy or locule/aril predictions. Export registration assumed; RGB caller must supply exact unrotated uncropped frame. No pose fusion or accuracy claim."}
    if include_exterior:
        grooves = np.zeros(mask.shape, bool)
        spikes = []
        if ndimage.binary_erosion(mask, iterations=2).any():
            grooves = detect_grooves_2d(rgb, mask) & mask
            spikes = detect_spikes_2d(rgb, mask)
        spike_pixels = np.zeros(mask.shape, np.uint8)
        for detection in spikes:
            row, column = detection["tip"]  # Existing detector returns row,column, NOT x,y.
            cv2.circle(spike_pixels, (column, row), 4, 1, 1)
        layers.update(groove=rgba(grooves, (245, 145, 40), 210),
                      spike=rgba(spike_pixels.astype(bool) & mask, (245, 70, 210), 240))
        stats.update(visible_spike_candidates=len(spikes), exterior_detector="frame_spikes RGB heuristic; not validated anatomy")

    transform_path, odometry_path = camera_dir / "frame_transforms.csv", camera_dir / "odometry.csv"
    timing = numeric_fields(frame_row(transform_path, frame_index), ["timestamp_unix"], transform_path)
    intrinsics = numeric_fields(frame_row(odometry_path, frame_index), ["fx", "fy", "cx", "cy"], odometry_path)
    for name, path in (("frame_transforms", transform_path), ("odometry", odometry_path)):
        if path.is_file():
            sources[name] = source_info(path)
    if timing is None:
        issues.append("No exact-frame timestamp; no nominal-FPS or neighbouring-row substitution")
    if intrinsics is None:
        issues.append("No exact-frame intrinsics; camera_matrix.csv last-frame values not substituted")
    else:
        intrinsics = {**intrinsics, "coordinate_space": "original camera pixels; NOT rescaled to display RGB",
                      "applied": False, "frame_index": frame_index}
    stats["timestamp_limit"] = "Raw timestamp_unix column retained; epoch origin and cross-camera clock alignment not established"
    return {"mask": mask, "valid_depth_mask": valid, "depth_mm": resized_depth,
            "confidence": resized_confidence, "layers": layers, "stats": stats, "sources": sources,
            "timestamp_unix": timing["timestamp_unix"] if timing else None, "intrinsics": intrinsics}
