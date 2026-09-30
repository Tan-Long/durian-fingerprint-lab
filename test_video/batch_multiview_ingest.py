#!/usr/bin/env python3
"""Build synchronized compact view banks from rig sessions that passed QC."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

import cv2
import numpy as np

from multiview_retrieval_logic import (
    compact,
    extract_features,
    geometric_match,
    project_features,
    train_projection,
    train_vocabulary,
    view_vector,
)
from pattern_map import fruit_mask


STATUS_FIELDS = [
    "order",
    "recorded_sample_id",
    "session_id",
    "stage",
    "progress_pct",
    "camera",
    "cam_tren_views",
    "cam_duoi_views",
    "message",
    "updated_at",
]

RESULT_FIELDS = [
    "order", "recorded_sample_id", "session_id", "status", "ready_for_search",
    "views_per_camera", "period_sec", "minimum_source_features",
    "maximum_angle_error_deg", "minimum_loop_inliers", "bank_bytes",
    "result_directory", "note",
]


class StatusLedger:
    """A resumable, atomically-written CSV status ledger."""

    def __init__(self, path: Path, source_rows: list[dict[str, str]]):
        self.path = path
        existing = {}
        if path.is_file():
            with path.open(encoding="utf-8-sig") as source:
                existing = {
                    row["session_id"]: row for row in csv.DictReader(source)
                }
        self.rows = []
        for source in source_rows:
            row = {
                "order": source["order"],
                "recorded_sample_id": source["recorded_sample_id"],
                "session_id": source["session_id"],
                "stage": "QUEUED",
                "progress_pct": "0",
                "camera": "",
                "cam_tren_views": "0",
                "cam_duoi_views": "0",
                "message": "",
                "updated_at": "",
            }
            row.update(existing.get(source["session_id"], {}))
            self.rows.append(row)
        self._write()

    def update(self, session_id: str, **changes: object) -> None:
        row = next(item for item in self.rows if item["session_id"] == session_id)
        row.update({key: str(value) for key, value in changes.items()})
        row["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._write()

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("w", newline="", encoding="utf-8-sig") as output:
            writer = csv.DictWriter(output, fieldnames=STATUS_FIELDS)
            writer.writeheader()
            writer.writerows(self.rows)
        temporary.replace(self.path)


def write_results_summary(output: Path, status_rows: list[dict[str, str]]) -> Path:
    path = output / "PROCESSING_RESULTS.csv"
    results = []
    for status in status_rows:
        target = output / "samples" / status["recorded_sample_id"] / status["session_id"]
        manifest_path = target / "manifest.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
        quality = manifest.get("quality_gate", {})
        banks = manifest.get("banks", {})
        results.append({
            "order": status["order"],
            "recorded_sample_id": status["recorded_sample_id"],
            "session_id": status["session_id"],
            "status": status["stage"],
            "ready_for_search": "YES" if status["stage"] == "READY" else "NO",
            "views_per_camera": manifest.get("views_per_camera", ""),
            "period_sec": manifest.get("revolution_period_sec", ""),
            "minimum_source_features": quality.get("minimum_source_features", ""),
            "maximum_angle_error_deg": quality.get("maximum_pair_angle_error_deg", ""),
            "minimum_loop_inliers": quality.get("minimum_camera_median_loop_non_dark_inliers", ""),
            "bank_bytes": sum(int(bank.get("bytes", 0)) for bank in banks.values()),
            "result_directory": str(target) if manifest else "",
            "note": status.get("message", ""),
        })
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8-sig") as destination:
        writer = csv.DictWriter(destination, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)
    temporary.replace(path)
    return path


def select_angle_frames(
    timestamps: np.ndarray,
    *,
    flash_timestamp: float,
    revolution_start_sec: float,
    revolution_duration_sec: float,
    camera_offset_deg: float = 0.0,
    views: int = 36,
) -> list[dict[str, float | int]]:
    """Select nearest source frames for shared physical surface angles."""
    timestamps = np.asarray(timestamps, np.float64)
    if len(timestamps) < 2 or revolution_duration_sec <= 0 or views <= 0:
        raise ValueError("timestamps, revolution duration and view count must be positive")
    selections = []
    for angle in np.arange(views, dtype=np.float64) * 360 / views:
        phase = (angle - camera_offset_deg) % 360
        target = flash_timestamp + revolution_start_sec + phase / 360 * revolution_duration_sec
        right = int(np.searchsorted(timestamps, target))
        candidates = [index for index in (right - 1, right) if 0 <= index < len(timestamps)]
        frame = min(candidates, key=lambda index: abs(timestamps[index] - target))
        error_ms = abs(float(timestamps[frame] - target)) * 1000
        selections.append(
            {
                "angle_deg": float(angle),
                "frame_index": frame,
                "target_timestamp": float(target),
                "timestamp_error_ms": error_ms,
                "angle_error_deg": error_ms / 1000 / revolution_duration_sec * 360,
            }
        )
    return selections


def detect_revolution_window(
    times_relative_to_flash: np.ndarray,
    motion: np.ndarray,
    *,
    flash_timestamp: float,
    rotations: int = 2,
) -> dict[str, float]:
    """Find the longest sustained motion window and divide it into revolutions."""
    times = np.asarray(times_relative_to_flash, np.float64)
    motion = np.asarray(motion, np.float64)
    if len(times) != len(motion) or len(times) < 3 or rotations <= 0:
        raise ValueError("motion samples and rotation count are invalid")
    step = float(np.median(np.diff(times)))
    low, high = np.percentile(motion, [10, 75])
    moving = motion > low + 0.35 * (high - low)

    # Bridge sub-second decoder/texture gaps, but not a real pause between turns.
    changes = np.diff(np.r_[True, moving, True].astype(np.int8))
    for start, end in zip(np.where(changes == -1)[0], np.where(changes == 1)[0]):
        if (end - start) * step <= 1.0:
            moving[start:end] = True

    changes = np.diff(np.r_[False, moving, False].astype(np.int8))
    runs = list(zip(np.where(changes == 1)[0], np.where(changes == -1)[0]))
    if not runs:
        raise RuntimeError("cannot find sustained turntable motion")
    start, end = max(runs, key=lambda run: run[1] - run[0])
    active_duration = float(times[end - 1] + step - times[start])
    if active_duration / rotations < 12:
        raise RuntimeError(f"rotation window is too short: {active_duration:.1f}s")
    return {
        "start_timestamp": float(flash_timestamp + times[start]),
        "active_duration_sec": active_duration,
        "revolution_duration_sec": active_duration / rotations,
    }


def detect_flash_frame(
    timestamps: np.ndarray, luminance: np.ndarray, *, search_seconds: float = 10.0
) -> dict[str, float | int | str]:
    """Locate a flash edge after camera startup, preferring light-off."""
    timestamps = np.asarray(timestamps, np.float64)
    luminance = np.asarray(luminance, np.float64)
    if len(timestamps) != len(luminance) or len(timestamps) < 2:
        raise ValueError("timestamp and luminance samples are invalid")
    end = int(np.searchsorted(timestamps, timestamps[0] + search_seconds, side="right"))
    start = max(1, int(np.searchsorted(timestamps, timestamps[0] + 0.5, side="left")))
    changes = np.diff(luminance[:end])
    candidates = changes[start - 1:]
    change_index = int(np.argmin(candidates)) + start - 1
    direction = "off"
    if -changes[change_index] < 5:
        change_index = int(np.argmax(candidates)) + start - 1
        direction = "on"
    if abs(changes[change_index]) < 5:
        raise RuntimeError("flash sync edge is not strong enough")
    edge = change_index + 1
    return {
        "frame_index": edge,
        "timestamp": float(timestamps[edge]),
        "luminance_drop": float(abs(changes[edge - 1])),
        "edge_direction": direction,
    }


def estimate_revolution_period(
    gray_frames: np.ndarray,
    timestamps: np.ndarray,
    *,
    start_timestamp: float,
    end_timestamp: float,
    minimum_sec: float = 17.0,
    maximum_sec: float = 24.0,
) -> float:
    """Find the lag where the rotating fruit texture best repeats."""
    frames = np.asarray(gray_frames, np.float32)
    timestamps = np.asarray(timestamps, np.float64)
    if len(frames) != len(timestamps) or len(frames) < 3:
        raise ValueError("frame and timestamp samples are invalid")
    step = float(np.median(np.diff(timestamps)))
    normalized = frames - frames.mean(axis=tuple(range(1, frames.ndim)), keepdims=True)
    candidates = []
    for lag in range(round(minimum_sec / step), round(maximum_sec / step) + 1):
        usable = (
            (timestamps[:-lag] >= start_timestamp)
            & (timestamps[:-lag] + lag * step <= end_timestamp)
        )
        if np.count_nonzero(usable) < 3:
            continue
        score = float(np.mean(np.abs(normalized[:-lag][usable] - normalized[lag:][usable])))
        candidates.append((score, lag))
    if not candidates:
        raise RuntimeError("cannot estimate revolution period")
    return min(candidates)[1] * step


def read_timestamps(path: Path) -> np.ndarray:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    key = next(name for name in rows[0] if "timestamp" in name.lower())
    return np.asarray([float(row[key]) for row in rows], np.float64)


def decode_gray(video: Path, width: int = 160, height: int = 120) -> np.ndarray:
    raw = subprocess.check_output(
        [
            "ffmpeg", "-v", "error", "-hwaccel", "videotoolbox", "-i", str(video),
            "-vf", f"scale={width}:{height},format=gray", "-fps_mode", "passthrough",
            "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1",
        ]
    )
    unit = width * height
    return np.frombuffer(raw[: len(raw) // unit * unit], np.uint8).reshape(-1, height, width)


def analyze_camera(camera: Path) -> dict:
    timestamps = read_timestamps(camera / "frame_transforms.csv")
    gray = decode_gray(camera / "rgb.mp4")
    if len(gray) != len(timestamps):
        raise RuntimeError(f"{camera.name}: decoded {len(gray)} frames for {len(timestamps)} timestamps")
    flash = detect_flash_frame(timestamps, gray.mean(axis=(1, 2)))
    stride = 3
    sampled = gray[::stride].astype(np.float32)
    sampled = sampled[:, 15:105, 20:140]
    normalized = sampled - sampled.mean(axis=(1, 2), keepdims=True)
    motion = np.mean(np.abs(normalized[1:] - normalized[:-1]), axis=(1, 2))
    motion_times = (timestamps[::stride][1:] + timestamps[::stride][:-1]) / 2
    window = detect_revolution_window(
        motion_times - float(flash["timestamp"]), motion,
        flash_timestamp=float(flash["timestamp"]), rotations=2,
    )
    period = estimate_revolution_period(
        gray[:, 15:105, 20:140], timestamps,
        start_timestamp=window["start_timestamp"],
        end_timestamp=window["start_timestamp"] + window["active_duration_sec"],
    )
    return {
        "timestamps": timestamps,
        "flash": flash,
        "start_relative_sec": window["start_timestamp"] - float(flash["timestamp"]),
        "active_duration_sec": window["active_duration_sec"],
        "period_sec": period,
    }


def decode_selected_frames(video: Path, indexes: list[int], size=(960, 720)) -> dict[int, np.ndarray]:
    wanted = set(indexes)
    maximum = max(wanted)
    capture = cv2.VideoCapture(str(video))
    decoded = {}
    for frame_index in range(maximum + 1):
        ok, frame = capture.read()
        if not ok:
            break
        if frame_index in wanted:
            decoded[frame_index] = cv2.cvtColor(cv2.resize(frame, size), cv2.COLOR_BGR2RGB)
    capture.release()
    missing = wanted - decoded.keys()
    if missing:
        raise RuntimeError(f"decoded frames missing: {sorted(missing)[:5]}")
    return decoded


def describe_frame(image: np.ndarray) -> dict:
    mask = fruit_mask(image)
    features = extract_features(image, mask)
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_32F)[mask].var())
    feature_count = len(features["points"])
    return {
        "image": image,
        "mask": mask,
        "features": features,
        "sharpness": sharpness,
        "feature_count": feature_count,
        "quality": feature_count + min(sharpness, 2400) * 0.25,
    }


def estimate_camera_azimuth(top: list[dict], bottom: list[dict]) -> dict:
    views = len(top)
    anchors = range(0, views, max(1, views // 6))
    scores = []
    for shift in range(-views // 2, views // 2):
        evidence = [
            geometric_match(top[index]["features"], bottom[(index + shift) % views]["features"])["non_dark_inliers"]
            for index in anchors
        ]
        scores.append((float(np.median(evidence)), int(np.sum(evidence)), shift))
    ranked = sorted(scores, reverse=True)
    best, second = ranked[:2]
    reliable = best[0] >= 6 and best[1] >= second[1] * 1.1
    shift = best[2] if reliable else 0
    return {
        "mode": "paired" if reliable else "independent",
        "camera_duoi_offset_deg": float(-shift * 360 / views),
        "best_median_non_dark_inliers": best[0],
        "best_total_non_dark_inliers": best[1],
        "runner_up_total_non_dark_inliers": second[1],
        "proposed_shift_bins": best[2],
    }


def first_loop_features(
    camera: Path, timing: dict, start_relative_sec: float, period_sec: float, views: int
) -> list[dict]:
    selected = select_angle_frames(
        timing["timestamps"], flash_timestamp=float(timing["flash"]["timestamp"]),
        revolution_start_sec=start_relative_sec, revolution_duration_sec=period_sec,
        views=views,
    )
    decoded = decode_selected_frames(camera / "rgb.mp4", [int(item["frame_index"]) for item in selected])
    return [describe_frame(decoded[int(item["frame_index"])]) for item in selected]


def build_camera_bank_inputs(
    camera: Path,
    timing: dict,
    *,
    start_relative_sec: float,
    period_sec: float,
    camera_offset_deg: float,
    views: int,
    progress=None,
) -> dict:
    loops = [
        select_angle_frames(
            timing["timestamps"], flash_timestamp=float(timing["flash"]["timestamp"]),
            revolution_start_sec=start_relative_sec + loop * period_sec,
            revolution_duration_sec=period_sec, camera_offset_deg=camera_offset_deg,
            views=views,
        )
        for loop in range(2)
    ]
    indexes = sorted({int(item["frame_index"]) for loop in loops for item in loop})
    decoded = decode_selected_frames(camera / "rgb.mp4", indexes)
    described = {}
    for position, frame_index in enumerate(indexes, 1):
        described[frame_index] = describe_frame(decoded[frame_index])
        if progress and (position % 12 == 0 or position == len(indexes)):
            progress(position, len(indexes))

    chosen, consistency = [], []
    for angle_index in range(views):
        candidates = []
        for loop_index, selections in enumerate(loops):
            selection = selections[angle_index]
            frame_index = int(selection["frame_index"])
            candidates.append({**selection, **described[frame_index], "loop": loop_index + 1})
        match = geometric_match(candidates[0]["features"], candidates[1]["features"])
        consistency.append(match["non_dark_inliers"])
        best = max(candidates, key=lambda item: item["quality"])
        best["loop_consistency_inliers"] = match["inliers"]
        best["loop_consistency_non_dark_inliers"] = match["non_dark_inliers"]
        chosen.append(best)
    return {
        "views": chosen,
        "median_loop_non_dark_inliers": float(np.median(consistency)),
        "minimum_loop_non_dark_inliers": int(min(consistency)),
    }


def save_shared_model(path: Path, feature_sets: list[dict]) -> dict:
    vocabulary = train_vocabulary(feature_sets)
    projection = train_projection(feature_sets)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        vocabulary=vocabulary.astype(np.float16),
        projection_mean=projection["mean"].astype(np.float16),
        projection_components=projection["components"].astype(np.float16),
        projection_scale=projection["scale"].astype(np.float16),
    )
    return {"vocabulary": vocabulary, "projection": projection}


def load_shared_model(path: Path) -> dict:
    data = np.load(path)
    return {
        "vocabulary": data["vocabulary"].astype(np.float32),
        "projection": {
            "mean": data["projection_mean"].astype(np.float32),
            "components": data["projection_components"].astype(np.float32),
            "scale": data["projection_scale"].astype(np.float32),
        },
    }


def save_bank(path: Path, bank: dict, model: dict) -> dict:
    views = bank["views"]
    full = [item["features"] for item in views]
    vectors = np.stack([view_vector(item["descriptors"], model["vocabulary"]) for item in full])
    projected = [project_features(compact(item), model["projection"], quantized=True) for item in full]
    counts = np.asarray([len(item["points"]) for item in projected], np.int16)
    scale = model["projection"]["scale"]
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        frame_indexes=np.asarray([item["frame_index"] for item in views], np.int32),
        angle_degrees=np.asarray([item["angle_deg"] for item in views], np.float32),
        selected_loops=np.asarray([item["loop"] for item in views], np.uint8),
        vectors=vectors.astype(np.float16),
        counts=counts,
        points=np.concatenate([item["points"] for item in projected]).astype(np.float16),
        descriptors=np.clip(
            np.rint(np.concatenate([item["descriptors"] for item in projected]) / scale),
            -127, 127,
        ).astype(np.int8),
        dark=np.concatenate([item["dark"] for item in projected]),
        source_feature_counts=np.asarray([item["feature_count"] for item in views], np.int16),
        sharpness=np.asarray([item["sharpness"] for item in views], np.float32),
        timestamp_error_ms=np.asarray([item["timestamp_error_ms"] for item in views], np.float32),
        loop_non_dark_inliers=np.asarray([item["loop_consistency_non_dark_inliers"] for item in views], np.int16),
    )
    self_index = int(np.argmax(vectors @ vectors[0]))
    self_match = geometric_match(projected[0], projected[self_index])
    if self_index != 0 or len(self_match["matches"]) < 100:
        raise RuntimeError(f"bank self-check failed at view {self_index}")
    return {"bytes": path.stat().st_size, "self_matches": len(self_match["matches"])}


def save_contact_sheet(path: Path, banks: dict) -> None:
    strips = []
    for camera in ("CAM_TREN", "CAM_DUOI"):
        thumbnails = []
        for item in banks[camera]["views"]:
            image = cv2.resize(item["image"], (160, 120))
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            cv2.putText(image, f'{item["angle_deg"]:.0f} L{item["loop"]}', (4, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 255), 1, cv2.LINE_AA)
            thumbnails.append(image)
        rows = [np.concatenate(thumbnails[index:index + 12], axis=1) for index in range(0, len(thumbnails), 12)]
        strips.append(np.concatenate(rows, axis=0))
    cv2.imwrite(str(path), np.concatenate(strips, axis=0), [cv2.IMWRITE_JPEG_QUALITY, 90])


def save_view_manifest(path: Path, banks: dict) -> None:
    fields = [
        "camera", "angle_deg", "frame_index", "selected_loop", "timestamp_error_ms",
        "angle_error_deg", "feature_count", "sharpness", "loop_inliers", "loop_non_dark_inliers",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for camera, bank in banks.items():
            for item in bank["views"]:
                writer.writerow({
                    "camera": camera,
                    "angle_deg": round(item["angle_deg"], 3),
                    "frame_index": item["frame_index"],
                    "selected_loop": item["loop"],
                    "timestamp_error_ms": round(item["timestamp_error_ms"], 3),
                    "angle_error_deg": round(item["angle_error_deg"], 3),
                    "feature_count": item["feature_count"],
                    "sharpness": round(item["sharpness"], 2),
                    "loop_inliers": item["loop_consistency_inliers"],
                    "loop_non_dark_inliers": item["loop_consistency_non_dark_inliers"],
                })


def process_session(root: Path, output: Path, row: dict, ledger: StatusLedger, views: int) -> dict:
    sample, session = row["recorded_sample_id"], row["session_id"]
    source = root / sample / session
    target = output / "samples" / sample / session
    target.mkdir(parents=True, exist_ok=True)
    ledger.update(session, stage="ANALYZING_SYNC", progress_pct=5, camera="BOTH", message="Tìm flash và chu kỳ quay")
    timing = {camera: analyze_camera(source / camera) for camera in ("CAM_TREN", "CAM_DUOI")}
    start_relative = float(np.median([item["start_relative_sec"] for item in timing.values()]))
    period = float(np.median([item["period_sec"] for item in timing.values()]))
    ledger.update(session, stage="CALIBRATING", progress_pct=20, camera="BOTH", message=f"Chu kỳ {period:.3f}s")

    calibration_path = output / "rig_calibration.json"
    if calibration_path.is_file():
        calibration = json.loads(calibration_path.read_text())
    else:
        top = first_loop_features(source / "CAM_TREN", timing["CAM_TREN"], start_relative, period, views)
        bottom = first_loop_features(source / "CAM_DUOI", timing["CAM_DUOI"], start_relative, period, views)
        calibration = estimate_camera_azimuth(top, bottom)
        calibration.update({"pilot_sample": sample, "pilot_session": session, "views": views})
        calibration_path.write_text(json.dumps(calibration, indent=2, ensure_ascii=False) + "\n")

    offsets = {"CAM_TREN": 0.0, "CAM_DUOI": float(calibration["camera_duoi_offset_deg"])}
    banks = {}
    for camera, base_progress in (("CAM_TREN", 30), ("CAM_DUOI", 55)):
        ledger.update(session, stage="EXTRACTING", progress_pct=base_progress, camera=camera, message="Đang trích đặc trưng hai vòng")
        def progress(done, total, camera=camera, base_progress=base_progress):
            ledger.update(
                session, stage="EXTRACTING", progress_pct=base_progress + round(done / total * 20),
                camera=camera, message=f"Ứng viên {done}/{total}",
            )
        banks[camera] = build_camera_bank_inputs(
            source / camera, timing[camera], start_relative_sec=start_relative,
            period_sec=period, camera_offset_deg=offsets[camera], views=views, progress=progress,
        )
        ledger.update(
            session, stage="EXTRACTED", progress_pct=base_progress + 20, camera=camera,
            **({"cam_tren_views": views} if camera == "CAM_TREN" else {"cam_duoi_views": views}),
            message=f"Đã chọn {views} view",
        )

    model_path = output / "shared_model.npz"
    selected_features = [item["features"] for bank in banks.values() for item in bank["views"]]
    ledger.update(session, stage="WRITING", progress_pct=85, camera="BOTH", message="Nén và kiểm tra bank")
    model = load_shared_model(model_path) if model_path.is_file() else save_shared_model(model_path, selected_features)
    saved = {
        camera: save_bank(target / f"{camera}.bank.npz", bank, model)
        for camera, bank in banks.items()
    }
    save_contact_sheet(target / "contact-sheet.jpg", banks)
    save_view_manifest(target / "view_selection.csv", banks)

    minimum_features = min(item["feature_count"] for bank in banks.values() for item in bank["views"])
    maximum_angle_error = max(item["angle_error_deg"] for bank in banks.values() for item in bank["views"])
    minimum_consistency = min(bank["median_loop_non_dark_inliers"] for bank in banks.values())
    ready = minimum_features >= 300 and maximum_angle_error <= 2.0 and minimum_consistency >= 5
    result = {
        "sample_id": sample,
        "session_id": session,
        "views_per_camera": views,
        "start_relative_to_flash_sec": start_relative,
        "revolution_period_sec": period,
        "calibration": calibration,
        "camera_timing": {
            camera: {
                "flash_frame": int(item["flash"]["frame_index"]),
                "flash_luminance_drop": item["flash"]["luminance_drop"],
                "flash_edge_direction": item["flash"]["edge_direction"],
                "start_relative_sec": item["start_relative_sec"],
                "period_sec": item["period_sec"],
            }
            for camera, item in timing.items()
        },
        "quality_gate": {
            "status": "READY" if ready else "REVIEW",
            "minimum_source_features": minimum_features,
            "maximum_pair_angle_error_deg": maximum_angle_error,
            "minimum_camera_median_loop_non_dark_inliers": minimum_consistency,
        },
        "banks": {
            camera: {
                **saved[camera],
                "median_loop_non_dark_inliers": bank["median_loop_non_dark_inliers"],
                "minimum_loop_non_dark_inliers": bank["minimum_loop_non_dark_inliers"],
            }
            for camera, bank in banks.items()
        },
    }
    (target / "manifest.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    final = result["quality_gate"]["status"]
    ledger.update(
        session, stage=final, progress_pct=100, camera="BOTH", cam_tren_views=views,
        cam_duoi_views=views,
        message=f"min_features={minimum_features}; angle_error={maximum_angle_error:.2f}°; loop={minimum_consistency:.1f}",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--sample")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--views", type=int, default=36)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    output = args.root / "processed_multiview_v1"
    with (args.root / "VIDEO_QUALITY_QC.csv").open(encoding="utf-8-sig") as source:
        passed = [row for row in csv.DictReader(source) if row["final_status"] == "PASS"]
    ledger = StatusLedger(output / "PROCESSING_STATUS.csv", passed)
    targets = passed if args.all else [row for row in passed if row["recorded_sample_id"] == args.sample]
    if not targets:
        raise SystemExit("choose --all or a PASS --sample")
    for row in targets:
        session = row["session_id"]
        current = next(item for item in ledger.rows if item["session_id"] == session)
        target = output / "samples" / row["recorded_sample_id"] / session
        complete = all((target / name).is_file() for name in ("CAM_TREN.bank.npz", "CAM_DUOI.bank.npz", "manifest.json"))
        if current["stage"] in ("READY", "REVIEW") and complete and not args.force:
            continue
        try:
            result = process_session(args.root, output, row, ledger, args.views)
            print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)
        except Exception as error:
            ledger.update(session, stage="FAILED", progress_pct=100, camera="", message=str(error)[:240])
            if not args.all:
                raise
            print(f'{row["recorded_sample_id"]}: {error}', flush=True)
    write_results_summary(output, ledger.rows)


if __name__ == "__main__":
    main()
