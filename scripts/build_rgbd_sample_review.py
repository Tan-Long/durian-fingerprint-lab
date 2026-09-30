#!/usr/bin/env python3
"""Known-sample phone-to-frame alignment from both ORIGINAL RGB+LiDAR streams.

--image PHONE --session-dir ORIGINAL_SESSION --bank-session-dir BANK_SESSION
--output-dir output/NEW_NAME

Reads only cached frame_indexes/flash metadata, NEVER cached descriptors/models.
Fresh SIFT is extracted from original RGB with depth/confidence foreground masks.
At most 36 sampled frames per camera are tested, not every video frame. This is
alignment within a supplied sample, NOT dataset identification or accuracy.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test_video"))
from batch_multiview_ingest import decode_selected_frames
from multiview_retrieval_logic import extract_features, geometric_match
from pattern_map import fruit_mask, read_image
from query_multiview_banks import evidence_order
from scripts.build_fingerprint_visual_review import jpeg_media, new_output, overlay, provenance


def read_layers(camera_dir, frame_index, rgb, *, include_exterior=False):
    from scripts.rgbd_source_layers import read_depth_layers
    return read_depth_layers(camera_dir, frame_index, rgb, include_exterior=include_exterior)


def sampled_indexes(bank_path):
    with np.load(bank_path, allow_pickle=False) as bank:
        indexes = bank["frame_indexes"]
    if indexes.ndim != 1 or indexes.dtype.kind not in "iu" or not 1 <= len(indexes) <= 36 or (indexes < 0).any():
        raise ValueError("expected 1..36 nonnegative integer frame_indexes; no cached feature arrays are consumed")
    return sorted(set(map(int, indexes)))


def timestamps(path, indexes, flash_frame):
    wanted = set(indexes) | {flash_frame}
    found = {}
    with path.open(newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            index = int(row["frame"])
            if index in wanted:
                value = float(row["timestamp_unix"])
                if index in found or not np.isfinite(value):
                    raise ValueError("duplicate frame or nonfinite timestamp in frame_transforms.csv")
                found[index] = value
    if wanted != found.keys():
        raise ValueError(f"missing frame timestamps: {sorted(wanted - found.keys())}")
    return {index: {"timestamp_unix_recorded": found[index], "flash_frame_index": flash_frame,
                    "seconds_from_cached_light_edge": found[index] - found[flash_frame]}
            for index in indexes}


def flat_layer(rgb, rgba):
    if rgba.dtype != np.uint8 or rgba.shape != (*rgb.shape[:2], 4):
        raise ValueError("analytical layers must be uint8 RGBA in exact RGB coordinates")
    alpha = rgba[:, :, 3:4].astype(np.float32) / 255
    return np.rint(rgba[:, :, :3] * alpha + rgb * (1 - alpha)).astype(np.uint8)


def camera_alignment(camera_dir, bank_path, flash_frame, query):
    indexes = sampled_indexes(bank_path)
    timing_path = camera_dir / "frame_transforms.csv"
    timing = timestamps(timing_path, indexes, flash_frame)
    video = camera_dir / "rgb.mp4"
    sources = {"video": provenance(video), "sampling_bank": provenance(bank_path),
               "timing": provenance(timing_path)}
    frames = decode_selected_frames(video, indexes, size=(960, 720))
    results, best = [], None
    for index in indexes:
        rgb = frames[index]
        layers = read_layers(camera_dir, index, rgb)
        mask = layers["mask"]
        if mask.dtype != bool or mask.shape != rgb.shape[:2]:
            raise ValueError("depth foreground mask must be bool in exact RGB coordinates")
        reference = extract_features(rgb, mask)
        match = geometric_match(query, reference)
        row = {"camera": camera_dir.name, "frame_index": index, **timing[index],
               "reference_features": len(reference["points"]), "ratio_matches": len(match["matches"]),
               "geometric_inliers": match["inliers"], "non_dark_inliers": match["non_dark_inliers"],
               "median_epipolar_error_px": match["error"], "mask_stats": layers["stats"],
               "mask_sources": layers["sources"]}
        results.append(row)
        if best is None or evidence_order(row) + (index,) < evidence_order(best["row"]) + (best["row"]["frame_index"],):
            best = {"row": row, "rgb": rgb, "features": reference, "match": match, "mask": mask}
    for name, path in (("video", video), ("sampling_bank", bank_path), ("timing", timing_path)):
        if provenance(path)["sha256"] != sources[name]["sha256"]:
            raise ValueError(f"source changed during alignment: {path}")
    best["layers"] = read_layers(camera_dir, best["row"]["frame_index"], best["rgb"], include_exterior=True)
    if not np.array_equal(best["mask"], best["layers"]["mask"]):
        raise ValueError("winner mask changed between extraction and layer rendering")
    return results, best, sources


def build_pack(image_path, session_dir, bank_session_dir, output):
    started = time.perf_counter()
    sync_path = session_dir / "sync.json"
    manifest_path = bank_session_dir / "manifest.json"
    sync = json.loads(sync_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    if (sync["sample_id"], sync["session_id"]) != (manifest["sample_id"], manifest["session_id"]):
        raise ValueError("original session and sampling manifest identify different sample/session")
    if manifest["quality_gate"]["status"] != "READY":
        raise ValueError("sampling manifest must be READY; READY is not recognition accuracy")
    query_source = provenance(image_path)
    query_rgb = read_image(image_path, 1000)
    query = extract_features(query_rgb, fruit_mask(query_rgb))
    if not len(query["points"]):
        raise ValueError("query has no SIFT features")
    output = new_output(output)
    media = [jpeg_media(output, "rgbd-query", "Ảnh điện thoại độc lập — truy vấn cùng mẫu đã chọn", "query_photo", query_rgb,
                        {"original": query_source, "render": "auto-orient; maximum 1000px; no crop"})]
    candidates, winners, all_sources = [], [], {}
    labels = {"rgb": "RGB gốc", "mask": "Vùng foreground RGB + LiDAR", "depth": "Độ sâu LiDAR",
              "confidence": "Confidence LiDAR", "groove": "Rãnh bề mặt — proxy", "spike": "Gai bề mặt — proxy"}
    for camera in ("CAM_TREN", "CAM_DUOI"):
        flash_frame = int(manifest["camera_timing"][camera]["flash_frame"])
        rows, best, sources = camera_alignment(session_dir / camera, bank_session_dir / f"{camera}.bank.npz", flash_frame, query)
        candidates.extend(rows)
        all_sources[camera] = sources
        layer_data = best["layers"]
        common = {"sample_id": sync["sample_id"], "session_id": sync["session_id"], **best["row"],
                  "rgb_sources": sources, "depth_sources": layer_data["sources"],
                  "intrinsics": layer_data["intrinsics"], "reference_size_wh": [960, 720],
                  "query_source": query_source, "query_size_wh": [query_rgb.shape[1], query_rgb.shape[0]],
                  "timing_limit": "Per-camera recorded timestamp field; not verified UTC. Light-edge-relative time uses cached flash_frame, not a newly measured cross-camera calibration."}
        group = f"{camera}-{best['row']['frame_index']}"
        rgb_item = jpeg_media(output, f"rgbd-{group}-rgb", f"{camera}: frame {best['row']['frame_index']} — RGB gốc", "rgbd_layer", best["rgb"], common)
        rgb_item.update(layer_group=group, layer="rgb", layer_label=labels["rgb"])
        media.append(rgb_item)
        for name, rgba in layer_data["layers"].items():
            if name not in labels:
                continue
            item = jpeg_media(output, f"rgbd-{group}-{name}", f"{camera}: {labels[name]}", "rgbd_layer", flat_layer(best["rgb"], rgba), common)
            item.update(layer_group=group, layer=name, layer_label=labels[name])
            media.append(item)
        plotted, point_provenance = overlay(query_rgb, best["rgb"], query, best["features"], best["match"], f"{camera}: frame {best['row']['frame_index']} (known sample only)")
        media.append(jpeg_media(output, f"rgbd-{group}-matches", f"{camera}: ảnh ↔ frame — các cặp inlier", "match_overlay", plotted, {**common, **point_provenance}))
        winners.append({**common, **point_provenance})
    if provenance(image_path)["sha256"] != query_source["sha256"]:
        raise ValueError("query source changed during alignment")
    raw = {"mode": "known_sample_alignment", "sample_id": sync["sample_id"], "session_id": sync["session_id"],
           "identity_verdict": None, "confidence": None, "query_features": len(query["points"]),
           "query_source": query_source, "sampled_frames": candidates, "best_per_camera": winners,
           "elapsed_seconds": time.perf_counter() - started}
    return {"schema_version": 1, "review_kind": "core_code",
            "sources": {"fixture_only": False, "git_snapshot": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                        "mode": "known_sample_alignment", "query": query_source, "sync": provenance(sync_path),
                        "sampling_manifest": provenance(manifest_path), "cameras": all_sources,
                        "generator": provenance(Path(__file__)),
                        "limits": "Fresh RGB SIFT + coarse depth/confidence mask within ONE supplied sample, not dataset identification. No cached descriptors/encoder or inter-camera ARKit pose. Ink/tag leakage remains; non-dark counts are diagnostics, not proof of ink removal. Groove/spike layers are exterior proxies, not hidden-locule/aril/shell predictions."},
            "cases": [{"id": "rgbd-known-sample", "title": f"{sync['sample_id']}: ảnh điện thoại ↔ frame RGB + LiDAR hai camera",
                       "track": "fingerprint", "priority": "review", "sample_ids": [sync["sample_id"]],
                       "findings": ["Đối sánh trong đúng mẫu được cung cấp, KHÔNG phải nhận diện giữa nhiều trái; không thay thế kết quả tìm kiếm bank trước đó.",
                                    f"Đã trích SIFT mới từ {len(candidates)} frame được lấy mẫu của hai video RGB gốc, với mask từ depth/confidence gốc; không quét mọi frame.",
                                    "Hai camera giữ riêng. Thời gian tương đối theo cạnh đèn đã lưu; không coi timestamp thô hai thiết bị là cùng gốc.",
                                    "Chữ viết/thẻ cuống vẫn có thể ảnh hưởng ghép. Inlier hình học chưa chứng minh nhận đúng vân tay tự nhiên.",
                                    "Các lớp rãnh/gai chỉ mô tả bề mặt; không dự đoán hộc, múi hoặc độ dày vỏ bên trong."],
                       "questions": ["Ảnh điện thoại và frame tốt nhất từng camera có khớp bề mặt không? Kiểm tra cặp điểm và các lớp LiDAR."],
                       "facts": [{"label": "Phạm vi", "value": "Known-sample alignment; identity_verdict/confidence = null", "source": "explicit run contract"}],
                       "media": media, "result_tables": [{"title": "Frame tốt nhất mỗi camera", "columns": ["Camera / frame", "Inliers", "Không tối", "Sai số (px)", "Giây sau cạnh đèn"],
                                                            "rows": [[f"{r['camera']} / {r['frame_index']}", r["geometric_inliers"], r["non_dark_inliers"], r["median_epipolar_error_px"], r["seconds_from_cached_light_edge"]] for r in winners]}],
                       "raw_result": raw}]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("image", "session-dir", "bank-session-dir", "output-dir"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        pack = build_pack(args.image, args.session_dir, args.bank_session_dir, args.output_dir)
        path = args.output_dir.resolve() / "pack.json"
        with path.open("x", encoding="utf-8") as target:
            target.write(json.dumps(pack, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    except (OSError, ValueError, RuntimeError, KeyError, cv2.error, subprocess.CalledProcessError) as exc:
        print(f"RGBD sample review failed: {exc}; partial NEW output retained for inspection", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
