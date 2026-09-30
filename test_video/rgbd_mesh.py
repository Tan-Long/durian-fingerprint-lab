#!/usr/bin/env python3
"""PROTOTYPE: can multi-frame LiDAR preserve individual durian spikes?"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from scipy import ndimage

from pattern_map import body_geometry, fruit_mask, write_png


def selected_frames(
    dataset: Path, video: Path, rows: int, start: int, period: int
) -> tuple[np.ndarray, int, float]:
    capture = cv2.VideoCapture(str(video))
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if start < 0 or period <= 0 or start + period >= count:
        capture.release()
        raise ValueError(f"rotation [{start}, {start + period}] is outside the {count}-frame video")
    intrinsics = np.loadtxt(dataset / "camera_matrix.csv", delimiter=",")
    sift, matcher = cv2.SIFT_create(nfeatures=2200, contrastThreshold=0.018), cv2.BFMatcher()

    def features(frame_index: int):
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok:
            raise RuntimeError(f"cannot read frame {frame_index}")
        frame = cv2.resize(frame, (640, 480))
        mask = fruit_mask(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).astype(np.uint8) * 255
        points, descriptors = sift.detectAndCompute(
            cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), mask
        )
        depth = cv2.imread(
            str(dataset / "depth" / f"{frame_index:06d}.png"), cv2.IMREAD_UNCHANGED
        ).astype(np.float32) / 1000
        confidence = cv2.imread(
            str(dataset / "confidence" / f"{frame_index:06d}.png"), cv2.IMREAD_UNCHANGED
        )
        return points, descriptors, depth, confidence

    def yz(data, indices):
        points, _, depth, confidence = data
        uv = np.array([point.pt for point in points])[indices] * np.array([256 / 640, 192 / 480])
        pixels = np.rint(uv).astype(int)
        inside = (
            (pixels[:, 0] >= 0)
            & (pixels[:, 0] < depth.shape[1])
            & (pixels[:, 1] >= 0)
            & (pixels[:, 1] < depth.shape[0])
        )
        z = np.zeros(len(pixels), np.float32)
        quality = np.zeros(len(pixels), np.uint8)
        z[inside] = depth[pixels[inside, 1], pixels[inside, 0]]
        quality[inside] = confidence[pixels[inside, 1], pixels[inside, 0]]
        valid = inside & (z > 0.15) & (z < 0.6) & (quality >= 1)
        fy, cy = intrinsics[1, 1] * 192 / 1440, intrinsics[1, 2] * 192 / 1440
        return np.column_stack(((uv[:, 1] - cy) * z / fy, z)), valid

    anchors = np.unique(np.append(np.arange(start, start + period, 30), start + period))
    previous, motion = features(int(anchors[0])), [0.0]
    for frame_index in anchors[1:]:
        current = features(int(frame_index))
        pairs = matcher.knnMatch(previous[1], current[1], k=2)
        matches = [first for first, second in pairs if first.distance < 0.72 * second.distance]
        left, left_ok = yz(previous, [item.queryIdx for item in matches])
        right, right_ok = yz(current, [item.trainIdx for item in matches])
        use = left_ok & right_ok
        transform = None
        if use.sum() >= 12:
            transform, _ = cv2.estimateAffinePartial2D(
                left[use],
                right[use],
                method=cv2.RANSAC,
                ransacReprojThreshold=0.004,
                maxIters=3000,
            )
        degrees = (
            0.0
            if transform is None
            else -np.degrees(np.arctan2(transform[1, 0], transform[0, 0]))
        )
        motion.append(motion[-1] + max(0.0, degrees))
        previous = current
    motion = np.asarray(motion)
    increments = np.diff(motion)
    moving = increments[increments > 0]
    typical = float(np.median(moving))
    # ponytail: 30-frame anchors cannot physically exceed 12° on this rig; use an encoder for other motors.
    limit = 12.0
    clean = increments.copy()
    for index in np.flatnonzero(increments > limit):
        nearby = increments[max(0, index - 2) : index + 3]
        nearby = nearby[(nearby > 0) & (nearby <= limit)]
        clean[index] = np.median(nearby) if len(nearby) else typical
    motion = np.concatenate(([0.0], np.cumsum(clean)))
    if motion[-1] < 180:
        raise RuntimeError(f"tracked only {motion[-1]:.1f} degrees of rotation")
    target = np.linspace(0, motion[-1], rows, endpoint=False)
    wanted = np.rint(np.interp(target, motion, anchors)).astype(int)
    capture.release()
    assert np.all(np.diff(wanted) >= 0) and wanted[-1] < start + period
    return wanted, count, float(motion[-1])


def scan_geometry(video: Path, wanted: np.ndarray, columns: int, depth_size: tuple[int, int]):
    capture = cv2.VideoCapture(str(video))
    bounds = np.zeros((len(wanted), 2), int)
    centers = np.zeros((len(wanted), depth_size[0]), np.float32)
    radius_profiles = np.zeros_like(centers)
    row = frame_index = 0
    while row < len(wanted):
        ok, frame = capture.read()
        if not ok:
            break
        if frame_index == wanted[row]:
            small = cv2.cvtColor(cv2.resize(frame, depth_size), cv2.COLOR_BGR2RGB)
            mask = fruit_mask(small)
            x0, x1, center, radius = body_geometry(mask)
            while row < len(wanted) and wanted[row] == frame_index:
                bounds[row] = (x0, x1)
                centers[row] = center
                radius_profiles[row] = radius
                row += 1
        frame_index += 1
    capture.release()
    if row != len(wanted):
        raise RuntimeError(f"geometry scan stopped at {row}/{len(wanted)}")
    x = np.linspace(
        np.median(bounds[:, 0]), np.median(bounds[:, 1]), columns, dtype=np.float32
    )
    xi = np.arange(depth_size[0])
    xs = np.broadcast_to(x, (len(wanted), columns)).copy()
    ys = np.stack([np.interp(x, xi, center) for center in centers]).astype(np.float32)
    radii = np.stack([np.interp(x, xi, radius) for radius in radius_profiles]).astype(np.float32)
    # ponytail: circular smoothing assumes one steady revolution; use tracked object poses if the turntable wobbles materially.
    return tuple(ndimage.gaussian_filter1d(item, 1.5, axis=0, mode="wrap") for item in (xs, ys, radii))


def sample_rgbd(dataset: Path, video: Path, wanted: np.ndarray, xs: np.ndarray, ys: np.ndarray):
    depth0 = cv2.imread(str(dataset / "depth" / f"{wanted[0]:06d}.png"), cv2.IMREAD_UNCHANGED)
    depth_height, depth_width = depth0.shape
    capture = cv2.VideoCapture(str(video))
    colors = np.zeros((*xs.shape, 3), np.float32)
    depths = np.zeros(xs.shape, np.float32)
    valid = np.zeros(xs.shape, bool)
    high_confidence = np.zeros(xs.shape, bool)
    row = frame_index = 0
    while row < len(wanted):
        ok, frame = capture.read()
        if not ok:
            break
        if frame_index == wanted[row]:
            depth = cv2.imread(str(dataset / "depth" / f"{frame_index:06d}.png"), cv2.IMREAD_UNCHANGED)
            confidence = cv2.imread(str(dataset / "confidence" / f"{frame_index:06d}.png"), cv2.IMREAD_UNCHANGED)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            while row < len(wanted) and wanted[row] == frame_index:
                map_x, map_y = xs[row][None], ys[row][None]
                sampled_depth = cv2.remap(depth.astype(np.float32), map_x, map_y, cv2.INTER_LINEAR)[0]
                sampled_confidence = cv2.remap(confidence, map_x, map_y, cv2.INTER_NEAREST)[0]
                rgb_x = map_x * rgb.shape[1] / depth_width
                rgb_y = map_y * rgb.shape[0] / depth_height
                colors[row] = cv2.remap(rgb, rgb_x, rgb_y, cv2.INTER_LINEAR)[0]
                depths[row] = sampled_depth / 1000
                valid[row] = (sampled_depth > 100) & (sampled_depth < 600)
                high_confidence[row] = sampled_confidence >= 1
                row += 1
        frame_index += 1
    capture.release()
    if row != len(wanted):
        raise RuntimeError(f"RGB-D scan stopped at {row}/{len(wanted)}")
    indices = ndimage.distance_transform_edt(~valid, return_distances=False, return_indices=True)
    depths = depths[tuple(indices)]
    return colors, depths, valid, high_confidence


def sample_rgb_nearest(
    video: Path,
    wanted: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    radii: np.ndarray,
    depth_size: tuple[int, int],
    atlas_width: int,
) -> np.ndarray:
    rows, axial_samples = xs.shape
    atlas_columns = np.arange(atlas_width)
    owners = np.rint(atlas_columns / atlas_width * rows).astype(int) % rows
    texture = np.zeros((axial_samples, atlas_width, 3), np.uint8)
    capture = cv2.VideoCapture(str(video))
    row = frame_index = 0
    while row < rows:
        ok, frame = capture.read()
        if not ok:
            break
        if frame_index == wanted[row]:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            columns = atlas_columns[owners == row]
            offset = (
                (columns / atlas_width - row / rows + 0.5) % 1 - 0.5
            ) * 2 * np.pi
            map_x = np.broadcast_to(xs[row], (len(columns), axial_samples))
            map_y = ys[row][None, :] + radii[row][None, :] * np.sin(offset)[:, None]
            sampled = cv2.remap(
                rgb,
                (map_x * rgb.shape[1] / depth_size[0]).astype(np.float32),
                (map_y * rgb.shape[0] / depth_size[1]).astype(np.float32),
                cv2.INTER_LINEAR,
            )
            texture[:, columns] = np.transpose(sampled, (1, 0, 2))
            row += 1
        frame_index += 1
    capture.release()
    if row != rows:
        raise RuntimeError(f"RGB slit-scan stopped at {row}/{rows}")
    return texture


def reconstruct(depths, xs, radii_px, intrinsics, depth_width: int):
    scale = depth_width / 1920
    fx, fy = intrinsics[0, 0] * scale, intrinsics[1, 1] * scale
    cx = intrinsics[0, 2] * scale
    center_depth = np.median(depths + radii_px * depths / fy, axis=0)
    center_depth = ndimage.gaussian_filter1d(center_depth, 4)
    silhouette_radius = np.median(radii_px * depths / fy, axis=0)
    silhouette_radius = ndimage.gaussian_filter1d(silhouette_radius, 4)
    radial = np.clip(
        center_depth[None, :] - depths,
        np.maximum(0.005, silhouette_radius * 0.55)[None, :],
        np.maximum(0.008, silhouette_radius * 1.45)[None, :],
    )
    axial = np.median((xs - cx) * depths / fx, axis=0)
    axial = ndimage.gaussian_filter1d(axial, 3)
    theta = np.arange(depths.shape[0])[:, None] / depths.shape[0] * 2 * np.pi
    vertices = np.stack(
        (
            np.broadcast_to(axial, radial.shape),
            radial * np.sin(theta),
            radial * np.cos(theta),
        ),
        axis=2,
    )
    return vertices, center_depth, silhouette_radius


def fuse_rgbd_bands(
    dataset: Path,
    video: Path,
    wanted: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    radii_px: np.ndarray,
    center_depth: np.ndarray,
    silhouette_radius: np.ndarray,
    intrinsics: np.ndarray,
    *,
    max_view_degrees: float,
    band_samples: int,
):
    depth0 = cv2.imread(str(dataset / "depth" / f"{wanted[0]:06d}.png"), cv2.IMREAD_UNCHANGED)
    depth_height, depth_width = depth0.shape
    scale = depth_width / 1920
    fy, cy = intrinsics[1, 1] * scale, intrinsics[1, 2] * scale
    rows, columns = xs.shape
    radial_sum = np.zeros((rows, columns), np.float32)
    weight_sum = np.zeros((rows, columns), np.float32)
    texture = np.zeros((rows, columns, 3), np.uint8)
    best_view = np.full((rows, columns), -np.inf, np.float32)
    support = np.zeros((rows, columns), np.uint16)
    offsets = np.deg2rad(np.linspace(-max_view_degrees, max_view_degrees, band_samples))
    axial_indexes = np.broadcast_to(np.arange(columns), (band_samples, columns))
    capture = cv2.VideoCapture(str(video))
    row = frame_index = 0
    while row < rows:
        ok, frame = capture.read()
        if not ok:
            break
        if frame_index == wanted[row]:
            depth = cv2.imread(
                str(dataset / "depth" / f"{frame_index:06d}.png"), cv2.IMREAD_UNCHANGED
            ).astype(np.float32) / 1000
            confidence = cv2.imread(
                str(dataset / "confidence" / f"{frame_index:06d}.png"), cv2.IMREAD_UNCHANGED
            )
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            fruit = fruit_mask(cv2.cvtColor(cv2.resize(frame, (depth_width, depth_height)), cv2.COLOR_BGR2RGB))
            while row < rows and wanted[row] == frame_index:
                map_x = np.broadcast_to(xs[row], (band_samples, columns)).astype(np.float32)
                map_y = (
                    ys[row][None, :] + radii_px[row][None, :] * np.sin(offsets)[:, None]
                ).astype(np.float32)
                depth_samples = cv2.remap(depth, map_x, map_y, cv2.INTER_LINEAR)
                quality = cv2.remap(confidence, map_x, map_y, cv2.INTER_NEAREST)
                fruit_samples = cv2.remap(
                    fruit.astype(np.uint8), map_x, map_y, cv2.INTER_NEAREST
                ).astype(bool)
                rgb_samples = cv2.remap(
                    rgb,
                    map_x * rgb.shape[1] / depth_width,
                    map_y * rgb.shape[0] / depth_height,
                    cv2.INTER_LINEAR,
                )
                point_y = (map_y - cy) * depth_samples / fy
                axis_y = (ys[row] - cy) * center_depth / fy
                relative_y = point_y - axis_y[None, :]
                relative_z = center_depth[None, :] - depth_samples
                radial = np.hypot(relative_y, relative_z)
                local_angle = np.arctan2(relative_y, relative_z)
                angle_indexes = np.mod(
                    np.rint((row / rows - local_angle / (2 * np.pi)) * rows), rows
                ).astype(int)
                valid = (
                    (depth_samples > 0.1)
                    & (depth_samples < 0.6)
                    & (quality >= 1)
                    & fruit_samples
                    & (relative_z > 0)
                    & (np.abs(local_angle) <= np.deg2rad(max_view_degrees * 1.25))
                    & (radial >= silhouette_radius[None, :] * 0.5)
                    & (radial <= silhouette_radius[None, :] * 1.5)
                )
                flat = (angle_indexes * columns + axial_indexes)[valid]
                values = radial[valid]
                weights = np.cos(local_angle[valid]) ** 16 * (quality[valid] + 1)
                np.add.at(radial_sum.ravel(), flat, values * weights)
                np.add.at(weight_sum.ravel(), flat, weights)
                np.add.at(support.ravel(), flat, 1)
                scores = np.cos(local_angle[valid]) ** 32 * (quality[valid] + 1)
                np.maximum.at(best_view.ravel(), flat, scores)
                winners = scores >= best_view.ravel()[flat] - 1e-7
                texture.reshape(-1, 3)[flat[winners]] = rgb_samples[valid][winners]
                row += 1
        frame_index += 1
    capture.release()
    if row != rows:
        raise RuntimeError(f"RGB-D fusion stopped at {row}/{rows}")
    valid = weight_sum > 0
    surface = np.divide(
        radial_sum, weight_sum, out=np.zeros_like(radial_sum), where=valid
    )
    distance, nearest = ndimage.distance_transform_edt(
        ~valid, return_distances=True, return_indices=True
    )
    fill = ~valid
    surface[fill] = surface[nearest[0][fill], nearest[1][fill]]
    texture[fill] = texture[nearest[0][fill], nearest[1][fill]]
    surface = ndimage.median_filter(
        np.concatenate((surface[-1:], surface, surface[:1])), size=3, mode="nearest"
    )[1:-1]
    return surface, texture, valid, support


def spike_relief(surface: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    angular = max(9, round(surface.shape[0] * 12 / 360) | 1)
    axial = max(7, round(surface.shape[1] * 0.05) | 1)
    axial_profile = np.median(surface, axis=0)
    frame_bias = np.median(surface - axial_profile[None, :], axis=1)
    corrected = surface - frame_bias[:, None]
    padded = np.concatenate((corrected[-angular:], corrected, corrected[:angular]))
    body = ndimage.percentile_filter(
        padded, 25, size=(angular, axial), mode="nearest"
    )
    body = ndimage.gaussian_filter(
        body, sigma=(angular / 4, axial / 4), mode="nearest"
    )[angular:-angular]
    relief = np.maximum(corrected - body - 0.0015, 0)
    relief[:, : axial // 2] = relief[:, -axial // 2 :] = 0
    return body, relief


def scalar_preview(values: np.ndarray, valid: np.ndarray) -> np.ndarray:
    ceiling = max(float(np.percentile(values[valid], 99.5)), 1e-9)
    gray = np.clip(values * 255 / ceiling, 0, 255).astype(np.uint8)
    color = cv2.cvtColor(cv2.applyColorMap(gray, cv2.COLORMAP_TURBO), cv2.COLOR_BGR2RGB)
    color[~valid] = 0
    return color


def circular_preview(image: np.ndarray, overlap_degrees: float = 30) -> np.ndarray:
    margin = max(1, round(image.shape[1] * overlap_degrees / 360))
    return np.concatenate((image[:, -margin:], image, image[:, :margin]), axis=1)


def write_obj(output: Path, vertices: np.ndarray, texture_name: str):
    rows, columns = vertices.shape[:2]
    lines = ["mtllib surface.mtl", "usemtl durian"]
    closed = np.concatenate((vertices, vertices[:1]), axis=0)
    for x, y, z in closed.reshape(-1, 3):
        lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")
    for row in range(rows + 1):
        for column in range(columns):
            lines.append(f"vt {column / (columns - 1):.7f} {1 - row / rows:.7f}")
    for row in range(rows):
        for column in range(columns - 1):
            a = row * columns + column + 1
            b, c, d = a + 1, a + columns, a + columns + 1
            lines.extend((f"f {a}/{a} {c}/{c} {b}/{b}", f"f {b}/{b} {c}/{c} {d}/{d}"))
    (output / "surface.obj").write_text("\n".join(lines) + "\n")
    (output / "surface.mtl").write_text(f"newmtl durian\nKd 1 1 1\nmap_Kd {texture_name}\n")


def render_mesh(vertices: np.ndarray, colors: np.ndarray, width: int = 1200, height: int = 800):
    points = vertices.reshape(-1, 3)
    rgb = colors.reshape(-1, 3)
    x, y, z = points.T
    x0, x1 = np.percentile(x, (0.5, 99.5))
    y0, y1 = np.percentile(y, (0.5, 99.5))
    scale = min(width * 0.86 / (x1 - x0), height * 0.82 / (y1 - y0))
    px = np.rint((x - (x0 + x1) / 2) * scale + width / 2).astype(int)
    py = np.rint(height / 2 - (y - (y0 + y1) / 2) * scale).astype(int)
    inside = (px >= 1) & (px < width - 1) & (py >= 1) & (py < height - 1)
    order = np.where(inside)[0][np.argsort(z[inside])]
    canvas = np.full((height, width, 3), 245, np.uint8)
    for offset_y in (-1, 0, 1):
        for offset_x in (-1, 0, 1):
            canvas[py[order] + offset_y, px[order] + offset_x] = rgb[order]
    return canvas


def run(args):
    dataset, output = Path(args.dataset), Path(args.output)
    video = dataset / "rgb.mp4"
    output.mkdir(parents=True, exist_ok=True)
    depth0 = cv2.imread(str(next((dataset / "depth").glob("*.png"))), cv2.IMREAD_UNCHANGED)
    depth_size = (depth0.shape[1], depth0.shape[0])
    if args.rgb_only:
        capture = cv2.VideoCapture(str(video))
        source_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        capture.release()
        if args.start < 0 or args.period <= 0 or args.start + args.period >= source_frames:
            raise ValueError("calibrated rotation is outside the video")
        wanted = np.rint(
            args.start + np.arange(args.rows) * args.period / args.rows
        ).astype(int)
        tracked_degrees = 360.0
    else:
        wanted, source_frames, tracked_degrees = selected_frames(
            dataset, video, args.rows, args.start, args.period
        )
    xs, ys, radii = scan_geometry(video, wanted, args.columns, depth_size)
    profile = np.median(radii, axis=0)
    body = np.flatnonzero(profile >= profile.max() * args.body_radius_ratio)
    start, stop = int(body[0]), int(body[-1]) + 1
    xs, ys, radii = xs[:, start:stop], ys[:, start:stop], radii[:, start:stop]
    if args.rgb_only:
        if len(np.unique(wanted)) != len(wanted):
            raise RuntimeError("RGB slit-scan selected a frame more than once")
        atlas_width = round(2 * np.pi * radii.max() * 1440 / depth_size[1])
        texture = sample_rgb_nearest(
            video, wanted, xs, ys, radii, depth_size, atlas_width
        )
        write_png(output / "body-texture-map.png", texture)
        write_png(output / "body-texture-map-circular-preview.png", circular_preview(texture))
        report = {
            "mode": "high-resolution RGB centerline slit-scan",
            "source": str(dataset / "rgb.mp4"),
            "source_resolution": [1920, 1440],
            "rotation_period_frames": args.period,
            "tracked_rotation_degrees_before_normalization": round(tracked_degrees, 2),
            "selected_frames": len(wanted),
            "unique_frames": len(np.unique(wanted)),
            "map_width": texture.shape[1],
            "map_height": texture.shape[0],
            "rgb_blending": False,
            "rgb_sources_per_map_pixel": 1,
            "depth_usage": "rotation tracking only; no depth values enter RGB pixels",
        }
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return
    colors, depths, valid, high_confidence = sample_rgbd(dataset, video, wanted, xs, ys)
    intrinsics = np.loadtxt(dataset / "camera_matrix.csv", delimiter=",")
    center_vertices, center_depth, silhouette_radius = reconstruct(
        depths, xs, radii, intrinsics, depth_size[0]
    )
    center_surface = np.linalg.norm(center_vertices[:, :, 1:], axis=2)
    fused_surface, _, fused_valid, support = fuse_rgbd_bands(
        dataset,
        video,
        wanted,
        xs,
        ys,
        radii,
        center_depth,
        silhouette_radius,
        intrinsics,
        max_view_degrees=args.max_view,
        band_samples=args.band_samples,
    )
    _, fused_relief = spike_relief(fused_surface)
    center_body, center_relief = spike_relief(center_surface)
    vertices = center_vertices
    texture = colors.astype(np.uint8)
    assert np.isfinite(vertices).all() and np.linalg.norm(vertices[:, :, 1:], axis=2).min() > 0
    texture_name = "depth-aligned-rgb-grid.png"
    write_png(output / texture_name, texture)
    # Human-facing layout: 360-degree angle runs left-to-right, stem-to-blossom runs top-to-bottom.
    wide = np.transpose(texture, (1, 0, 2))
    physical_ratio = float(
        2 * np.pi * np.median(np.linalg.norm(vertices[:, :, 1:], axis=2)) / np.ptp(vertices[:, :, 0])
    )
    wide = cv2.resize(wide, (round(wide.shape[0] * physical_ratio), wide.shape[0]), interpolation=cv2.INTER_LANCZOS4)
    write_png(output / "depth-aligned-rgb-wide-preview.png", wide)
    write_png(output / "depth-aligned-rgb-circular-preview.png", circular_preview(wide))
    center_valid = valid & high_confidence
    center_height_preview = scalar_preview(center_relief, center_valid)
    fused_height_preview = scalar_preview(fused_relief, fused_valid)
    radius_preview = scalar_preview(center_surface - center_surface.min(), center_valid)
    overlay = np.where(
        (center_relief > np.percentile(center_relief[center_valid], 75))[..., None],
        (texture.astype(np.float32) * 0.55 + center_height_preview * 0.45).astype(np.uint8),
        texture,
    )
    target_width = round(center_surface.shape[1] * physical_ratio)
    for name, image in (
        ("lidar-radius-map.png", radius_preview),
        ("spike-height-map.png", center_height_preview),
        ("fused-band-spike-height-map.png", fused_height_preview),
        ("depth-relief-overlay-preview.png", overlay),
    ):
        image = cv2.resize(
            np.transpose(image, (1, 0, 2)),
            (target_width, center_surface.shape[1]),
            interpolation=cv2.INTER_NEAREST,
        )
        write_png(output / name, image)
        if name in {"spike-height-map.png", "depth-relief-overlay-preview.png"}:
            write_png(
                output / name.replace(".png", "-circular-preview.png"),
                circular_preview(image),
            )
    np.save(output / "radial-surface-meters.npy", center_surface.T)
    np.save(output / "body-surface-meters.npy", center_body.T)
    np.save(output / "spike-height-meters.npy", center_relief.T)
    np.save(output / "fused-band-spike-height-meters.npy", fused_relief.T)
    angle_step = max(1, args.rows // args.mesh_rows)
    axial_step = max(1, center_surface.shape[1] // args.mesh_columns)
    mesh_vertices = vertices[::angle_step, ::axial_step]
    mesh_colors = texture[::angle_step, ::axial_step]
    write_png(output / "mesh-preview.png", render_mesh(mesh_vertices, mesh_colors))
    write_obj(output, mesh_vertices, texture_name)
    report = {
        "source": str(dataset),
        "source_frames": source_frames,
        "rotation_start_frame": args.start,
        "rotation_period_frames": args.period,
        "tracked_rotation_degrees_before_normalization": round(tracked_degrees, 2),
        "phase_model": "SIFT+LiDAR tracked motion normalized to one calibrated turn",
        "front_depth_band_degrees": args.max_view,
        "depth_samples_per_band": args.band_samples,
        "body_radius_ratio": args.body_radius_ratio,
        "pattern_map_width_to_height": round(physical_ratio, 3),
        "surface_rows": int(center_surface.shape[0]),
        "surface_columns": int(center_surface.shape[1]),
        "vertices": int(np.prod(mesh_vertices.shape[:2]) + mesh_vertices.shape[1]),
        "faces": int(mesh_vertices.shape[0] * (mesh_vertices.shape[1] - 1) * 2),
        "centerline_valid_lidar_fraction": round(float(valid.mean()), 4),
        "centerline_high_confidence_fraction": round(float(high_confidence.mean()), 4),
        "fused_lidar_coverage": round(float(fused_valid.mean()), 4),
        "median_observations_per_cell": int(np.median(support[fused_valid])),
        "canonical_depth_model": "one high-confidence centerline profile per tracked angle",
        "spike_height_p99_millimeters": round(
            float(np.percentile(center_relief[center_valid], 99) * 1000), 2
        ),
        "fused_band_spike_height_p99_millimeters": round(
            float(np.percentile(fused_relief[fused_valid], 99) * 1000), 2
        ),
        "seam": "single seam between the first and last turntable angle",
        "canonical_rgb_map": "../video-body-unwrap/body-texture-map.png",
        "depth_aligned_rgb_preview": "depth-aligned-rgb-wide-preview.png",
        "circular_rgb_preview": "depth-aligned-rgb-circular-preview.png",
        "depth_map": "spike-height-map.png",
        "circular_depth_preview": "spike-height-map-circular-preview.png",
        "fused_band_depth_map": "fused-band-spike-height-map.png",
        "depth_overlay_preview": "depth-relief-overlay-preview.png",
        "warning": "LiDAR RGB images are low-resolution diagnostics; never replace the canonical RGB map with them",
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="CAM-TURNTABLE-01")
    parser.add_argument("--output", default="processed/rgbd-mesh")
    parser.add_argument("--rows", type=int, default=720)
    parser.add_argument("--columns", type=int, default=1000)
    parser.add_argument("--mesh-rows", type=int, default=360)
    parser.add_argument("--mesh-columns", type=int, default=300)
    parser.add_argument("--max-view", type=float, default=22)
    parser.add_argument("--band-samples", type=int, default=41)
    parser.add_argument("--body-radius-ratio", type=float, default=0.7)
    parser.add_argument("--rgb-only", action="store_true")
    # Physical calibration knobs: this recording completes its first repeat at frame 2610.
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--period", type=int, default=2610)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
