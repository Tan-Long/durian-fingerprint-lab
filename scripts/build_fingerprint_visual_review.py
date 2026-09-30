#!/usr/bin/env python3
"""Build one real, UNVERIFIED fingerprint diagnostic from an explicit phone photo.

Run with the existing test_video environment, --image PATH, repeatable
--bank-root PATH and --output-dir output/NEW_NAME.
Only a new directory below this checkout's output/ is permitted. Reads existing
banks and up to three selected video prefixes; no fitting or source writes.
Reference coordinates match ingest: zero-based frame, RGB resize to 960x720,
without cropping. Query coordinates use the existing auto-oriented 1000px loader.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "test_video"))
from batch_multiview_ingest import decode_selected_frames
from multiview_retrieval_logic import extract_features, geometric_match, project_features
from pattern_map import fruit_mask, read_image
from query_multiview_banks import query_banks, read_bank, read_model

def provenance(path):
    path = path.resolve(strict=True)
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": str(path), "sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def new_output(path):
    base = ROOT / "output"
    output = path.resolve()
    if base.resolve() != base or not output.is_relative_to(base) or output == base:
        raise ValueError("output must be a NEW directory below this checkout's output/ (no redirected base)")
    output.mkdir(parents=True, exist_ok=False)
    return output


def jpeg_media(output, media_id, label, kind, rgb, source):
    path = output / f"{media_id}.jpg"
    ok, encoded = cv2.imencode(".jpg", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 94])
    if not ok:
        raise ValueError("JPEG encoding failed")
    with path.open("xb") as target:
        target.write(encoded.tobytes())
    return {"id": media_id, "label": label, "kind": kind, "source_path": str(path),
            "sha256": provenance(path)["sha256"], "link_status": "generated_diagnostic",
            "provenance": source}


def overlay(query_rgb, reference_rgb, query, reference, match, title):
    """Plot only geometric inliers at their native coordinates; no warp or crop."""
    header, gap = 64, 24
    height = max(query_rgb.shape[0], reference_rgb.shape[0])
    offset = query_rgb.shape[1] + gap
    canvas = np.full((height + header, offset + reference_rgb.shape[1], 3), 28, np.uint8)
    canvas[header:header + query_rgb.shape[0], :query_rgb.shape[1]] = query_rgb
    canvas[header:header + reference_rgb.shape[0], offset:] = reference_rgb
    cv2.putText(canvas, "QUERY: unverified; writing/tag leakage", (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    cv2.putText(canvas, title, (offset + 10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    cv2.putText(canvas, "Green: non-dark inliers | Orange: dark inlier (NOT verified identity)", (12, 49), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    correspondences = []
    for item, selected in zip(match["matches"], match["inlier_mask"]):
        if not selected:
            continue
        q, r = query["points"][item.queryIdx], reference["points"][item.trainIdx]
        for point, rgb in ((q, query_rgb), (r, reference_rgb)):
            if not np.isfinite(point).all() or not (0 <= point[0] < rgb.shape[1] and 0 <= point[1] < rgb.shape[0]):
                raise ValueError("stored keypoint is outside the rendered coordinate space")
        non_dark = not query["dark"][item.queryIdx] and not reference["dark"][item.trainIdx]
        color = (30, 230, 80) if non_dark else (255, 145, 40)
        a = (min(round(float(q[0])), query_rgb.shape[1] - 1), min(round(float(q[1])), query_rgb.shape[0] - 1) + header)
        b = (min(round(float(r[0])), reference_rgb.shape[1] - 1) + offset, min(round(float(r[1])), reference_rgb.shape[0] - 1) + header)
        cv2.line(canvas, a, b, color, 1, cv2.LINE_AA)
        cv2.circle(canvas, a, 4, color, 1, cv2.LINE_AA)
        cv2.circle(canvas, b, 4, color, 1, cv2.LINE_AA)
        correspondences.append({"query_index": item.queryIdx, "reference_index": item.trainIdx,
                                "query_xy": q.tolist(), "reference_xy": r.tolist(),
                                "inlier": True, "non_dark": bool(non_dark)})
    return canvas, {"query_offset_xy": [0, header], "reference_offset_xy": [offset, header],
                    "coordinate_scale_xy": [1, 1], "inlier_correspondences": correspondences}


def source_video(row):
    root = Path(row["bank_root"])
    for name in (row["sample_id"], row["session_id"], row["camera"]):
        if Path(name).name != name or name in {".", ".."}:
            raise ValueError("candidate provenance must use literal filename components")
    # Exact inverse of batch_multiview_ingest.process_session/main; no ID guessing.
    return root.parent / row["sample_id"] / row["session_id"] / row["camera"] / "rgb.mp4"


def build_pack(output, image_path, roots):
    started = time.perf_counter()
    query_source = provenance(image_path)
    query_rgb = read_image(image_path, 1000)
    mask = fruit_mask(query_rgb)
    features = extract_features(query_rgb, mask)
    report = query_banks(features, roots, top_k=20)
    report.update(image=str(image_path.resolve()), fruit_coverage=float(mask.mean()),
                  elapsed_seconds=time.perf_counter() - started, confidence=None)
    selected = report["fruit_ranking"][:3]
    if not selected:
        raise ValueError("No geometric candidate rows available; no visual identification output")
    output = new_output(output)
    media = [jpeg_media(output, "fp-query", "Ảnh truy vấn thật — mã thư mục chưa xác minh", "query_photo", query_rgb,
                        {"original": query_source, "render": "read_image auto-orient, maximum 1000px; no crop"})]
    visual_sources = []
    for ranked in selected:
        row = ranked["best_candidate"]
        bank_path = Path(row["bank_path"])
        model_path = Path(row["bank_root"]) / "shared_model.npz"
        manifest_path = bank_path.parent / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        if (manifest["sample_id"], manifest["session_id"], manifest["quality_gate"]["status"]) != (row["sample_id"], row["session_id"], "READY"):
            raise ValueError("selected bank manifest no longer matches candidate provenance")
        model_source = provenance(model_path)
        expected_model = next(r["encoder_sha256"] for r in report["roots"] if r["bank_root"] == row["bank_root"])
        if model_source["sha256"] != expected_model:
            raise ValueError("encoder changed after ranking")
        bank_source = provenance(bank_path)
        model = read_model(model_path)
        bank = read_bank(bank_path, model, geometry=True)
        index = row["view_index"]
        if int(bank["frame_indexes"][index]) != row["frame_index"]:
            raise ValueError("bank frame index changed after ranking")
        start, stop = bank["offsets"][index:index + 2]
        reference = {key: bank[key][start:stop] for key in ("points", "descriptors", "dark")}
        projected = project_features(features, model["projection"], quantized=False)
        match = geometric_match(projected, reference)
        if (match["inliers"], match["non_dark_inliers"], len(match["matches"]), match["error"]) != (
                row["geometric_inliers"], row["non_dark_inliers"], row["ratio_matches"], row["median_epipolar_error_px"]):
            raise ValueError("overlay rematch differs from ranked evidence; refusing misleading visualization")
        video = source_video(row)
        video_source = provenance(video)
        frame = decode_selected_frames(video, [row["frame_index"]], size=(960, 720))[row["frame_index"]]
        common = {"candidate": row, "source_video": video_source, "bank": bank_source,
                  "encoder": model_source, "manifest": provenance(manifest_path),
                  "frame_index_zero_based": row["frame_index"], "reference_size_wh": [960, 720],
                  "render": "ingest decode_selected_frames: full frame RGB resized to 960x720; no crop",
                  "query_original": query_source, "query_size_wh": [query_rgb.shape[1], query_rgb.shape[0]]}
        rank, sample = ranked["rank"], row["sample_id"]
        rendered, points = overlay(query_rgb, frame, projected, reference, match, f"Rank {rank}: {sample} | inliers={match['inliers']}")
        media.append(jpeg_media(output, f"fp-rank{rank}-reference", f"Hạng {rank}: {sample} — frame gốc {row['frame_index']}", "reference_frame", frame, common))
        media.append(jpeg_media(output, f"fp-rank{rank}-matches", f"Hạng {rank}: {sample} — các cặp inlier, chưa xác nhận đúng trái", "match_overlay", rendered, {**common, **points}))
        visual_sources.append({**common, **points})
        for path, before in ((bank_path, bank_source), (model_path, model_source), (video, video_source)):
            if provenance(path)["sha256"] != before["sha256"]:
                raise ValueError(f"source changed during rendering: {path}")
    if provenance(image_path)["sha256"] != query_source["sha256"]:
        raise ValueError("query source changed during rendering")
    return {
        "schema_version": 1, "review_kind": "core_code",
        "sources": {"git_snapshot": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                    "fixture_only": False, "query": query_source,
                    "generator": provenance(Path(__file__)), "elapsed_seconds": time.perf_counter() - started,
                    "limits": "Real-image diagnostic, NOT accuracy evidence. Query folder ID is unverified. Visible handwritten shell marks and stem tag can leak identity. Existing encoder-training leakage is not controlled; no verified enrollment/query split or thresholds. Hashes record current source bytes; existing banks have no historical video hash proving ingest-time identity."},
        "cases": [
            {"id": "fingerprint-real", "title": "Vân tay: ảnh thật và bằng chứng ghép điểm — chưa xác nhận đúng trái",
             "track": "fingerprint", "priority": "review", "sample_ids": [row["sample_id"] for row in selected],
             "findings": ["Đây là kết quả matcher chạy trên ảnh thật và hai bank hiện có, không phải ảnh minh họa AI.",
                          "Mã trong thư mục ảnh truy vấn chưa được xác minh; không dùng làm nhãn đúng.",
                          "Ảnh có chữ viết trên vỏ và thẻ cuống: dấu này/nền có thể chi phối phép ghép, chưa chứng minh vân tay tự nhiên.",
                          "Inliers chỉ là các cặp điểm qua kiểm tra hình học, không chứng minh cùng trái. Xanh: không tối; cam: ít nhất một điểm tối.",
                          "Top 3 lấy từ shortlist 20 view mỗi encoder; không phải tìm kiếm hình học toàn bộ bank. Không có confidence hay kết luận nhận dạng."],
             "questions": ["Các ảnh tham chiếu và cặp điểm có khớp bề mặt thật không? Ghi rõ hạng/ảnh và vùng sai nếu có."],
             "facts": [{"label": "Đặc trưng truy vấn", "value": report["query_features"], "source": "current matcher run"},
                       {"label": "Số bank encoder", "value": len(report["roots"]), "source": "current matcher run"},
                       {"label": "Confidence / kết luận", "value": "null / null — chưa hiệu chuẩn", "source": "current matcher run"}],
             "media": media,
             "result_tables": [{"title": "Top mã ghi nhận — chỉ là bằng chứng", "columns": ["Hạng", "Mã", "Inliers", "Không tối", "Sai số (px)"],
                                "rows": [[r["rank"], r["sample_id"], r["best_candidate"]["geometric_inliers"], r["best_candidate"]["non_dark_inliers"], r["best_candidate"]["median_epipolar_error_px"]] for r in selected]}],
             "raw_result": {**report, "visual_evidence": visual_sources}},
            {"id": "morphology-pending", "title": "Hộc · Múi · Vỏ: chưa có kết quả dự đoán từ ảnh thật",
             "track": "morphology", "priority": "review", "sample_ids": [],
             "findings": ["Chưa có mô hình dự đoán hộc, múi hoặc độ dày vỏ từ ảnh trước khi mở trái.",
                          "Baseline trung vị chỉ là code tham chiếu; không hiển thị số tổng hợp như kết quả ảnh thật."],
             "questions": ["Chưa có đầu ra mô hình ảnh để duyệt; cần nhãn và tập đánh giá độc lập trước."],
             "facts": [], "media": [], "result_tables": [],
             "raw_result": {"status": "no_image_predictor", "predictions": None, "confidence": None}},
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--image", required=True, type=Path, help="Explicit independent phone photo; folder ID is not verified truth")
    parser.add_argument("--bank-root", required=True, action="append", type=Path)
    args = parser.parse_args(argv)
    try:
        pack = build_pack(args.output_dir, args.image, args.bank_root)
        path = args.output_dir.resolve() / "pack.json"
        with path.open("x", encoding="utf-8") as target:
            target.write(json.dumps(pack, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    except (OSError, ValueError, RuntimeError, KeyError, cv2.error, subprocess.CalledProcessError) as exc:
        print(f"visual review failed: {exc}; any partial NEW output directory is retained for inspection", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
