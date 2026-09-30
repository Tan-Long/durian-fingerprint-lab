#!/usr/bin/env python3
"""PROTOTYPE: compact multi-view retrieval logic; delete or absorb after evaluation."""

from __future__ import annotations

import cv2
import numpy as np
from scipy import ndimage


def extract_features(image: np.ndarray, mask: np.ndarray, limit: int = 1600) -> dict:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    points, descriptors = cv2.SIFT_create(
        nfeatures=limit, contrastThreshold=0.014
    ).detectAndCompute(gray, (mask * 255).astype(np.uint8))
    if descriptors is None:
        return {"points": np.empty((0, 2)), "descriptors": np.empty((0, 128)), "responses": np.empty(0), "dark": np.empty(0, bool)}
    descriptors = descriptors.astype(np.float32)
    descriptors = np.sqrt(descriptors / np.maximum(descriptors.sum(1, keepdims=True), 1e-6))
    xy = np.asarray([point.pt for point in points], np.float32)
    dark = ndimage.binary_dilation((gray < 68) & mask, iterations=4)
    pixels = np.rint(xy).astype(int)
    pixels[:, 0] = np.clip(pixels[:, 0], 0, image.shape[1] - 1)
    pixels[:, 1] = np.clip(pixels[:, 1], 0, image.shape[0] - 1)
    return {
        "points": xy,
        "descriptors": descriptors,
        "responses": np.asarray([point.response for point in points], np.float32),
        "dark": dark[pixels[:, 1], pixels[:, 0]],
    }


def compact(features: dict, limit: int = 800) -> dict:
    take = np.argsort(features["responses"])[-limit:]
    return {key: value[take] for key, value in features.items()}


def train_projection(feature_sets: list[dict], dimensions: int = 32) -> dict:
    descriptors = np.concatenate([item["descriptors"] for item in feature_sets])
    if len(descriptors) > 16_000:
        descriptors = descriptors[
            np.random.default_rng(11).choice(len(descriptors), 16_000, replace=False)
        ]
    mean = descriptors.mean(0)
    _, _, vectors = np.linalg.svd(descriptors - mean, full_matrices=False)
    components = vectors[:dimensions]
    projected = (descriptors - mean) @ components.T
    projected /= np.maximum(np.linalg.norm(projected, axis=1, keepdims=True), 1e-6)
    scale = np.maximum(np.percentile(np.abs(projected), 99.5, axis=0) / 127, 1e-6)
    return {"mean": mean, "components": components, "scale": scale.astype(np.float32)}


def project_features(features: dict, projection: dict, quantized: bool) -> dict:
    descriptors = (features["descriptors"] - projection["mean"]) @ projection["components"].T
    descriptors /= np.maximum(np.linalg.norm(descriptors, axis=1, keepdims=True), 1e-6)
    if quantized:
        descriptors = (
            np.clip(np.rint(descriptors / projection["scale"]), -127, 127).astype(np.int8)
            * projection["scale"]
        )
        descriptors /= np.maximum(np.linalg.norm(descriptors, axis=1, keepdims=True), 1e-6)
    return {**features, "descriptors": descriptors.astype(np.float32)}


def train_vocabulary(feature_sets: list[dict], words: int = 64) -> np.ndarray:
    descriptors = np.concatenate([item["descriptors"] for item in feature_sets])
    if len(descriptors) > 16_000:
        descriptors = descriptors[np.random.default_rng(7).choice(len(descriptors), 16_000, replace=False)]
    cv2.setRNGSeed(7)
    _, _, vocabulary = cv2.kmeans(
        np.ascontiguousarray(descriptors),
        words,
        None,
        (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 24, 1e-4),
        1,
        cv2.KMEANS_PP_CENTERS,
    )
    return vocabulary


def view_vector(descriptors: np.ndarray, vocabulary: np.ndarray) -> np.ndarray:
    distances = (
        np.square(descriptors).sum(1, keepdims=True)
        + np.square(vocabulary).sum(1)[None]
        - 2 * descriptors @ vocabulary.T
    )
    histogram = np.bincount(np.argmin(distances, axis=1), minlength=len(vocabulary)).astype(np.float32)
    histogram = np.sqrt(histogram / max(histogram.sum(), 1))
    return histogram / max(np.linalg.norm(histogram), 1e-6)


def top_views(query: np.ndarray, bank: np.ndarray, count: int) -> tuple[np.ndarray, np.ndarray]:
    scores = bank @ query
    indexes = np.argsort(scores)[-count:][::-1]
    return indexes, scores[indexes]


def geometric_match(query: dict, reference: dict) -> dict:
    pairs = cv2.BFMatcher(cv2.NORM_L2).knnMatch(
        query["descriptors"], reference["descriptors"], k=2
    )
    good = [first for first, second in pairs if first.distance < 0.74 * second.distance]
    result = {"matches": good, "inlier_mask": np.zeros(len(good), bool), "inliers": 0, "non_dark_inliers": 0, "error": None, "visual_transform": None}
    if len(good) < 8:
        return result
    source = np.float32([query["points"][item.queryIdx] for item in good])
    target = np.float32([reference["points"][item.trainIdx] for item in good])
    fundamental, mask = cv2.findFundamentalMat(
        source, target, cv2.FM_RANSAC, 2.0, 0.999, 5000
    )
    if fundamental is None or fundamental.shape != (3, 3) or mask is None:
        return result
    selected = mask.ravel().astype(bool)
    if not selected.any():
        return result
    source_h = np.column_stack((source, np.ones(len(source))))
    target_h = np.column_stack((target, np.ones(len(target))))
    left_lines = (fundamental @ source_h.T).T
    right_lines = (fundamental.T @ target_h.T).T
    numerator = np.abs(np.sum(target_h * left_lines, axis=1))
    error = numerator * np.sqrt(
        1 / np.maximum(np.square(left_lines[:, :2]).sum(1), 1e-9)
        + 1 / np.maximum(np.square(right_lines[:, :2]).sum(1), 1e-9)
    )
    non_dark = np.asarray(
        [not query["dark"][item.queryIdx] and not reference["dark"][item.trainIdx] for item in good]
    )
    visual_transform, _ = cv2.findHomography(
        source[selected], target[selected], cv2.RANSAC, 6.0
    )
    result.update(
        inlier_mask=selected,
        inliers=int(selected.sum()),
        non_dark_inliers=int((selected & non_dark).sum()),
        error=float(np.median(error[selected])),
        visual_transform=visual_transform,
    )
    return result
