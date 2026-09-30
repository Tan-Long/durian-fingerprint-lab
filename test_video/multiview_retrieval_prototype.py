#!/usr/bin/env python3
"""PROTOTYPE: can a compact multi-view bank retrieve arbitrary phone views quickly?

Run: test_video/.venv/bin/python test_video/multiview_retrieval_prototype.py --batch

The fixed-camera/turntable video and the moving-camera/hanging-fruit video build
two separate banks. The HEIC photos query both, so their retrieval strength,
storage, and latency can be compared on the same fruit.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from multiview_retrieval_logic import compact, extract_features, geometric_match, project_features, top_views, train_projection, train_vocabulary, view_vector
from pattern_map import fruit_mask, read_image, write_png
from rgbd_mesh import selected_frames


def decode_frames(video: Path, wanted: np.ndarray, size=(960, 720)) -> list[np.ndarray]:
    capture = cv2.VideoCapture(str(video))
    frames = []
    row = frame_index = 0
    while row < len(wanted):
        ok, frame = capture.read()
        if not ok:
            break
        if frame_index == wanted[row]:
            frames.append(cv2.cvtColor(cv2.resize(frame, size), cv2.COLOR_BGR2RGB))
            row += 1
        frame_index += 1
    capture.release()
    if len(frames) != len(wanted):
        raise RuntimeError(f"decoded {len(frames)}/{len(wanted)} frames")
    return frames


def save_bank(path: Path, frame_indexes: np.ndarray, vectors: np.ndarray, vocabulary: np.ndarray, projection: dict, features: list[dict]) -> int:
    counts = np.asarray([len(item["points"]) for item in features], np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        frame_indexes=frame_indexes.astype(np.int32),
        vectors=vectors.astype(np.float16),
        vocabulary=vocabulary.astype(np.float16),
        projection_mean=projection["mean"].astype(np.float16),
        projection_components=projection["components"].astype(np.float16),
        projection_scale=projection["scale"].astype(np.float16),
        counts=counts,
        points=np.concatenate([item["points"] for item in features]).astype(np.float16),
        descriptors=np.clip(
            np.rint(
                np.concatenate([item["descriptors"] for item in features])
                / projection["scale"]
            ),
            -127,
            127,
        ).astype(np.int8),
        dark=np.concatenate([item["dark"] for item in features]),
    )
    return path.stat().st_size


def draw_overlay(query_image: np.ndarray, query_mask: np.ndarray, reference_image: np.ndarray, reference_mask: np.ndarray, transform: np.ndarray | None) -> np.ndarray:
    canvas = (reference_image * 0.35).astype(np.uint8)
    if transform is None:
        return canvas
    size = (reference_image.shape[1], reference_image.shape[0])
    warped = cv2.warpPerspective(query_image, transform, size)
    warped_mask = cv2.warpPerspective(
        (query_mask * 255).astype(np.uint8), transform, size, flags=cv2.INTER_NEAREST
    ) > 0
    overlap = warped_mask & reference_mask
    if overlap.any():
        adjusted = np.clip(
            warped.astype(np.float32)
            + reference_image[overlap].mean(0)
            - warped[overlap].mean(0),
            0,
            255,
        )
        canvas[overlap] = (
            reference_image[overlap].astype(np.float32) * 0.5
            + adjusted[overlap] * 0.5
        ).astype(np.uint8)
    return canvas


def query_record(name: str, image: np.ndarray, bank_name: str, bank: dict, vocabulary: np.ndarray, projection: dict, output: Path, top_k: int) -> dict:
    started = time.perf_counter()
    mask = fruit_mask(image)
    query = extract_features(image, mask)
    feature_ms = (time.perf_counter() - started) * 1000
    vector = view_vector(query["descriptors"], vocabulary)
    query = project_features(query, projection, quantized=False)
    search_started = time.perf_counter()
    indexes, coarse_scores = top_views(vector, bank["vectors"], top_k)
    search_ms = (time.perf_counter() - search_started) * 1000
    verify_started = time.perf_counter()
    candidates = []
    for index, coarse_score in zip(indexes, coarse_scores):
        match = geometric_match(query, bank["features"][index])
        candidates.append((match["inliers"], match["non_dark_inliers"], -float(match["error"] or 1e9), int(index), float(coarse_score), match))
    best = max(candidates)
    verify_ms = (time.perf_counter() - verify_started) * 1000
    _, _, _, index, coarse_score, match = best
    algorithm_ms = (time.perf_counter() - started) * 1000
    overlay_ok = match["inliers"] >= 15 and match["non_dark_inliers"] >= 4
    write_png(
        output / "overlays" / f"{name}--{bank_name}.png",
        draw_overlay(
            image, mask, bank["references"][index], bank["masks"][index],
            match["visual_transform"] if overlay_ok else None,
        ),
    )
    return {
        "query": name,
        "bank": bank_name,
        "features": len(query["points"]),
        "fruit_coverage": round(float(mask.mean()), 4),
        "matched_view": index,
        "reference_frame": int(bank["frame_indexes"][index]),
        "view_progress_degrees": round(index * 360 / len(bank["references"]), 1),
        "coarse_similarity": round(coarse_score, 4),
        "geometric_inliers": match["inliers"],
        "non_dark_inliers": match["non_dark_inliers"],
        "median_epipolar_error_px": None if match["error"] is None else round(match["error"], 2),
        "feature_ms": round(feature_ms, 1),
        "coarse_search_ms": round(search_ms, 3),
        "geometric_verify_ms": round(verify_ms, 1),
        "algorithm_ms": round(algorithm_ms, 1),
        "including_overlay_write_ms": round((time.perf_counter() - started) * 1000, 1),
        "overlay_passed_quality_gate": overlay_ok,
        "evidence": "strong" if match["non_dark_inliers"] >= 15 else "medium" if match["non_dark_inliers"] >= 8 else "weak",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", action="store_true")
    parser.add_argument("--views", type=int, default=36)
    parser.add_argument("--top-k", type=int, default=20)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    output = root / "processed" / "multiview-retrieval-prototype"
    output.mkdir(parents=True, exist_ok=True)

    turntable = root / "CAM-TURNTABLE-01"
    turntable_indexes, _, tracked = selected_frames(
        turntable, turntable / "rgb.mp4", args.views, 58, 2552
    )
    orbit = root / "CAM-ORBIT-01"
    capture = cv2.VideoCapture(str(orbit / "rgb.mp4"))
    orbit_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    capture.release()
    orbit_indexes = np.linspace(0, orbit_count - 2, args.views).round().astype(int)
    indexes_by_bank = {"turntable": turntable_indexes, "orbit": orbit_indexes}
    datasets = {"turntable": turntable, "orbit": orbit}
    banks = {}
    all_features = []
    for bank_name in datasets:
        frame_indexes = indexes_by_bank[bank_name]
        assert len(np.unique(frame_indexes)) == len(frame_indexes)
        references = decode_frames(datasets[bank_name] / "rgb.mp4", frame_indexes)
        masks = [fruit_mask(image) for image in references]
        full_features = [
            extract_features(image, mask) for image, mask in zip(references, masks)
        ]
        banks[bank_name] = {
            "frame_indexes": frame_indexes,
            "references": references,
            "masks": masks,
            "full_features": full_features,
        }
        all_features.extend(full_features)
    vocabulary = train_vocabulary(all_features)
    projection = train_projection(all_features)
    for bank_name, bank in banks.items():
        bank["vectors"] = np.stack(
            [view_vector(item["descriptors"], vocabulary) for item in bank["full_features"]]
        )
        bank["features"] = [
            project_features(compact(item), projection, quantized=True)
            for item in bank.pop("full_features")
        ]
        bank["bytes"] = save_bank(
            output / f"PROTOTYPE-{bank_name}-bank.npz",
            bank["frame_indexes"], bank["vectors"], vocabulary, projection,
            bank["features"],
        )
        self_indexes, _ = top_views(bank["vectors"][0], bank["vectors"], 1)
        self_match = geometric_match(
            bank["features"][0], bank["features"][int(self_indexes[0])]
        )
        assert int(self_indexes[0]) == 0 and len(self_match["matches"]) > 100

    queries = [(path.stem, read_image(path, 1000)) for path in sorted((root / "img").glob("*.HEIC"))]

    simulated = np.tile(banks["turntable"]["vectors"], (1000, 1))
    probe = view_vector(extract_features(queries[0][1], fruit_mask(queries[0][1]))["descriptors"], vocabulary)
    timings = []
    for _ in range(30):
        started = time.perf_counter(); top_views(probe, simulated, args.top_k); timings.append((time.perf_counter() - started) * 1000)

    results = []
    def run_one(index: int) -> None:
        name, image = queries[index]
        for bank_name, bank in banks.items():
            results.append(
                query_record(
                    name, image, bank_name, bank, vocabulary, projection, output,
                    args.top_k,
                )
            )

    if args.batch or not sys.stdin.isatty():
        for index in range(len(queries)):
            run_one(index)
    else:
        last = None
        while True:
            print("\033[2J\033[H", end="")
            print("\033[1mPROTOTYPE multi-view retrieval\033[0m")
            print(json.dumps({"banks": {name: {"views": len(bank["references"]), "bytes": bank["bytes"]} for name, bank in banks.items()}, "queries": [name for name, _ in queries], "last_result": last}, indent=2, ensure_ascii=False))
            command = input("\n[a] all  [1-9] query  [q] quit > ").strip().lower()
            if command == "q": break
            chosen = range(len(queries)) if command == "a" else [int(command) - 1] if command.isdigit() and 0 < int(command) <= len(queries) else []
            for index in chosen: run_one(index); last = results[-1]

    comparison = {
        bank_name: {
            "median_geometric_inliers": round(float(np.median([item["geometric_inliers"] for item in results if item["bank"] == bank_name])), 1),
            "max_geometric_inliers": max(item["geometric_inliers"] for item in results if item["bank"] == bank_name),
            "max_non_dark_inliers": max(item["non_dark_inliers"] for item in results if item["bank"] == bank_name),
            "median_algorithm_ms": round(float(np.median([item["algorithm_ms"] for item in results if item["bank"] == bank_name])), 1),
        }
        for bank_name in banks
    }
    report = {
        "prototype_question": "Which multi-view capture works better for arbitrary consumer photos: fixed camera + rotating fruit, or moving camera + hanging fruit?",
        "reference": {
            "fruit_count": 1,
            "views_per_bank": args.views,
            "turntable_tracked_degrees": round(tracked, 2),
            "banks": {
                name: {
                    "bank_bytes": bank["bytes"],
                    "estimated_mb_for_1000_fruits": round(bank["bytes"] * 1000 / 1_000_000, 1),
                }
                for name, bank in banks.items()
            },
        },
        "benchmark": {"simulated_views": len(simulated), "exact_vector_search_median_ms": round(float(np.median(timings)), 3), "local_verification_candidates": args.top_k},
        "comparison": comparison,
        "results": results,
        "limitations": ["Only one fruit is present, so false-positive rejection is untested.", "Black marker strokes remain in the data; non_dark_inliers is the stricter signal.", "These are two sequential capture styles, not the planned synchronized three-camera rig."],
    }
    (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
