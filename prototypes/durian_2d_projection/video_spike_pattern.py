#!/usr/bin/env python3
"""PROTOTYPE: build a canonical tip/base graph from repeated video observations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

import cv2
import numpy as np
from scipy import ndimage

try:
    from . import project
    from .center_strip_map import cylindrical_band_atlas
    from .prototype_pattern_match import read_png, registration_mask
except ImportError:  # Direct script execution.
    import project
    from center_strip_map import cylindrical_band_atlas
    from prototype_pattern_match import read_png, registration_mask


def rotation_profile(
    masks: list[np.ndarray], body_radius_ratio: float = 0.7
) -> tuple[int, int, np.ndarray]:
    boxes = [project.bounds(mask) for mask in masks]
    axis_y = int(np.median([(box[1] + box[3]) / 2 for box in boxes]))
    samples = []
    for mask in masks:
        occupied = mask.any(axis=0)
        top = np.argmax(mask, axis=0).astype(float)
        bottom = mask.shape[0] - 1 - np.argmax(mask[::-1], axis=0).astype(float)
        radius = np.minimum(axis_y - top, bottom - axis_y)
        radius[~(occupied & (top <= axis_y) & (bottom >= axis_y))] = np.nan
        samples.append(radius)
    samples = np.stack(samples)
    measured = np.isfinite(samples).any(axis=0)
    radius = np.full(masks[0].shape[1], np.nan)
    radius[measured] = np.nanmedian(samples[:, measured], axis=0)
    reliable = np.isfinite(radius) & (radius > 20)
    labels, count = ndimage.label(reliable)
    if not count:
        raise RuntimeError("rotation profile failed")
    center_label = labels[masks[0].shape[1] // 2]
    if not center_label:
        sizes = ndimage.sum(reliable, labels, range(1, count + 1))
        center_label = int(np.argmax(sizes)) + 1
    xs = np.flatnonzero(labels == center_label)
    x0, x1 = int(xs[0]), int(xs[-1]) + 1
    profile = ndimage.gaussian_filter1d(
        np.interp(np.arange(x0, x1), xs, radius[xs]), 8
    )
    body = profile >= profile.max() * body_radius_ratio
    labels, count = ndimage.label(body)
    sizes = ndimage.sum(body, labels, range(1, count + 1))
    body_xs = np.flatnonzero(labels == int(np.argmax(sizes)) + 1)
    start, stop = int(body_xs[0]), int(body_xs[-1]) + 1
    return axis_y, x0 + start, profile[start:stop]


def phases_from_shifts(
    shifts: np.ndarray, radius: float, max_rotation_degrees: float
) -> tuple[np.ndarray, list[int]]:
    direction = np.sign(np.median(shifts[shifts != 0]))
    limit = radius * np.sin(np.deg2rad(max_rotation_degrees))
    valid = (shifts * direction >= 0) & (np.abs(shifts) <= limit)
    clean = shifts.copy()
    fallback = float(np.median(shifts[valid]))
    for index in np.flatnonzero(~valid):
        nearby = shifts[max(0, index - 2) : index + 3]
        nearby = nearby[(nearby * direction >= 0) & (np.abs(nearby) <= limit)]
        clean[index] = np.median(nearby) if len(nearby) else fallback
    increments = np.arcsin(np.clip(clean / radius, -0.95, 0.95))
    return np.concatenate(([0.0], np.cumsum(increments))), np.flatnonzero(~valid).tolist()


def registered_phases(
    frames: np.ndarray,
    *,
    axis_y: int,
    x0: int,
    radius: np.ndarray,
    tool: Path,
    temporary: Path,
    max_rotation_degrees: float,
) -> tuple[np.ndarray, list[int]]:
    half_height = min(200, axis_y, frames.shape[1] - axis_y)
    window = np.outer(np.hanning(2 * half_height), np.hanning(len(radius)))
    paths = []
    for index, frame in enumerate(frames):
        gray = frame[
            axis_y - half_height : axis_y + half_height,
            x0 : x0 + len(radius),
        ].mean(axis=2)
        detail = gray - ndimage.gaussian_filter(gray, 5)
        scale = np.percentile(np.abs(detail), 95)
        patch = np.clip(128 + detail * 70 / max(scale, 1) * window, 0, 255).astype(np.uint8)
        path = temporary / f"registration-{index:03d}.png"
        project.write_png(np.repeat(patch[..., None], 3, axis=2), path)
        paths.append(path)
    shifts = []
    for before, after in zip(paths, paths[1:]):
        _, vertical = map(float, project.run([str(tool), str(before), str(after)]).split())
        shifts.append(vertical)
    return phases_from_shifts(
        np.asarray(shifts), float(radius.max()), max_rotation_degrees
    )


def project_detection(
    detection: dict,
    *,
    frame_index: int,
    phase: float,
    axis_y: int,
    x0: int,
    radius: np.ndarray,
    map_width: int,
    max_view: float,
) -> dict | None:
    tip_y, tip_x = detection["tip"]
    axial = tip_x - x0
    if axial < 0 or axial >= len(radius):
        return None
    normalized = (axis_y - tip_y) / radius[axial]
    if abs(normalized) > np.sin(max_view):
        return None
    offset = float(np.arcsin(np.clip(normalized, -1, 1)))
    longitude = int(np.mod(phase + offset, 2 * np.pi) * map_width / (2 * np.pi))
    boundary = []
    for row, column in detection["base_boundary"]:
        base_axial = column - x0
        if 0 <= base_axial < len(radius):
            base_normalized = np.clip((axis_y - row) / radius[base_axial], -1, 1)
            base_longitude = int(
                np.mod(phase + np.arcsin(base_normalized), 2 * np.pi)
                * map_width
                / (2 * np.pi)
            )
            boundary.append([base_axial, base_longitude])
    frontness = float(np.cos(offset) ** 32)
    return {
        "tip": [axial, longitude],
        "base_boundary": boundary,
        "frame": frame_index,
        "quality": round(frontness * max(float(detection.get("tip_confidence", 1)), 0.1), 4),
    }


def merge_observations(
    candidates: list[dict], map_width: int, *, axial_tolerance: float = 14, angular_tolerance: float = 20
) -> list[dict]:
    parent = list(range(len(candidates)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(first: int, second: int) -> None:
        first, second = find(first), find(second)
        if first != second:
            parent[second] = first

    for first, one in enumerate(candidates):
        for second in range(first + 1, len(candidates)):
            two = candidates[second]
            if one["frame"] == two["frame"]:
                continue
            axial = abs(one["tip"][0] - two["tip"][0]) / axial_tolerance
            angular_raw = abs(one["tip"][1] - two["tip"][1])
            angular = min(angular_raw, map_width - angular_raw) / angular_tolerance
            if axial * axial + angular * angular <= 1:
                union(first, second)

    groups: dict[int, list[dict]] = {}
    for index, candidate in enumerate(candidates):
        groups.setdefault(find(index), []).append(candidate)
    merged = []
    for group in groups.values():
        winner = max(group, key=lambda item: item["quality"]).copy()
        winner["support_frames"] = len({item["frame"] for item in group})
        merged.append(winner)
    return merged


def vision_grooves(
    frame: np.ndarray,
    mask: np.ndarray,
    tool: Path,
    image_path: Path,
    contrast: float,
    smoothing: float,
    min_area: float,
) -> np.ndarray:
    result = np.zeros(mask.shape, dtype=bool)
    height, width = mask.shape
    tile_width = min(420, width)
    starts = (
        [0]
        if width == tile_width
        else sorted(
            set(range(0, width - tile_width + 1, tile_width - 80))
            | {width - tile_width}
        )
    )
    for start in starts:
        tile = frame[:, start : start + tile_width]
        project.write_png(tile, image_path)
        contours = json.loads(project.run([str(tool), str(image_path), str(contrast)]))
        for raw_points in contours:
            normalized = np.asarray(raw_points)
            points = np.column_stack(
                (
                    (1 - normalized[:, 1]) * (height - 1),
                    normalized[:, 0] * (tile.shape[1] - 1) + start,
                )
            )
            points = ndimage.gaussian_filter1d(points, smoothing, axis=0, mode="wrap")
            polygon_area = abs(
                np.dot(points[:, 1], np.roll(points[:, 0], 1))
                - np.dot(points[:, 0], np.roll(points[:, 1], 1))
            ) / 2
            if polygon_area < min_area:
                continue
            ends = np.roll(points, -1, axis=0)
            steps = np.maximum(np.abs(ends - points).max(axis=1).astype(int) + 1, 1)
            for offset in range(int(steps.max())):
                selected = offset < steps
                blend = (offset / steps[selected])[:, None]
                pixels = np.rint(
                    points[selected] + (ends[selected] - points[selected]) * blend
                ).astype(int)
                left = start + (0 if start == 0 else 3)
                right = start + tile.shape[1] - (0 if start + tile.shape[1] == width else 3)
                inside = (pixels[:, 1] >= left) & (pixels[:, 1] < right)
                result[pixels[inside, 0], pixels[inside, 1]] = True
    return result & mask


def project_binary(
    pixels: np.ndarray,
    *,
    phase: float,
    axis_y: int,
    x0: int,
    radius: np.ndarray,
    map_width: int,
    max_view: float,
) -> np.ndarray:
    rows, columns = np.where(pixels)
    axial = columns - x0
    inside = (axial >= 0) & (axial < len(radius))
    rows, axial = rows[inside], axial[inside]
    normalized = (axis_y - rows) / radius[axial]
    visible = np.abs(normalized) <= np.sin(max_view)
    axial, normalized = axial[visible], normalized[visible]
    longitude = (
        np.mod(phase + np.arcsin(normalized), 2 * np.pi)
        * map_width
        / (2 * np.pi)
    ).astype(int)
    result = np.zeros((len(radius), map_width), dtype=bool)
    result[axial, longitude] = True
    return result


def connect_grooves(grooves: np.ndarray) -> np.ndarray:
    connected = grooves.copy()
    fill = np.roll(grooves, 1, 1) & np.roll(grooves, -1, 1)
    fill[1:-1] |= grooves[:-2] & grooves[2:]
    fill[1:-1] |= np.roll(grooves[:-2], 1, 1) & np.roll(grooves[2:], -1, 1)
    fill[1:-1] |= np.roll(grooves[:-2], -1, 1) & np.roll(grooves[2:], 1, 1)
    connected[fill] = True
    return connected


def skeletonize(mask: np.ndarray) -> np.ndarray:
    structure = ndimage.generate_binary_structure(2, 1)
    skeleton = np.zeros_like(mask)
    remaining = mask.copy()
    while remaining.any():
        eroded = ndimage.binary_erosion(remaining, structure=structure)
        opened = ndimage.binary_dilation(eroded, structure=structure)
        skeleton |= remaining & ~opened
        remaining = eroded
    return skeleton


def render_pattern(observations: list[dict], grooves: np.ndarray) -> np.ndarray:
    height, width = grooves.shape
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[grooves] = (40, 230, 255)
    for observation in observations:
        row, column = observation["tip"]
        color = (255, 70, 40) if observation["support_frames"] >= 2 else (255, 170, 40)
        canvas[max(0, row - 3) : row + 4, column] = color
        canvas[row, (np.arange(column - 3, column + 4) % width)] = color
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--frames", type=int, default=48)
    parser.add_argument("--max-view", type=float, default=12)
    parser.add_argument("--body-radius-ratio", type=float, default=0.7)
    parser.add_argument("--vision-contrast", type=float, default=0.8)
    parser.add_argument("--contour-smoothing", type=float, default=1.2)
    parser.add_argument("--min-contour-area", type=float, default=50)
    parser.add_argument("--max-frame-rotation", type=float, default=20)
    parser.add_argument("--start-frame", type=int, default=58)
    parser.add_argument("--period-frames", type=int, default=2552)
    parser.add_argument("--output-name")
    parser.add_argument("--unwrap-only", action="store_true")
    args = parser.parse_args()

    source = args.root / "CAM-TURNTABLE-01"
    output = args.root / "processed" / (
        args.output_name
        or ("video-body-unwrap" if args.unwrap_only else "video-spike-pattern")
    )
    output.mkdir(parents=True, exist_ok=True)
    depth_files = sorted((source / "depth").glob("*.png"))
    if args.unwrap_only:
        if args.frames < 2:
            raise ValueError("unwrap needs at least two frames")
        depth_indexes = np.rint(
            args.start_frame
            + np.arange(args.frames) * args.period_frames / (args.frames - 1)
        ).astype(int)
        if len(np.unique(depth_indexes)) != len(depth_indexes) or depth_indexes[-1] >= len(depth_files):
            raise ValueError("calibrated frame range is invalid")
        capture = cv2.VideoCapture(str(source / "rgb.mp4"))
        decoded = []
        wanted_row = frame_index = 0
        while wanted_row < len(depth_indexes):
            ok, frame = capture.read()
            if not ok:
                break
            if frame_index == depth_indexes[wanted_row]:
                decoded.append(
                    cv2.cvtColor(
                        cv2.resize(frame, (1440, 1080), interpolation=cv2.INTER_AREA),
                        cv2.COLOR_BGR2RGB,
                    )
                )
                wanted_row += 1
            frame_index += 1
        capture.release()
        if len(decoded) != len(depth_indexes):
            raise RuntimeError(f"decoded {len(decoded)}/{len(depth_indexes)} calibrated frames")
        frames = np.stack(decoded)
    else:
        duration = float(project.probe(source / "rgb.mp4")["format"]["duration"])
        samples = args.frames + 4
        frames = project.decode_frames(
            source / "rgb.mp4", duration, width=960, height=720, samples=samples
        )[: args.frames]
        depth_indexes = np.linspace(
            len(depth_files) * 0.02, len(depth_files) * 0.98 - 1, samples
        ).round().astype(int)[: args.frames]
    masks = [
        registration_mask(frame, read_png(depth_files[index], "gray16le", "<u2"))
        for frame, index in zip(frames, depth_indexes)
    ]
    source_frames = len(frames)
    axis_y, x0, radius = rotation_profile(masks, args.body_radius_ratio)
    with tempfile.TemporaryDirectory(prefix="durian-registration-") as temporary:
        temporary = Path(temporary)
        registration_tool = temporary / "register-images"
        project.run(
            [
                "xcrun",
                "swiftc",
                str(Path(__file__).with_name("register_images.swift")),
                "-o",
                str(registration_tool),
            ]
        )
        phases, rejected_pairs = registered_phases(
            frames,
            axis_y=axis_y,
            x0=x0,
            radius=radius,
            tool=registration_tool,
            temporary=temporary,
            max_rotation_degrees=args.max_frame_rotation,
        )
    captured_motion = float(abs(phases[-1]))
    if args.unwrap_only:
        if captured_motion < np.pi:
            raise RuntimeError("RGB registration tracked less than half a turn")
        phases *= 2 * np.pi / captured_motion
        cycle_error = 0.0
    else:
        cycle_end = int(np.argmin(np.abs(np.abs(phases) - 2 * np.pi)))
        cycle_error = float(abs(abs(phases[cycle_end]) - 2 * np.pi))
        if cycle_end < 2 or cycle_error > np.deg2rad(25):
            raise RuntimeError("video does not contain one registered 360-degree turn")
        frames, masks = frames[: cycle_end + 1], masks[: cycle_end + 1]
        phases = np.linspace(
            0, np.sign(phases[cycle_end]) * 2 * np.pi, cycle_end + 1
        )
    axis_y, x0, radius = rotation_profile(masks, args.body_radius_ratio)
    _, full_x0, _ = rotation_profile(masks, 0)
    texture, valid_texture = cylindrical_band_atlas(
        frames,
        masks,
        max_view_degrees=args.max_view,
        phases=phases,
        seam=args.unwrap_only,
    )
    body_start = x0 - full_x0
    body_stop = body_start + len(radius)
    texture = texture[body_start:body_stop]
    valid_texture = valid_texture[body_start:body_stop]
    map_width = texture.shape[1]
    if args.unwrap_only:
        project.write_png(texture, output / "body-texture-map.png")
        report = {
            "frames": len(frames),
            "source_frames": source_frames,
            "map_width": map_width,
            "map_height": len(radius),
            "body_x_range": [x0, x0 + len(radius)],
            "texture_coverage": round(float(valid_texture.mean()), 4),
            "captured_motion_degrees": round(float(np.rad2deg(captured_motion)), 2),
            "cycle_end_error_degrees": round(float(np.rad2deg(cycle_error)), 2),
            "registration_rejected_pairs": rejected_pairs,
            "method": "registered RGB body unwrap only; no contour or spike detection",
        }
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return
    with tempfile.TemporaryDirectory(prefix="durian-contours-") as temporary:
        temporary = Path(temporary)
        contour_tool = temporary / "detect-contours"
        project.run(
            [
                "xcrun",
                "swiftc",
                str(Path(__file__).with_name("detect_contours.swift")),
                "-o",
                str(contour_tool),
            ]
        )
        groove_seen = np.zeros((len(radius), map_width), dtype=bool)
        for phase, frame, mask in zip(phases, frames, masks):
            local_mask = mask[:, x0 : x0 + len(radius)]
            local_edges = vision_grooves(
                frame[:, x0 : x0 + len(radius)],
                local_mask,
                contour_tool,
                temporary / "frame.png",
                args.vision_contrast,
                args.contour_smoothing,
                args.min_contour_area,
            )
            frame_edges = np.zeros(mask.shape, dtype=bool)
            frame_edges[:, x0 : x0 + len(radius)] = local_edges
            projected = project_binary(
                frame_edges,
                phase=float(phase),
                axis_y=axis_y,
                x0=x0,
                radius=radius,
                map_width=map_width,
                max_view=np.deg2rad(args.max_view),
            )
            groove_seen |= projected
        groove_map = connect_grooves(skeletonize(groove_seen))
    pattern = render_pattern([], groove_map)
    project.write_png(texture, output / "texture-map.png")
    project.write_png(render_pattern([], groove_map), output / "groove-map.png")
    project.write_png(pattern, output / "pattern-map.png")
    payload = {
        "frames": len(frames),
        "source_frames": source_frames,
        "map_width": map_width,
        "map_height": len(radius),
        "body_x_range": [x0, x0 + len(radius)],
        "body_radius_ratio": args.body_radius_ratio,
        "vision_contrast": args.vision_contrast,
        "contour_smoothing": args.contour_smoothing,
        "min_contour_area": args.min_contour_area,
        "max_frame_rotation": args.max_frame_rotation,
        "groove_pixel_fraction": round(float(groove_map.mean()), 4),
        "texture_coverage": round(float(valid_texture.mean()), 4),
        "captured_motion_degrees": round(float(np.rad2deg(captured_motion)), 2),
        "cycle_end_error_degrees": round(float(np.rad2deg(cycle_error)), 2),
        "registration_rejected_pairs": rejected_pairs,
        "method": "binary frame contours registered before cylindrical stitching",
        "spikes": [],
    }
    (output / "pattern.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "spikes"}, indent=2))


if __name__ == "__main__":
    main()
