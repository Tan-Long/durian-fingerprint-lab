#!/usr/bin/env python3
"""Build a full-detail mesh and spike graph from a Scanner turntable capture."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

import heightmap
import project
import prototype_pattern_match as pattern_match
from spike_graph import extract_spikes, render_graph


HERE = Path(__file__).resolve().parent


def prepare_images(root: Path, output: Path, samples: int) -> int:
    source = root / "CAM-TURNTABLE-01"
    sys.path.insert(0, str(root))
    from rgbd_mesh import selected_frames

    frame_indexes, _, _ = selected_frames(source, source / "rgb.mp4", samples, 0, 2610)
    capture = cv2.VideoCapture(str(source / "rgb.mp4"))

    images = output / "images"
    images.mkdir(parents=True, exist_ok=True)
    for old in images.glob("*.png"):
        old.unlink()
    for index, frame_index in enumerate(frame_indexes):
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
        ok, frame = capture.read()
        if not ok:
            raise RuntimeError(f"cannot read RGB frame {frame_index}")
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        depth = pattern_match.read_png(
            source / "depth" / f"{frame_index:06d}.png", "gray16le", "<u2"
        )
        mask = pattern_match.registration_mask(frame, depth)
        frame, mask = np.rot90(frame), np.rot90(mask)
        masked = np.zeros((*frame.shape[:2], 4), dtype=np.uint8)
        masked[mask, :3] = frame[mask]
        masked[mask, 3] = 255
        project.write_png(masked, images / f"view-{index:03d}.png")
    capture.release()

    orbit = root / "CAM-ORBIT-01"
    orbit_capture = cv2.VideoCapture(str(orbit / "rgb.mp4"))
    orbit_count = int(orbit_capture.get(cv2.CAP_PROP_FRAME_COUNT))
    orbit_indexes = np.rint(
        np.linspace(orbit_count * 0.02, orbit_count * 0.98 - 1, max(24, samples // 2))
    ).astype(int)
    for offset, frame_index in enumerate(orbit_indexes, len(frame_indexes)):
        orbit_capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
        ok, frame = orbit_capture.read()
        if not ok:
            raise RuntimeError(f"cannot read orbit RGB frame {frame_index}")
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        depth = pattern_match.read_png(
            orbit / "depth" / f"{frame_index:06d}.png", "gray16le", "<u2"
        )
        mask = pattern_match.registration_mask(frame, depth)
        frame, mask = np.rot90(frame), np.rot90(mask)
        masked = np.zeros((*frame.shape[:2], 4), dtype=np.uint8)
        masked[mask, :3] = frame[mask]
        masked[mask, 3] = 255
        project.write_png(masked, images / f"view-{offset:03d}.png")
    orbit_capture.release()
    return len(frame_indexes) + len(orbit_indexes)


def reconstruct(images: Path, model: Path, detail: str) -> None:
    bridge = model.parent / "reconstruct"
    subprocess.run(
        ["swiftc", "-parse-as-library", str(HERE / "reconstruct.swift"), "-o", str(bridge)],
        check=True,
    )
    subprocess.run([str(bridge), str(images), str(model), detail], check=True)


def estimate_scale(root: Path, model: Path) -> float:
    source = root / "CAM-TURNTABLE-01"
    duration = float(project.probe(source / "rgb.mp4")["format"]["duration"])
    frame = project.decode_frames(source / "rgb.mp4", duration, width=1920, height=1440, samples=3)[1]
    depth_files = sorted((source / "depth").glob("*.png"))
    depth = pattern_match.read_png(depth_files[len(depth_files) // 2], "gray16le", "<u2")
    mask = pattern_match.registration_mask(frame, depth)
    rows, columns = np.where(mask)
    center = depth[62:130, 72:184]
    distance = float(np.median(center[(center > 0) & (center < 2_000)])) / 1_000
    camera = np.loadtxt(source / "camera_matrix.csv", delimiter=",")
    physical = np.array(
        [np.ptp(columns) * distance / camera[0, 0], np.ptp(rows) * distance / camera[1, 1]]
    )
    points, _ = heightmap.load_mesh(model)
    span = np.ptp(points, axis=0)
    model_size = np.array([span[1], max(span[0], span[2])])
    return float(np.median(physical / model_size))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="directory containing CAM-TURNTABLE-01")
    parser.add_argument("--samples", type=int, default=72)
    parser.add_argument("--detail", choices=("medium", "full"), default="full")
    parser.add_argument("--scale", type=float, help="meters per Object Capture model unit")
    parser.add_argument("--reuse-model", action="store_true")
    args = parser.parse_args()

    output = args.root / "processed" / "spike-graph"
    output.mkdir(parents=True, exist_ok=True)
    model = output / "durian.usdz"
    if not args.reuse_model:
        count = prepare_images(args.root, output, args.samples)
        model.unlink(missing_ok=True)
        print(f"reconstructing {count} full-resolution views", flush=True)
        reconstruct(output / "images", model, args.detail)
    elif not model.is_file():
        raise RuntimeError(f"missing model: {model}")
    heightmap.generate(model, output)

    surface = np.load(output / "height-normalized.npy")
    scale = args.scale or estimate_scale(args.root, model)
    metric_surface = np.load(output / "height-model-units.npy") * scale
    np.save(output / "height-meters.npy", metric_surface)
    graph = extract_spikes(surface, metric_surface=metric_surface)
    graph["source"] = str(model)
    graph["scale_meters_per_model_unit"] = scale
    (output / "spikes.json").write_text(json.dumps(graph, indent=2))
    project.write_png(render_graph(surface, graph), output / "spikes.png")
    print(
        f"{len(graph['spikes'])} spikes at scale {scale:.4f} m/unit: {output / 'spikes.json'}",
        flush=True,
    )


if __name__ == "__main__":
    main()
