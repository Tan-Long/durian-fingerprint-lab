#!/usr/bin/env python3
"""PROTOTYPE: test a 360° map from overlapping front-facing RGB bands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

try:
    from . import project
    from .image_pattern_map import local_contrast_pattern
    from .prototype_pattern_match import read_png, registration_mask
except ImportError:  # Direct script execution.
    import project
    from image_pattern_map import local_contrast_pattern
    from prototype_pattern_match import read_png, registration_mask


def minimum_cost_seam(cost: np.ndarray) -> np.ndarray:
    total = cost[0].astype(np.float64)
    links = np.zeros(cost.shape, dtype=np.int8)
    for row in range(1, len(cost)):
        padded = np.pad(total, 1, constant_values=np.inf)
        choices = np.stack((padded[:-2], padded[1:-1], padded[2:]))
        step = np.argmin(choices, axis=0)
        links[row] = step - 1
        total = cost[row] + np.min(choices, axis=0)
    seam = np.empty(len(cost), dtype=int)
    seam[-1] = int(np.argmin(total))
    for row in range(len(cost) - 1, 0, -1):
        seam[row - 1] = seam[row] + links[row, seam[row]]
    return seam


def seam_aware_atlas(
    frames: np.ndarray,
    masks: list[np.ndarray],
    phases: np.ndarray,
    *,
    axis_y: int,
    x0: int,
    x1: int,
    radius: np.ndarray,
    max_view_degrees: float,
    atlas_width: int,
) -> tuple[np.ndarray, np.ndarray]:
    longitude_limit = np.deg2rad(max_view_degrees)
    margin = int(np.ceil(atlas_width * longitude_limit / (2 * np.pi))) + 3
    extended_width = atlas_width + 2 * margin
    canvas = np.zeros((x1 - x0, extended_width, 3), dtype=np.uint8)
    canvas_valid = np.zeros(canvas.shape[:2], dtype=bool)
    direction = np.sign(phases[-1] - phases[0]) or 1
    unwrapped_phases = (phases - phases[0]) * direction
    scale = atlas_width / (2 * np.pi)
    source_x = np.arange(x0, x1)[:, None]

    for phase, frame, mask in zip(unwrapped_phases, frames, masks):
        center = margin + phase * scale
        columns = np.arange(
            max(0, int(np.floor(center - longitude_limit * scale))),
            min(extended_width, int(np.ceil(center + longitude_limit * scale)) + 1),
        )
        longitude_offset = ((columns - center) / scale) * direction
        source_y = axis_y - radius[:, None] * np.sin(longitude_offset)[None, :]
        coordinates = (
            source_y,
            np.broadcast_to(source_x, source_y.shape),
        )
        layer_strip = np.stack(
            [ndimage.map_coordinates(frame[..., channel], coordinates, order=1) for channel in range(3)],
            axis=2,
        ).astype(np.uint8)
        usable = ndimage.map_coordinates(mask, coordinates, order=0).astype(bool)
        layer = np.zeros_like(canvas)
        layer[:, columns] = layer_strip
        layer_valid = np.zeros(canvas.shape[:2], dtype=bool)
        layer_valid[:, columns] = usable
        overlap = canvas_valid & layer_valid
        overlap_columns = np.flatnonzero(overlap.sum(axis=0) > canvas.shape[0] * 0.25)
        if not len(overlap_columns):
            take = layer_valid & ~canvas_valid
        else:
            left, right = int(overlap_columns[0]), int(overlap_columns[-1]) + 1
            difference = np.abs(
                canvas[:, left:right].astype(np.int16)
                - layer[:, left:right].astype(np.int16)
            ).mean(axis=2)
            difference[~overlap[:, left:right]] = 1e6
            seam = minimum_cost_seam(difference) + left
            take = layer_valid & (
                ~canvas_valid | (np.arange(extended_width)[None, :] >= seam[:, None])
            )
        canvas[take] = layer[take]
        canvas_valid[take] = True

    canvas = canvas[:, margin : margin + atlas_width]
    valid = canvas_valid[:, margin : margin + atlas_width]
    holes = ~valid
    if holes.any():
        distance, nearest = ndimage.distance_transform_edt(
            holes, return_distances=True, return_indices=True
        )
        fill = holes & (distance <= 3)
        canvas[fill] = canvas[nearest[0][fill], nearest[1][fill]]
        valid[fill] = True
    return canvas, valid


def cylindrical_band_atlas(
    frames: np.ndarray,
    masks: list[np.ndarray],
    *,
    max_view_degrees: float = 4,
    phases: np.ndarray | None = None,
    blend: bool = False,
    seam: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """Keep complete front-facing patches and discard oblique surface pixels."""
    boxes = [project.bounds(mask) for mask in masks]
    axis_y = int(np.median([(box[1] + box[3]) / 2 for box in boxes]))
    tops = []
    for mask in masks:
        any_pixel = mask.any(axis=0)
        top = np.argmax(mask, axis=0).astype(float)
        bottom = (mask.shape[0] - 1 - np.argmax(mask[::-1], axis=0)).astype(float)
        crosses_axis = any_pixel & (top <= axis_y) & (bottom >= axis_y)
        radius = np.minimum(axis_y - top, bottom - axis_y)
        radius[~crosses_axis] = np.nan
        tops.append(radius)
    samples = np.stack(tops)
    measured = np.isfinite(samples).any(axis=0)
    radius = np.full(frames.shape[2], np.nan)
    radius[measured] = np.nanmedian(samples[:, measured], axis=0)
    reliable = np.isfinite(radius) & (radius > 20)
    labels, count = ndimage.label(reliable)
    if not count:
        raise RuntimeError("rotation-axis surface profile failed")
    center_label = labels[frames.shape[2] // 2]
    if not center_label:
        sizes = ndimage.sum(reliable, labels, range(1, count + 1))
        center_label = int(np.argmax(sizes)) + 1
    xs = np.flatnonzero(labels == center_label)
    x0, x1 = int(xs[0]), int(xs[-1]) + 1
    radius = np.interp(np.arange(x0, x1), xs, radius[xs])
    radius = ndimage.gaussian_filter1d(radius, 8)

    atlas_width = max(720, round(2 * np.pi * radius.max()))
    atlas = np.zeros((x1 - x0, atlas_width, 3), dtype=np.uint8)
    best = np.full((x1 - x0, atlas_width), -1.0, dtype=np.float32)
    color_sum = np.zeros(atlas.shape, dtype=np.float32)
    weight_sum = np.zeros(atlas.shape[:2], dtype=np.float32)
    longitude_limit = np.deg2rad(max_view_degrees)
    half_band = int(np.ceil(radius.max() * np.sin(longitude_limit)))
    sample_x = np.arange(x0, x1)
    sample_y = np.arange(axis_y - half_band, axis_y + half_band + 1)
    normalized_y = (axis_y - sample_y[:, None]) / radius[None, :]
    longitude_offset = np.arcsin(np.clip(normalized_y, -1, 1))
    if phases is None:
        phases = np.linspace(0, 2 * np.pi, len(frames), endpoint=False)
    if seam:
        return seam_aware_atlas(
            frames,
            masks,
            phases,
            axis_y=axis_y,
            x0=x0,
            x1=x1,
            radius=radius,
            max_view_degrees=max_view_degrees,
            atlas_width=atlas_width,
        )

    for phase, frame, mask in zip(phases, frames, masks):
        usable = (
            (np.abs(longitude_offset) <= longitude_limit)
            & mask[np.ix_(sample_y, sample_x)]
        )
        atlas_y = np.broadcast_to(np.arange(x1 - x0)[None, :], usable.shape)
        atlas_x = np.floor(
            np.mod(phase + longitude_offset, 2 * np.pi) * atlas_width / (2 * np.pi)
        ).astype(int)
        confidence = np.cos(longitude_offset) ** 64
        source = frame[np.ix_(sample_y, sample_x)]
        rows, columns = atlas_y[usable], atlas_x[usable]
        weights = confidence[usable]
        if blend:
            np.add.at(weight_sum, (rows, columns), weights)
            for channel in range(3):
                np.add.at(
                    color_sum[..., channel],
                    (rows, columns),
                    source[..., channel][usable] * weights,
                )
            continue
        better = weights > best[rows, columns]
        rows, columns, weights = rows[better], columns[better], weights[better]
        best[rows, columns] = weights
        atlas[rows, columns] = source[usable][better]

    valid = weight_sum > 0 if blend else best >= 0
    if blend:
        atlas[valid] = np.clip(
            color_sum[valid] / weight_sum[valid, None], 0, 255
        ).astype(np.uint8)
    holes = ~valid
    if holes.any():
        distance, nearest = ndimage.distance_transform_edt(
            holes, return_distances=True, return_indices=True
        )
        fill = holes & (distance <= 3)
        atlas[fill] = atlas[nearest[0][fill], nearest[1][fill]]
        valid[fill] = True
    return atlas, valid


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--frames", type=int, default=144)
    parser.add_argument("--max-view", type=float, default=4)
    args = parser.parse_args()

    source = args.root / "CAM-TURNTABLE-01"
    output = args.root / "processed" / "center-strip-map"
    output.mkdir(parents=True, exist_ok=True)
    duration = float(project.probe(source / "rgb.mp4")["format"]["duration"])
    samples = args.frames + 9
    frames = project.decode_frames(
        source / "rgb.mp4", duration, width=960, height=720, samples=samples
    )[: args.frames]
    depth_files = sorted((source / "depth").glob("*.png"))
    depth_indexes = np.linspace(
        int(len(depth_files) * 0.02), int(len(depth_files) * 0.98) - 1, samples
    ).round().astype(int)[: args.frames]
    masks = [
        registration_mask(frame, read_png(depth_files[index], "gray16le", "<u2"))
        for frame, index in zip(frames, depth_indexes)
    ]
    measured = project.frame_phases(
        [(np.rot90(frame), np.rot90(mask)) for frame, mask in zip(frames, masks)]
    )
    if abs(measured[-1] - measured[0]) < 0.5:
        raise RuntimeError("not enough measured rotation to build a map")
    phases = (measured - measured[0]) * (2 * np.pi / abs(measured[-1] - measured[0]))

    texture, valid = cylindrical_band_atlas(
        frames, masks, max_view_degrees=args.max_view, phases=phases
    )
    pattern = local_contrast_pattern(texture, valid)
    project.write_png(texture, output / "texture-map.png")
    project.write_png(pattern, output / "pattern-map.png")
    report = {
        "status": "experimental; reject unless visual audit passes",
        "frames": len(frames),
        "map_width": texture.shape[1],
        "map_height": texture.shape[0],
        "coverage": round(float(valid.mean()), 4),
        "max_view_degrees": args.max_view,
        "measured_motion_degrees": round(float(abs(np.rad2deg(measured[-1] - measured[0]))), 1),
        "method": "overlapping front-facing bands around the horizontal rotation axis",
    }
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
