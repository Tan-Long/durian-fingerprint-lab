#!/usr/bin/env python3
"""Query READY batch banks with their own encoders; emit diagnostic JSON to stdout.

Example (requires the existing Python dependencies and ImageMagick):
  python test_video/query_multiview_banks.py --image phone.HEIC \\
    --bank-root /Volumes/SoilTECH/DurianScan/27082026/processed_multiview_v1 \\
    --bank-root /Volumes/SoilTECH/DurianScan/28082026/processed_multiview_v1

Coarse shortlists are independent per root. Final rows show the best tested view
per root/sample/session/camera, sorted by geometric inliers, non-dark inliers,
then epipolar error. These are uncalibrated evidence, not identity decisions.
The existing color mask may include labels/background; this is not an accuracy
benchmark. No video decoding, model fitting, or writes to source banks occur.

Fruit ranking groups exact recorded sample IDs, not verified identities. Each
fruit retains its best geometric row and indexes into candidates for supporting
rows. Neither repeated views nor cross-encoder coarse scores boost fruit rank.

Batch mode: --batch queries.json replaces --image. The JSON must be a nonempty
array of {"query_id": "phone-1", "image": "phone.HEIC"}; relative image paths are
resolved against the JSON file's directory. IDs must be unique. Results/errors
and timings go to stdout; exit status is 2 if any query fails. No globbing occurs.
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
from pathlib import Path
import subprocess
import time
import zipfile

import cv2
import numpy as np

from multiview_retrieval_logic import extract_features, geometric_match, project_features, view_vector
from pattern_map import fruit_mask, read_image


def checked_array(data, key: str, shape: tuple, kinds: str) -> np.ndarray:
    array = data[key]
    if (array.dtype.kind not in kinds or array.ndim != len(shape)
            or any(size is not None and size != actual for size, actual in zip(shape, array.shape))
            or not np.isfinite(array).all()):
        raise ValueError(f"invalid {key}: shape={array.shape}, dtype={array.dtype}; expected {shape}, kind {kinds}, finite values")
    return array


def read_model(path: Path) -> dict:
    with np.load(path, allow_pickle=False) as data:
        vocabulary = checked_array(data, "vocabulary", (None, 128), "f").astype(np.float32)
        components = checked_array(data, "projection_components", (None, 128), "f").astype(np.float32)
        mean = checked_array(data, "projection_mean", (128,), "f").astype(np.float32)
        scale = checked_array(data, "projection_scale", (len(components),), "f").astype(np.float32)
    if not len(vocabulary) or not len(components) or (scale <= 0).any():
        raise ValueError("encoder requires nonempty vocabulary/components and positive projection_scale")
    return {"vocabulary": vocabulary, "projection": {"mean": mean, "components": components, "scale": scale}}


def read_bank(path: Path, model: dict, *, geometry: bool = False) -> dict:
    with np.load(path, allow_pickle=False) as data:
        counts = checked_array(data, "counts", (None,), "iu").astype(np.int64)
        if not len(counts) or (counts < 0).any():
            raise ValueError(f"{path}: counts must describe nonnegative feature counts for at least one view")
        views, features = len(counts), int(counts.sum())
        result = {
            "counts": counts,
            "vectors": checked_array(data, "vectors", (views, len(model["vocabulary"])), "f").astype(np.float32),
            "frame_indexes": checked_array(data, "frame_indexes", (views,), "iu"),
            "angle_degrees": checked_array(data, "angle_degrees", (views,), "f"),
        }
        if (result["frame_indexes"] < 0).any():
            raise ValueError(f"{path}: negative frame index")
        if geometry:
            descriptors = checked_array(data, "descriptors", (features, len(model["projection"]["scale"])), "i")
            if descriptors.dtype != np.int8:
                raise ValueError(f"{path}: descriptors must use batch bank int8 quantization")
            descriptors = descriptors.astype(np.float32) * model["projection"]["scale"]
            descriptors /= np.maximum(np.linalg.norm(descriptors, axis=1, keepdims=True), 1e-6)
            result.update(
                points=checked_array(data, "points", (features, 2), "f").astype(np.float32),
                descriptors=descriptors,
                dark=checked_array(data, "dark", (features,), "b"),
                offsets=np.concatenate(([0], np.cumsum(counts))),
            )
    return result


def evidence_order(row: dict) -> tuple:
    error = row["median_epipolar_error_px"]
    return (-row["geometric_inliers"], -row["non_dark_inliers"], float("inf") if error is None else error)


def candidate_order(row: dict) -> tuple:
    """Geometry first, then stable provenance only; never cross-encoder coarse scores."""
    return evidence_order(row) + tuple(row[key] for key in (
        "sample_id", "session_id", "camera", "bank_root", "bank_path", "view_index"))


def rank_fruits(candidates: list[dict]) -> list[dict]:
    """Group literal recorded IDs; supporting indexes refer to the supplied list."""
    grouped = {}
    for index, row in enumerate(candidates):
        grouped.setdefault(row["sample_id"], []).append(index)
    ranking = []
    for sample_id, indexes in grouped.items():
        indexes.sort(key=lambda index: candidate_order(candidates[index]))
        ranking.append({"sample_id": sample_id, "best_candidate": candidates[indexes[0]],
                        "supporting_candidate_indexes": indexes})
    ranking.sort(key=lambda row: candidate_order(row["best_candidate"]))
    return [{"rank": rank, **row} for rank, row in enumerate(ranking, 1)]


def query_banks(features: dict, roots: list[Path], top_k: int = 20) -> dict:
    """Keep at most top_k view references per encoder; load one feature bank at a time."""
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    report = {
        "query_features": len(features["points"]), "top_views_per_root": top_k,
        "identity_verdict": None,
        "notice": ("Uncalibrated geometric evidence. READY is ingest QC, not recognition accuracy. "
                   "Labels/background may influence matching. Fruit ranking groups exact recorded sample IDs, "
                   "not verified identities across collections. Provenance breaks geometric ties, not stronger evidence."),
        "roots": [], "candidates": [], "fruit_ranking": [],
    }
    if not len(features["descriptors"]):
        report["query_issue"] = "no query features"
        return report
    for root in dict.fromkeys(path.resolve() for path in roots):
        model_path = root / "shared_model.npz"
        try:
            model = read_model(model_path)
        except (OSError, ValueError, KeyError, TypeError, EOFError, zipfile.BadZipFile) as exc:
            raise ValueError(f"{model_path}: {exc}") from exc
        vector = view_vector(features["descriptors"], model["vocabulary"])
        projected = project_features(features, model["projection"], quantized=False)
        stats = {"bank_root": str(root), "encoder_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
                 "ready_sessions": 0, "skipped_sessions": 0, "banks": 0, "views": 0}
        shortlist = []
        manifests = sorted((root / "samples").glob("*/*/manifest.json"))
        if not manifests:
            raise ValueError(f"{root}: no samples/*/*/manifest.json files")
        # ponytail: linear scan of coarse vectors; add a persistent index if measured latency requires it.
        for manifest_path in manifests:
            try:
                manifest = json.loads(manifest_path.read_text())
                if manifest["quality_gate"]["status"] != "READY":
                    stats["skipped_sessions"] += 1
                    continue
                sample, session = manifest["sample_id"], manifest["session_id"]
                if not all(isinstance(value, str) and value for value in (sample, session)):
                    raise ValueError("sample_id/session_id must be nonempty strings")
                banks = manifest["banks"]
                if not isinstance(banks, dict) or not banks:
                    raise ValueError("READY manifest must list banks")
                stats["ready_sessions"] += 1
                for camera in sorted(banks):
                    bank_path = manifest_path.parent / f"{camera}.bank.npz"
                    if bank_path.resolve().parent != manifest_path.parent.resolve():
                        raise ValueError("bank camera must be a filename component")
                    bank = read_bank(bank_path, model)
                    stats["banks"] += 1
                    for index, score in enumerate(bank["vectors"] @ vector):
                        stats["views"] += 1
                        # Serial number resolves equal scores without comparing metadata dictionaries.
                        item = (float(score), stats["views"], str(bank_path), index, sample, session, camera)
                        heapq.heappush(shortlist, item)
                        if len(shortlist) > top_k:
                            heapq.heappop(shortlist)
            except (OSError, ValueError, KeyError, TypeError, EOFError, zipfile.BadZipFile) as exc:
                raise ValueError(f"{manifest_path}: {exc}") from exc
        if not shortlist:
            raise ValueError(f"{root}: no READY bank views")
        ranked = sorted(shortlist, reverse=True)
        by_bank = {}
        for rank, item in enumerate(ranked, 1):
            by_bank.setdefault(item[2], []).append((rank, item))
        for bank_path, selected in by_bank.items():
            try:
                bank = read_bank(Path(bank_path), model, geometry=True)
            except (OSError, ValueError, KeyError, TypeError, EOFError, zipfile.BadZipFile) as exc:
                raise ValueError(f"{bank_path}: {exc}") from exc
            candidates = []
            for rank, (score, _, _, index, sample, session, camera) in selected:
                start, stop = bank["offsets"][index:index + 2]
                reference = {key: bank[key][start:stop] for key in ("points", "descriptors", "dark")}
                match = geometric_match(projected, reference)
                candidates.append({
                    "bank_root": str(root), "sample_id": sample, "session_id": session,
                    "camera": camera, "bank_path": bank_path, "view_index": index,
                    "frame_index": int(bank["frame_indexes"][index]), "angle_degrees": float(bank["angle_degrees"][index]),
                    "coarse_rank_within_root": rank, "coarse_similarity_within_root": score,
                    "ratio_matches": len(match["matches"]), "geometric_inliers": match["inliers"],
                    "non_dark_inliers": match["non_dark_inliers"], "median_epipolar_error_px": match["error"],
                    "tested_views_in_camera": len(selected),
                })
            report["candidates"].append(min(candidates, key=candidate_order))
        report["roots"].append(stats)
    report["candidates"].sort(key=candidate_order)
    report["fruit_ranking"] = rank_fruits(report["candidates"])
    return report


def query_image(path: Path, roots: list[Path], top_k: int = 20) -> dict:
    started = time.perf_counter()
    image = read_image(path, 1000)
    mask = fruit_mask(image)
    report = query_banks(extract_features(image, mask), roots, top_k)
    report.update(image=str(path.resolve()), fruit_coverage=float(mask.mean()),
                  elapsed_seconds=time.perf_counter() - started)
    return report


def read_batch(path: Path) -> list[dict]:
    items = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(items, list) or not items:
        raise ValueError("batch must be a nonempty JSON array of {query_id, image}")
    seen = set()
    queries = []
    for index, item in enumerate(items):
        if (not isinstance(item, dict) or set(item) != {"query_id", "image"}
                or any(not isinstance(item[key], str) or not item[key].strip()
                       or "\x00" in item[key] for key in ("query_id", "image"))):
            raise ValueError(f"batch item {index}: requires exactly nonempty string query_id and image")
        if item["query_id"] in seen:
            raise ValueError(f"batch item {index}: duplicate query_id {item['query_id']!r}")
        seen.add(item["query_id"])
        image_path = Path(item["image"])
        if not image_path.is_absolute():
            image_path = path.resolve().parent / image_path
        queries.append({"query_id": item["query_id"], "image": str(image_path.resolve())})
    return queries


QUERY_ERRORS = (OSError, ValueError, KeyError, cv2.error, subprocess.CalledProcessError)


def query_batch(queries: list[dict], roots: list[Path], top_k: int = 20) -> dict:
    started = time.perf_counter()
    results = []
    for query in queries:
        query_started = time.perf_counter()
        row = {"query_id": query["query_id"], "image": query["image"]}
        try:
            row.update(status="ok", result=query_image(Path(query["image"]), roots, top_k))
        except QUERY_ERRORS as exc:
            row.update(status="error", error={"type": type(exc).__name__, "message": str(exc)})
        row["elapsed_seconds"] = time.perf_counter() - query_started
        results.append(row)
    return {"queries": results, "elapsed_seconds": time.perf_counter() - started,
            "identity_verdict": None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", type=Path)
    source.add_argument("--batch", type=Path, help="JSON array of explicit query_id/image pairs")
    parser.add_argument("--bank-root", type=Path, action="append", required=True)
    parser.add_argument("--top-k", type=int, default=20, help="candidate views per root encoder (default: 20)")
    args = parser.parse_args()
    if args.top_k <= 0:
        parser.error("--top-k must be positive")
    try:
        if args.batch is not None:
            report = query_batch(read_batch(args.batch), args.bank_root, args.top_k)
        else:
            report = query_image(args.image, args.bank_root, args.top_k)
    except QUERY_ERRORS as exc:
        parser.exit(2, f"query failed: {exc}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    if args.batch is not None and any(row["status"] == "error" for row in report["queries"]):
        parser.exit(2)


if __name__ == "__main__":
    main()
