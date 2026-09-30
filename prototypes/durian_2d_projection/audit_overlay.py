#!/usr/bin/env python3
"""Project a reconstructed spike graph onto its source Scanner video."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy import ndimage

import heightmap
import project
import prototype_pattern_match as pattern_match


def project_points(
    points: np.ndarray,
    mesh: np.ndarray,
    angle: float,
    bounds: tuple[int, int, int, int],
) -> tuple[np.ndarray, np.ndarray]:
    center_x = (mesh[:, 0].min() + mesh[:, 0].max()) / 2
    center_z = (mesh[:, 2].min() + mesh[:, 2].max()) / 2
    cosine, sine = np.cos(angle), np.sin(angle)

    def rotate(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        x, z = values[:, 0] - center_x, values[:, 2] - center_z
        return x * cosine + z * sine, -x * sine + z * cosine

    mesh_x, _ = rotate(mesh)
    point_x, point_z = rotate(points)
    x0, y0, x1, y1 = bounds
    columns = x0 + (point_x - mesh_x.min()) * (x1 - x0) / max(float(np.ptp(mesh_x)), 1e-9)
    rows = y1 - (points[:, 1] - mesh[:, 1].min()) * (y1 - y0) / max(
        float(np.ptp(mesh[:, 1])), 1e-9
    )
    return np.column_stack((rows, columns)), point_z < 0


def graph_points(graph: dict, mesh: np.ndarray, surface: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    tip_rows = np.array([spike["tip"]["row"] for spike in graph["spikes"]])
    tip_columns = np.array([spike["tip"]["column"] for spike in graph["spikes"]])
    tips = heightmap.atlas_points(
        mesh, tip_rows, tip_columns, surface[tip_rows, tip_columns]
    )
    boundary = np.concatenate(
        [np.asarray(spike["base"]["boundary"], dtype=int) for spike in graph["spikes"]]
    )
    bases = heightmap.atlas_points(
        mesh, boundary[:, 0], boundary[:, 1], surface[boundary[:, 0], boundary[:, 1]]
    )
    return tips, bases


def fruit_bounds(mask: np.ndarray) -> tuple[int, int, int, int]:
    rows, columns = np.where(mask)
    return int(columns.min()), int(rows.min()), int(columns.max()), int(rows.max())


def fit_phase(
    frames: np.ndarray,
    masks: list[np.ndarray],
    tips: np.ndarray,
    mesh: np.ndarray,
) -> tuple[float, int, float]:
    evidence = []
    for frame, mask in zip(frames, masks):
        gray = frame.astype(np.float32).mean(axis=2)
        detail = ndimage.gaussian_filter(gray, 1) - ndimage.gaussian_filter(gray, 5)
        edges = ndimage.maximum_filter(np.hypot(ndimage.sobel(detail, 0), ndimage.sobel(detail, 1)), 7)
        edges /= np.percentile(edges[mask], 90) + 1e-6
        evidence.append(edges)

    best = (-np.inf, 0.0, 1)
    indexes = range(0, len(frames), max(1, len(frames) // 8))
    for direction in (-1, 1):
        for phase in np.deg2rad(np.arange(0, 360, 5)):
            scores = []
            for index in indexes:
                angle = phase + direction * index * 2 * np.pi / len(frames)
                pixels, visible = project_points(tips, mesh, angle, fruit_bounds(masks[index]))
                rows = np.rint(pixels[:, 0]).astype(int)
                columns = np.rint(pixels[:, 1]).astype(int)
                inside = visible & (rows >= 0) & (rows < frames.shape[1]) & (columns >= 0) & (columns < frames.shape[2])
                if inside.any():
                    scores.append(float(np.median(evidence[index][rows[inside], columns[inside]])))
            candidate = (float(np.mean(scores)), phase, direction)
            if candidate[0] > best[0]:
                best = candidate
    return best[1], best[2], best[0]


def draw(
    frame: np.ndarray,
    pixels: np.ndarray,
    visible: np.ndarray,
    color: tuple[int, int, int],
    radius: int,
    clip: np.ndarray,
) -> None:
    rows = np.rint(pixels[:, 0]).astype(int)
    columns = np.rint(pixels[:, 1]).astype(int)
    inside = visible & (rows >= 0) & (rows < frame.shape[0]) & (columns >= 0) & (columns < frame.shape[1])
    marks = np.zeros(frame.shape[:2], dtype=bool)
    marks[rows[inside], columns[inside]] = True
    marks = ndimage.binary_dilation(marks, iterations=radius) & clip
    frame[marks] = np.asarray(color, dtype=np.uint8)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--phase", type=float, help="manual longitude offset in degrees")
    parser.add_argument("--reverse", action="store_true")
    parser.add_argument("--samples", type=int, default=72)
    args = parser.parse_args()

    source = args.root / "CAM-TURNTABLE-01"
    output = args.root / "processed" / "spike-graph"
    sys.path.insert(0, str(args.root))
    from rgbd_mesh import selected_frames

    frame_indexes, _, _ = selected_frames(source, source / "rgb.mp4", args.samples, 0, 2610)
    capture = cv2.VideoCapture(str(source / "rgb.mp4"))
    frames, masks = [], []
    for frame_index in frame_indexes:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
        ok, frame = capture.read()
        if not ok:
            raise RuntimeError(f"cannot read frame {frame_index}")
        frame = cv2.cvtColor(cv2.resize(frame, (960, 720)), cv2.COLOR_BGR2RGB)
        depth = pattern_match.read_png(
            source / "depth" / f"{frame_index:06d}.png", "gray16le", "<u2"
        )
        frames.append(np.rot90(frame))
        masks.append(np.rot90(pattern_match.registration_mask(frame, depth)))
    capture.release()
    frames = np.asarray(frames)

    mesh, _ = heightmap.load_mesh(output / "durian.usdz")
    surface = np.load(output / "height-model-units.npy")
    graph = json.loads((output / "spikes.json").read_text())
    tips, bases = graph_points(graph, mesh, surface)
    if args.phase is None:
        phase, direction, score = fit_phase(frames, masks, tips, mesh)
    else:
        phase, direction, score = np.deg2rad(args.phase), (-1 if args.reverse else 1), -1.0

    video = output / "overlay-audit.mp4"
    encoder = subprocess.Popen(
        [
            "ffmpeg", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", "960x720", "-r", "12", "-i", "pipe:0", "-an", "-c:v", "libx264",
            "-crf", "18", "-pix_fmt", "yuv420p", "-y", str(video),
        ],
        stdin=subprocess.PIPE,
    )
    for index, (frame, mask) in enumerate(zip(frames, masks)):
        angle = phase + direction * index * 2 * np.pi / len(frames)
        bounds = fruit_bounds(mask)
        tip_pixels, tip_visible = project_points(tips, mesh, angle, bounds)
        base_pixels, base_visible = project_points(bases, mesh, angle, bounds)
        overlay = frame.copy()
        draw(overlay, base_pixels, base_visible, (0, 220, 255), 1, mask)
        draw(overlay, tip_pixels, tip_visible, (255, 35, 35), 3, mask)
        landscape = np.rot90(overlay, -1)
        if index in (0, len(frames) // 4, len(frames) // 2):
            project.write_png(landscape, output / f"overlay-frame-{index:03d}.png")
        encoder.stdin.write(np.ascontiguousarray(landscape).tobytes())
    encoder.stdin.close()
    if encoder.wait():
        raise RuntimeError("ffmpeg overlay encoding failed")

    report = {
        "phase_degrees": round(float(np.rad2deg(phase)), 1),
        "direction": direction,
        "fit_score": round(score, 4),
        "tips": len(graph["spikes"]),
        "legend": {"red": "tip", "cyan": "base boundary"},
    }
    (output / "overlay-report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    print(video)


if __name__ == "__main__":
    main()
