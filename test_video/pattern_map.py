#!/usr/bin/env python3
"""Build and query a full-circumference durian thorn pattern map."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
import cv2
from scipy import ndimage


def read_image(path: Path, limit: int = 1200) -> np.ndarray:
    size = subprocess.check_output(
        ["magick", str(path), "-auto-orient", "-resize", f"{limit}x{limit}>", "-format", "%w %h", "info:"],
        text=True,
    ).split()
    width, height = map(int, size)
    raw = subprocess.check_output(
        ["magick", str(path), "-auto-orient", "-resize", f"{limit}x{limit}>", "-depth", "8", "rgb:-"]
    )
    return np.frombuffer(raw, np.uint8).reshape(height, width, 3)


def write_png(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.nan_to_num(image).clip(0, 255).astype(np.uint8)
    height, width = image.shape[:2]
    subprocess.run(
        ["magick", "-size", f"{width}x{height}", "-depth", "8", "rgb:-", str(path)],
        input=image.tobytes(),
        check=True,
    )


def fruit_mask(image: np.ndarray) -> np.ndarray:
    rgb = image.astype(np.float32) / 255
    high, low = rgb.max(2), rgb.min(2)
    saturation = (high - low) / np.maximum(high, 0.05)
    r, g, b = np.moveaxis(rgb, 2, 0)
    candidate = (saturation > 0.16) & (g > 0.58 * r) & (g > 0.82 * b) & (high > 0.12)
    candidate = ndimage.binary_closing(candidate, iterations=max(2, min(image.shape[:2]) // 250))
    labels, count = ndimage.label(candidate)
    if not count:
        raise ValueError("cannot find the durian")
    center = np.array(candidate.shape) / 2
    choices = []
    for label in range(1, count + 1):
        yy, xx = np.where(labels == label)
        if len(xx) < candidate.size * 0.01:
            continue
        distance = np.linalg.norm(np.array([yy.mean(), xx.mean()]) - center)
        choices.append((len(xx) / (1 + distance / min(candidate.shape)), label))
    if not choices:
        raise ValueError("durian region is too small")
    mask = labels == max(choices)[1]
    return ndimage.binary_fill_holes(ndimage.binary_closing(mask, iterations=4))


def body_geometry(mask: np.ndarray) -> tuple[int, int, np.ndarray, np.ndarray]:
    height, width = mask.shape
    top = np.full(width, height, dtype=int)
    bottom = np.full(width, -1, dtype=int)
    for x in np.where(mask.any(0))[0]:
        rows = np.where(mask[:, x])[0]
        top[x], bottom[x] = rows[0], rows[-1]
    thickness = np.maximum(0, bottom - top + 1)
    body = thickness > thickness.max() * 0.20
    labels, count = ndimage.label(body)
    if not count:
        raise ValueError("cannot estimate fruit axis")
    label = max(range(1, count + 1), key=lambda value: np.sum(labels == value))
    xs = np.where(labels == label)[0]
    x0, x1 = int(xs[0]), int(xs[-1])
    center = (top + bottom) / 2
    radius = thickness / 2
    center[x0 : x1 + 1] = ndimage.median_filter(center[x0 : x1 + 1], size=11, mode="nearest")
    radius[x0 : x1 + 1] = ndimage.median_filter(radius[x0 : x1 + 1], size=11, mode="nearest")
    return x0, x1, center, radius


def unwrap_on_geometry(
    image: np.ndarray,
    valid_mask: np.ndarray,
    geometry_mask: np.ndarray,
    width: int,
    height: int,
    low: float,
    high: float,
):
    x0, x1, center, radius = body_geometry(geometry_mask)
    x = np.linspace(x0, x1, width)
    delta = np.linspace(low, high, height)
    xi = np.rint(x).astype(int)
    xx = np.broadcast_to(x, (height, width))
    yy = center[xi][None, :] + radius[xi][None, :] * np.sin(delta[:, None])
    color = np.stack(
        [ndimage.map_coordinates(image[:, :, channel], (yy, xx), order=1, mode="constant") for channel in range(3)],
        axis=2,
    )
    valid = ndimage.map_coordinates(valid_mask.astype(np.uint8), (yy, xx), order=0, mode="constant") > 0
    return color.astype(np.float32), valid


def texture(image: np.ndarray) -> np.ndarray:
    gray = image @ np.array([0.299, 0.587, 0.114], np.float32)
    smooth = ndimage.gaussian_filter(gray, 1.0)
    gx = ndimage.sobel(smooth, axis=1)
    gy = ndimage.sobel(smooth, axis=0)
    return np.hypot(gx, gy)


def feature_bank(paths: list[Path]):
    sift = cv2.SIFT_create(nfeatures=4000, contrastThreshold=0.018)
    bank = []
    for path in paths:
        image = read_image(path, 1000)
        mask = fruit_mask(image)
        keypoints, descriptors = sift.detectAndCompute(
            cv2.cvtColor(image, cv2.COLOR_RGB2GRAY), (mask * 255).astype(np.uint8)
        )
        bank.append((image, mask, keypoints, descriptors))
    return sift, bank


def local_pose(query_path: Path, sift, bank):
    query = read_image(query_path, 1000)
    query_mask = fruit_mask(query)
    query_points, query_descriptors = sift.detectAndCompute(
        cv2.cvtColor(query, cv2.COLOR_RGB2GRAY), (query_mask * 255).astype(np.uint8)
    )
    matcher = cv2.BFMatcher()
    best = (0, float("inf"), 0, None)
    for index, (_, _, reference_points, reference_descriptors) in enumerate(bank):
        pairs = matcher.knnMatch(query_descriptors, reference_descriptors, k=2)
        good = [first for first, second in pairs if first.distance < 0.72 * second.distance]
        if len(good) < 6:
            continue
        source = np.float32([query_points[item.queryIdx].pt for item in good])
        target = np.float32([reference_points[item.trainIdx].pt for item in good])
        transform, inlier_mask = cv2.findHomography(source, target, cv2.RANSAC, 4.5)
        if transform is None or inlier_mask is None:
            continue
        inliers = int(inlier_mask.sum())
        if inliers < 4:
            continue
        predicted = cv2.perspectiveTransform(source[:, None], transform)[:, 0]
        selected = inlier_mask.ravel() > 0
        error = float(np.median(np.linalg.norm(predicted[selected] - target[selected], axis=1)))
        if (inliers, -error) > (best[0], -best[1]):
            best = inliers, error, index, transform
    return query, query_mask, best


def correlation(left: np.ndarray, right: np.ndarray, mask: np.ndarray) -> float:
    margin = np.zeros(mask.shape[1], bool)
    margin[int(mask.shape[1] * 0.08) : int(mask.shape[1] * 0.94)] = True
    mask = mask & margin[None, :]
    a, b = texture(left)[mask], texture(right)[mask]
    if len(a) < 100:
        return 0.0
    a = (a - a.mean()) / max(a.std(), 1e-6)
    b = (b - b.mean()) / max(b.std(), 1e-6)
    return float(np.mean(a * b))


def circular_band(atlas: np.ndarray, view_index: int, view_count: int, band_height: int) -> np.ndarray:
    center = round(view_index / view_count * atlas.shape[0])
    offsets = np.arange(band_height) - band_height // 2
    return atlas[(center + offsets) % atlas.shape[0]]


def align_uv_patch(atlas, query, mask, view_index, view_count):
    center = round(view_index / view_count * atlas.shape[0])
    search = max(2, round(atlas.shape[0] / view_count))
    best = (-2.0, center, query, mask, None)
    for flip in (False, True):
        candidate = query[::-1] if flip else query
        candidate_mask = mask[::-1] if flip else mask
        for offset in range(-search, search + 1):
            row = (center + offset) % atlas.shape[0]
            reference = circular_band(atlas, row, atlas.shape[0], query.shape[0])
            score = correlation(reference, candidate, candidate_mask)
            if score > best[0]:
                best = score, row, candidate, candidate_mask, reference
    return best


def run(args) -> None:
    views = sorted(Path(args.views).glob("*.jpg"))
    queries = sorted(Path(args.queries).glob("*"))
    queries = [path for path in queries if path.suffix.lower() in {".heic", ".jpg", ".jpeg", ".png"}]
    if len(views) < 12 or not queries:
        raise SystemExit("need at least 12 reference views and one query image")
    output = Path(args.output)
    sift, bank = feature_bank(views)
    # Small runnable guard: the pose stage must retrieve a registered view itself.
    _, _, check = local_pose(views[0], sift, bank)
    assert check[0] > 50 and check[2] == 0, "local-pose self-check failed"
    reference = read_image(Path(args.rgbd_texture), 2000)
    write_png(output / "reference-pattern-map.png", np.transpose(reference, (1, 0, 2)))
    results = []
    for query_path in queries:
        query_image, query_image_mask, pose = local_pose(query_path, sift, bank)
        inliers, reprojection_error, view_index, transform = pose
        reference_image, reference_mask = bank[view_index][:2]
        if transform is None:
            query = np.zeros((reference.shape[0] // 4, reference.shape[1], 3), np.float32)
            query_mask = np.zeros(query.shape[:2], bool)
            uv_score = 0.0
            reference_strip = np.zeros_like(query)
        else:
            size = (reference_image.shape[1], reference_image.shape[0])
            warped = cv2.warpPerspective(query_image, transform, size)
            warped_mask = cv2.warpPerspective((query_image_mask * 255).astype(np.uint8), transform, size) > 0
            band_height = reference.shape[0] // 4
            query, query_mask = unwrap_on_geometry(
                warped, warped_mask, reference_mask, reference.shape[1], band_height, -np.pi / 4, np.pi / 4
            )
            uv_score, uv_row, query, query_mask, reference_strip = align_uv_patch(
                reference, query, query_mask, view_index, len(views)
            )
        write_png(output / "projected" / f"{query_path.stem}.png", np.where(query_mask[:, :, None], query, 0))
        divider = np.full((query.shape[0], 8, 3), 255)
        write_png(
            output / "matches" / f"{query_path.stem}.png",
            np.concatenate((reference_strip, divider, np.where(query_mask[:, :, None], query, 0)), axis=1),
        )
        results.append(
            {
                "image": query_path.name,
                "reference_angle_degrees": round((uv_row if transform is not None else view_index / len(views) * reference.shape[0]) / reference.shape[0] * 360, 1),
                "local_geometric_inliers": inliers,
                "median_reprojection_error_px": None if not np.isfinite(reprojection_error) else round(reprojection_error, 2),
                "uv_texture_correlation": round(uv_score, 4),
                "strength": "strong" if inliers >= 15 else "medium" if inliers >= 8 else "weak",
            }
        )
    report = {
        "projection": "RGB-D mesh UV; query homography followed by a central ±45-degree UV patch",
        "reference_views": len(views),
        "rgbd_texture": str(args.rgbd_texture),
        "results": results,
        "warning": "Scores rank candidates only; same/different thresholds require negative fruit samples.",
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--views", default="processed/view-bank-hires")
    parser.add_argument("--rgbd-texture", default="processed/rgbd-mesh/surface-texture.png")
    parser.add_argument("--queries", default="img")
    parser.add_argument("--output", default="processed/uv-pattern")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
