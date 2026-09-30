#!/usr/bin/env python3
"""Extract a tip/base graph from a radial durian height surface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage


def extract_spikes(
    surface: np.ndarray,
    *,
    min_distance: int = 18,
    min_prominence: float = 0.04,
    metric_surface: np.ndarray | None = None,
    pole_margin: float = 0.06,
) -> dict:
    valid = np.isfinite(surface)
    margin = int(surface.shape[0] * pole_margin)
    valid[:margin] = valid[-margin:] = False
    filled = np.where(valid, surface, 0).astype(np.float32)
    background = ndimage.gaussian_filter(
        filled, min_distance / 2, mode=("nearest", "wrap")
    )
    prominence = filled - background
    local_max = prominence == ndimage.maximum_filter(
        prominence, 2 * min_distance + 1, mode=("nearest", "wrap")
    )
    tips = np.argwhere(valid & local_max & (prominence >= min_prominence))
    tips = tips[np.argsort(prominence[tuple(tips.T)])[::-1]]

    if not len(tips):
        return {"shape": list(surface.shape), "spikes": [], "edges": []}

    spikes = []
    for identifier, (row, column) in enumerate(tips, 1):
        radius = int(min_distance * 1.25)
        rows = np.arange(max(0, row - radius), min(surface.shape[0], row + radius + 1))
        offsets = np.arange(-radius, radius + 1)
        columns = (column + offsets) % surface.shape[1]
        local = prominence[np.ix_(rows, columns)]
        local_valid = valid[np.ix_(rows, columns)]
        disk = (rows[:, None] - row) ** 2 + offsets[None, :] ** 2 <= radius**2
        threshold = max(min_prominence * 0.25, float(prominence[row, column]) * 0.15)
        candidates = local_valid & disk & (local >= threshold)
        components, _ = ndimage.label(candidates)
        center = (row - rows[0], radius)
        component = components[center]
        local_region = components == component
        region_rows, region_column_indexes = np.where(local_region)
        base_rows = rows[region_rows]
        base_columns = columns[region_column_indexes]
        region_values = filled[base_rows, base_columns]
        local_boundary = local_region & ~ndimage.binary_erosion(local_region)
        boundary_rows, boundary_column_indexes = np.where(local_boundary)
        boundary_points = np.column_stack((rows[boundary_rows], columns[boundary_column_indexes]))
        boundary_points = boundary_points[:: max(1, len(boundary_points) // 64)]
        base_level = float(np.percentile(region_values, 10))
        spikes.append(
            {
                "id": identifier,
                "tip": {
                    "row": int(row),
                    "column": int(column),
                    "height": round(float(filled[row, column]), 6),
                    "prominence": round(float(prominence[row, column]), 6),
                },
                "base": {
                    "center_row": round(float(base_rows.mean()), 2),
                    "center_column": round(float((column + np.mean((base_columns - column + surface.shape[1] / 2) % surface.shape[1] - surface.shape[1] / 2)) % surface.shape[1]), 2),
                    "area_pixels": int(len(base_rows)),
                    "level": round(base_level, 6),
                    "boundary": [[int(y), int(x)] for y, x in boundary_points],
                },
                "height_above_base": round(float(filled[row, column] - base_level), 6),
            }
        )
        if metric_surface is not None:
            metric_base = metric_surface[base_rows, base_columns]
            spikes[-1]["tip"]["radial_height_meters"] = round(
                float(metric_surface[row, column]), 6
            )
            spikes[-1]["height_above_base_meters"] = round(
                float(metric_surface[row, column] - np.nanpercentile(metric_base, 10)), 6
            )

    edges = []
    width = surface.shape[1]
    for index, spike in enumerate(spikes):
        row, column = spike["tip"]["row"], spike["tip"]["column"]
        distances = []
        for other_index, other in enumerate(spikes):
            if index == other_index:
                continue
            dy = other["tip"]["row"] - row
            dx = abs(other["tip"]["column"] - column)
            dx = min(dx, width - dx)
            distances.append((float(np.hypot(dy, dx)), other_index))
        for distance, other_index in sorted(distances)[:3]:
            first, second = sorted((spike["id"], spikes[other_index]["id"]))
            edge = {"from": first, "to": second, "distance_pixels": round(distance, 3)}
            if edge not in edges:
                edges.append(edge)
    return {"shape": list(surface.shape), "spikes": spikes, "edges": edges}


def render_graph(surface: np.ndarray, graph: dict) -> np.ndarray:
    valid = np.isfinite(surface)
    low, high = np.nanpercentile(surface, (2, 98))
    gray = np.clip((np.nan_to_num(surface, nan=low) - low) * 255 / max(high - low, 1e-9), 0, 255)
    image = np.repeat(gray.astype(np.uint8)[..., None], 3, axis=2)
    image[~valid] = 0
    bases = np.zeros(surface.shape, dtype=bool)
    tips = np.zeros(surface.shape, dtype=bool)
    for spike in graph["spikes"]:
        boundary = np.asarray(spike["base"]["boundary"])
        bases[boundary[:, 0], boundary[:, 1]] = True
        tip = spike["tip"]
        tips[tip["row"], tip["column"]] = True
    image[ndimage.binary_dilation(bases, iterations=2)] = (0, 220, 255)
    image[ndimage.binary_dilation(tips, iterations=4)] = (255, 35, 35)
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("height_map", type=Path, help="height-normalized.npy")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-distance", type=int, default=18)
    parser.add_argument("--min-prominence", type=float, default=0.04)
    parser.add_argument("--pole-margin", type=float, default=0.06)
    args = parser.parse_args()
    surface = np.load(args.height_map)
    graph = extract_spikes(
        surface,
        min_distance=args.min_distance,
        min_prominence=args.min_prominence,
        pole_margin=args.pole_margin,
    )
    output = args.output or args.height_map.with_name("spikes.json")
    output.write_text(json.dumps(graph, indent=2))
    try:
        from . import project
    except ImportError:
        import project
    preview = output.with_suffix(".png")
    project.write_png(render_graph(surface, graph), preview)
    print(f"{len(graph['spikes'])} spikes: {output}, {preview}")


if __name__ == "__main__":
    main()
