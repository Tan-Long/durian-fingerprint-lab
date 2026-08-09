#!/usr/bin/env python3
"""PROTOTYPE: unwrap a USDZ durian mesh into a comparable radial height map."""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from scipy import ndimage

import project


WIDTH = 1440
HEIGHT = 720


def usd_array(document: str, name: str) -> str:
    match = re.search(rf"\b{re.escape(name)}\s*=\s*\[(.*?)\]\s*\n", document, re.S)
    if not match:
        raise RuntimeError(f"USD array not found: {name}")
    return match.group(1)


def load_mesh(model: Path) -> tuple[np.ndarray, np.ndarray]:
    with tempfile.TemporaryDirectory(prefix="durian-usd-") as temporary:
        text = Path(temporary) / "model.usda"
        subprocess.run(["usdcat", str(model), "-o", str(text)], check=True)
        document = text.read_text()
    points = np.asarray(
        [
            [float(value) for value in item.split(",")]
            for item in re.findall(r"\(([^()]*)\)", usd_array(document, "points"))
        ],
        dtype=np.float32,
    )
    counts = np.fromstring(usd_array(document, "faceVertexCounts"), sep=",", dtype=int)
    indexes = np.fromstring(usd_array(document, "faceVertexIndices"), sep=",", dtype=int)
    if not len(points) or counts.sum() != len(indexes) or np.any(counts != 3):
        raise RuntimeError("Expected one non-empty triangular USD mesh")
    return points, indexes.reshape(-1, 3)


def radial_height(points: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x, y, z = points.T
    center_x = (x.min() + x.max()) / 2
    center_z = (z.min() + z.max()) / 2
    radius = np.hypot(x - center_x, z - center_z)
    normalized_y = (y - y.min()) / max(float(np.ptp(y)), 1e-9)

    bins = np.clip((normalized_y * 63).astype(int), 0, 63)
    body = np.full(64, np.nan, dtype=np.float32)
    for index in range(64):
        values = radius[bins == index]
        if len(values):
            body[index] = np.percentile(values, 25)
    known = np.flatnonzero(~np.isnan(body))
    body = np.interp(np.arange(64), known, body[known])
    body = ndimage.gaussian_filter1d(body, 2)
    spike_height = np.maximum(radius - np.interp(normalized_y * 63, np.arange(64), body), 0)
    longitude = np.mod(np.arctan2(z - center_z, x - center_x), 2 * np.pi) / (2 * np.pi)
    return longitude, 1 - normalized_y, spike_height


def rasterize(
    longitude: np.ndarray,
    vertical: np.ndarray,
    values: np.ndarray,
    faces: np.ndarray,
) -> np.ndarray:
    output = np.full((HEIGHT, WIDTH), np.nan, dtype=np.float32)
    for face in faces:
        ux = longitude[face].copy()
        if np.ptp(ux) > 0.5:
            ux[ux < 0.5] += 1
            variants = (ux, ux - 1)
        else:
            variants = (ux,)
        py = vertical[face] * (HEIGHT - 1)
        heights = values[face]
        for variant in variants:
            px = variant * WIDTH
            x0 = max(0, int(np.floor(px.min())))
            x1 = min(WIDTH - 1, int(np.ceil(px.max())))
            y0 = max(0, int(np.floor(py.min())))
            y1 = min(HEIGHT - 1, int(np.ceil(py.max())))
            if x0 > x1 or y0 > y1 or (x1 - x0 + 1) * (y1 - y0 + 1) > 100_000:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
            denominator = (py[1] - py[2]) * (px[0] - px[2]) + (px[2] - px[1]) * (py[0] - py[2])
            if abs(denominator) < 1e-9:
                continue
            a = ((py[1] - py[2]) * (gx - px[2]) + (px[2] - px[1]) * (gy - py[2])) / denominator
            b = ((py[2] - py[0]) * (gx - px[2]) + (px[0] - px[2]) * (gy - py[2])) / denominator
            c = 1 - a - b
            inside = (a >= -1e-5) & (b >= -1e-5) & (c >= -1e-5)
            if not inside.any():
                continue
            interpolated = a * heights[0] + b * heights[1] + c * heights[2]
            region = output[y0 : y1 + 1, x0 : x1 + 1]
            region[inside] = np.fmax(region[inside], interpolated[inside])
    return output


def generate(model: Path, output: Path) -> Path:
    points, faces = load_mesh(model)
    longitude, vertical, height = radial_height(points)
    surface = rasterize(longitude, vertical, height, faces)
    valid = ~np.isnan(surface)
    if valid.mean() < 0.25:
        raise RuntimeError(f"Only {valid.mean():.0%} of height map is covered")
    ceiling = max(float(np.nanpercentile(surface, 99)), 1e-9)
    normalized = np.clip(surface / ceiling, 0, 1)
    normalized[~valid] = np.nan

    # Object Capture closes unseen backs with a smooth synthetic cap. Put that
    # low-detail sector at the map seam and exclude it from matching.
    middle = normalized[int(HEIGHT * 0.08) : int(HEIGHT * 0.92)]
    column_detail = np.nanpercentile(middle, 90, axis=0)
    column_detail = ndimage.gaussian_filter1d(
        np.nan_to_num(column_detail), WIDTH / 100, mode="wrap"
    )
    reliable = column_detail > np.percentile(column_detail, 35)
    doubled = np.concatenate((reliable, reliable))
    best_start = best_length = start = 0
    for index, is_reliable in enumerate(doubled):
        if is_reliable:
            length = min(index - start + 1, WIDTH)
            if length > best_length:
                best_start, best_length = index - length + 1, length
        else:
            start = index + 1
    reliable_columns = np.zeros(WIDTH, dtype=bool)
    reliable_columns[np.arange(best_start, best_start + best_length) % WIDTH] = True
    center = (best_start + best_length // 2) % WIDTH
    shift = WIDTH // 2 - center
    normalized = np.roll(normalized, shift, axis=1)
    reliable_columns = np.roll(reliable_columns, shift)
    normalized[:, ~reliable_columns] = np.nan
    valid = ~np.isnan(normalized)
    np.save(output / "height-normalized.npy", normalized)

    stops = np.array(
        [[12, 20, 45], [25, 105, 150], [55, 180, 120], [245, 210, 65], [220, 55, 35]],
        dtype=np.float32,
    )
    position = np.nan_to_num(normalized) * (len(stops) - 1)
    low = np.floor(position).astype(int)
    high = np.minimum(low + 1, len(stops) - 1)
    fraction = (position - low)[..., None]
    color = (stops[low] * (1 - fraction) + stops[high] * fraction).astype(np.uint8)
    color[~valid] = 0
    target = output / "height-map.png"
    project.write_png(color, target)
    print(
        f"height map {target}: {points.shape[0]} vertices, {faces.shape[0]} triangles, "
        f"{valid.mean():.0%} coverage",
        flush=True,
    )
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.model.parent
    output.mkdir(parents=True, exist_ok=True)
    generate(args.model, output)


if __name__ == "__main__":
    main()
