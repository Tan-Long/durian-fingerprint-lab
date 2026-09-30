#!/usr/bin/env python3
"""Extract a detail-preserving front-surface pattern map from still photos."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

try:
    from . import project
    from .prototype_pattern_match import orient_vertical, photo_mask, read_photo
except ImportError:  # Direct script execution.
    import project
    from prototype_pattern_match import orient_vertical, photo_mask, read_photo


def rectify_front(
    frame: np.ndarray,
    mask: np.ndarray,
    *,
    size: int = 1400,
    longitude_degrees: float = 45,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample a visible ellipsoid patch into canonical longitude/height space."""
    x0, y0, x1, y1 = project.bounds(mask)
    source_rows = np.arange(y0, y1)
    left = np.full(len(source_rows), np.nan)
    right = np.full(len(source_rows), np.nan)
    for index, row in enumerate(source_rows):
        occupied = np.flatnonzero(mask[row, x0:x1])
        if len(occupied) >= 8:
            left[index], right[index] = occupied[0] + x0, occupied[-1] + x0

    known = np.isfinite(left)
    if known.sum() < len(source_rows) * 0.5:
        raise RuntimeError("fruit silhouette is too incomplete to rectify")
    left = np.interp(source_rows, source_rows[known], left[known])
    right = np.interp(source_rows, source_rows[known], right[known])

    smoothing = max(3, len(source_rows) / 40)
    centers_by_row = ndimage.gaussian_filter1d((left + right) / 2, smoothing)
    radii_by_row = ndimage.gaussian_filter1d((right - left) / 2, smoothing)
    reliable = radii_by_row >= radii_by_row.max() * 0.4
    reliable_rows = source_rows[reliable]
    if len(reliable_rows) < len(source_rows) * 0.4:
        raise RuntimeError("fruit has too little front-facing surface")

    output_rows = np.linspace(reliable_rows[0], reliable_rows[-1], size)
    centers = np.interp(output_rows, source_rows, centers_by_row)
    radii = np.interp(output_rows, source_rows, radii_by_row)
    longitude = np.deg2rad(np.linspace(-longitude_degrees, longitude_degrees, size))
    source_x = centers[:, None] + radii[:, None] * np.sin(longitude)[None, :]
    source_y = np.broadcast_to(output_rows[:, None], source_x.shape)
    coordinates = np.stack((source_y, source_x))

    texture = np.stack(
        [ndimage.map_coordinates(frame[..., channel], coordinates, order=1) for channel in range(3)],
        axis=2,
    ).astype(np.uint8)
    valid = ndimage.map_coordinates(mask.astype(np.uint8), coordinates, order=0) > 0
    valid = ndimage.binary_erosion(valid, iterations=max(2, size // 350))
    texture[~valid] = 0
    return texture, valid


def local_contrast_pattern(texture: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Keep real image structure while suppressing broad lighting gradients."""
    gray = (
        texture[..., 0].astype(np.float32) * 0.299
        + texture[..., 1].astype(np.float32) * 0.587
        + texture[..., 2].astype(np.float32) * 0.114
    )
    illumination = ndimage.gaussian_filter(gray, 24)
    fine = gray - ndimage.gaussian_filter(gray, 2)
    enhanced = gray + 1.8 * (gray - illumination) + 0.8 * fine
    low, high = np.percentile(enhanced[valid], (1, 99))
    pattern = np.clip((enhanced - low) * 255 / max(high - low, 1), 0, 255).astype(np.uint8)
    pattern[~valid] = 0
    return np.repeat(pattern[..., None], 3, axis=2)


def process(path: Path, output: Path, *, size: int, longitude: float) -> dict:
    frame = read_photo(path, width=2016, height=1512)
    frame, mask = orient_vertical(frame, photo_mask(frame))
    texture, valid = rectify_front(frame, mask, size=size, longitude_degrees=longitude)
    pattern = local_contrast_pattern(texture, valid)
    output.mkdir(parents=True, exist_ok=True)
    project.write_png(texture, output / f"{path.stem}-texture-map.png")
    project.write_png(pattern, output / f"{path.stem}-pattern-map.png")
    return {
        "image": path.name,
        "map_size": size,
        "longitude_degrees": longitude,
        "valid_pixels": int(valid.sum()),
        "coverage": round(float(valid.mean()), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, default=Path("test_video/processed/image-pattern-map"))
    parser.add_argument("--size", type=int, default=1400)
    parser.add_argument("--longitude", type=float, default=45)
    args = parser.parse_args()
    rows = [process(path, args.output, size=args.size, longitude=args.longitude) for path in args.images]
    (args.output / "report.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
