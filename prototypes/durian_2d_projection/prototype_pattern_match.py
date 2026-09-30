#!/usr/bin/env python3
"""PROTOTYPE: can full-map vs partial-map projection recover matching surface angles?

Run: python3 prototypes/durian_2d_projection/prototype_pattern_match.py test_video

The registration video becomes one canonical 360° map. Each consumer photo
becomes a masked partial map; unseen cells stay unknown. The prototype searches
every circular longitude shift and prints the strongest match.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path

import numpy as np
from scipy import ndimage

try:
    from . import project as projection
    from .pattern_map_logic import circular_difference, circular_ncc, pattern_features
except ImportError:  # Direct script execution.
    import project as projection
    from pattern_map_logic import circular_difference, circular_ncc, pattern_features


MAP_WIDTH = 1440
MAP_HEIGHT = 512
FRAME_SAMPLES = 72


def read_png(path: Path, pixel_format: str, dtype: str) -> np.ndarray:
    raw = projection.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", pixel_format, "pipe:1"]
    )
    return np.frombuffer(raw, dtype=dtype).reshape(192, 256)


def largest_center_component(mask: np.ndarray) -> np.ndarray:
    labels, count = ndimage.label(mask)
    center = np.array(mask.shape) / 2
    winner = 0
    best = 0.0
    for label in range(1, count + 1):
        ys, xs = np.where(labels == label)
        if len(xs) < 2_000:
            continue
        distance = np.linalg.norm((np.array([ys.mean(), xs.mean()]) - center) / center)
        score = len(xs) / (1 + distance * 2)
        if score > best:
            winner, best = label, score
    if not winner:
        raise RuntimeError("fruit mask failed")
    return ndimage.binary_fill_holes(labels == winner)


def registration_mask(frame: np.ndarray, depth: np.ndarray) -> np.ndarray:
    patch = depth[62:130, 72:184]
    center_depth = np.median(patch[(patch > 0) & (patch < 2_000)])
    near = (depth >= center_depth - 80) & (depth <= center_depth + 130)
    near = ndimage.zoom(
        near, (frame.shape[0] / depth.shape[0], frame.shape[1] / depth.shape[1]), order=0
    )[: frame.shape[0], : frame.shape[1]]
    rgb = frame.astype(np.int16)
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    color = (
        (green - blue > 8)
        & (red - blue > 2)
        & (chroma > 20)
        & (rgb.mean(axis=2) > 45)
        & (rgb.mean(axis=2) < 220)
    )
    return largest_center_component(ndimage.binary_closing(near & color, iterations=3))


def photo_mask(frame: np.ndarray) -> np.ndarray:
    rgb = frame.astype(np.int16)
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    fruit = (
        (2 * green - red - blue > 5)
        & (red - blue > 0)
        & (chroma > 16)
        & (rgb.mean(axis=2) > 35)
        & (rgb.mean(axis=2) < 240)
    )
    fruit[:10] = fruit[-10:] = False
    fruit[:, :10] = fruit[:, -10:] = False
    fruit = ndimage.binary_closing(fruit, iterations=7)
    return largest_center_component(fruit)


def orient_vertical(frame: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ys, xs = np.where(mask)
    covariance = np.cov(np.stack((xs, ys)))
    _, vectors = np.linalg.eigh(covariance)
    x, y = vectors[:, -1]
    angle = np.degrees(np.arctan2(x, y))
    return (
        ndimage.rotate(frame, angle, reshape=True, order=1),
        ndimage.rotate(mask, angle, reshape=True, order=0) > 0,
    )


def read_photo(path: Path, *, width: int = 960, height: int = 720) -> np.ndarray:
    raw = projection.run(
        [
            "ffmpeg", "-v", "error", "-i", str(path), "-vf", f"scale={width}:{height}",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
        ]
    )
    return np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3)


def partial_map(frame: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    atlas = projection.spherical_atlas([(frame, mask)], np.array([0.0]))
    valid = np.any(atlas != 0, axis=2)
    valid[: int(MAP_HEIGHT * 0.08)] = False
    valid[int(MAP_HEIGHT * 0.92) :] = False
    valid = ndimage.binary_erosion(valid, iterations=2)
    return atlas, valid


def best_variant(reference: np.ndarray, atlas: np.ndarray, valid: np.ndarray) -> dict:
    candidates = []
    for flip_axis, candidate, candidate_valid in (
        ("normal", atlas, valid),
        ("axis-flip", atlas[::-1], valid[::-1]),
        ("mirror", atlas[:, ::-1], valid[:, ::-1]),
        ("axis+mirror", atlas[::-1, ::-1], valid[::-1, ::-1]),
    ):
        features = pattern_features(candidate, candidate_valid)
        scores = circular_ncc(reference, features, candidate_valid)
        shift = int(np.argmax(scores))
        candidates.append(
            {"variant": flip_axis, "shift": shift, "score": float(scores[shift])}
        )
    return max(candidates, key=lambda item: item["score"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    source = args.root / "CAM-TURNTABLE-01"
    output = args.root / "processed" / "pattern-map-prototype"
    output.mkdir(parents=True, exist_ok=True)

    projection.ATLAS_WIDTH = MAP_WIDTH
    projection.ATLAS_HEIGHT = MAP_HEIGHT
    projection.SURFACE_STEP = 2
    projection.MAX_VIEW_ANGLE = np.deg2rad(28)

    duration = float(projection.probe(source / "rgb.mp4")["format"]["duration"])
    frames = projection.decode_frames(
        source / "rgb.mp4", duration, width=960, height=720, samples=FRAME_SAMPLES
    )
    depth_files = sorted((source / "depth").glob("*.png"))
    depth_indexes = np.linspace(
        int(len(depth_files) * 0.02), int(len(depth_files) * 0.98) - 1, len(frames)
    ).round().astype(int)

    views = []
    for frame, depth_index in zip(frames, depth_indexes):
        depth = read_png(depth_files[depth_index], "gray16le", "<u2")
        views.append((np.rot90(frame), np.rot90(registration_mask(frame, depth))))

    registration = [view for index, view in enumerate(views) if index % 2 == 0]
    phases = np.deg2rad(np.arange(0, 360, 10))
    full_atlas = projection.spherical_atlas(registration, phases)
    full_valid = np.any(full_atlas != 0, axis=2)
    full_features = pattern_features(full_atlas, full_valid)
    projection.write_png(full_atlas, output / "full-map.png")
    ceiling = np.percentile(full_features[full_valid], 97)
    projection.write_png(
        np.repeat(np.clip(full_features * 255 / ceiling, 0, 255).astype(np.uint8)[..., None], 3, axis=2),
        output / "full-pattern.png",
    )

    held_out_atlas, held_out_valid = partial_map(*views[19])
    held_out = best_variant(full_features, held_out_atlas, held_out_valid)
    raw_angle = held_out["shift"] * 360 / MAP_WIDTH
    angle_sign = 1 if circular_difference(raw_angle, 95) <= circular_difference(-raw_angle, 95) else -1
    recovered = (angle_sign * raw_angle) % 360
    assert circular_difference(recovered, 95) <= 15, (recovered, held_out)
    print(f"SELF-CHECK  expected=95.0° recovered={recovered:.1f}° score={held_out['score']:.3f}")

    rows = []
    query_paths = sorted(path for path in (args.root / "processed" / "query-images-retry").glob("IMG_*.jpg") if path.stem[4:].isdigit())
    for path in query_paths:
        frame = read_photo(path)
        oriented = orient_vertical(frame, photo_mask(frame))
        atlas, valid = partial_map(*oriented)
        result = best_variant(full_features, atlas, valid)
        angle = (angle_sign * result["shift"] * 360 / MAP_WIDTH) % 360
        row = {
            "image": path.name,
            "angle_degrees": round(angle, 1),
            "score": round(result["score"], 4),
            "variant": result["variant"],
            "valid_pixels": int(valid.sum()),
        }
        rows.append(row)
        projection.write_png(atlas, output / f"{path.stem}-partial-map.png")
        print(json.dumps(row, ensure_ascii=False))

    with (output / "results.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    print(f"OUTPUT {output}")


if __name__ == "__main__":
    main()
