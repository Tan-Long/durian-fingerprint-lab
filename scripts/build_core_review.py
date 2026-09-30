#!/usr/bin/env python3
"""Run existing synthetic fixtures and create a NEW core-code review pack.

Usage: test_video/.venv/bin/python -B scripts/build_core_review.py --output pack.json
No source media, workbook, real bank, or review database is read or modified.
This demonstrates code behavior, not real-world model accuracy or acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test_video"))

from test_query_multiview_banks import sample_features, write_root, query_banks
from scripts.test_morphology_baseline import fixture, run


def build_pack():
    query, reference = sample_features()
    with tempfile.TemporaryDirectory(prefix="core-review-synthetic-") as directory:
        roots = [Path(directory) / "encoder-a", Path(directory) / "encoder-b"]
        for index, root in enumerate(roots):
            write_root(root, query, reference, reverse=bool(index))
        fingerprint = query_banks(query, roots, top_k=1)
    data = fixture()
    morphology = run(data)
    fingerprint_source = "test_video/test_query_multiview_banks.py:sample_features/write_root"
    morphology_source = "scripts/test_morphology_baseline.py:fixture"
    heldout = {row["fruit_id"]: row for row in data["fruits"] if row["split"] == "test"}
    metrics, predictions = [], []
    for target, result in morphology["targets"].items():
        metric = result["metrics"]
        metrics.append([target, result["model"]["constant"], metric["mae"], metric["rmse"], metric["bias"]])
        for prediction in result["predictions"]:
            predictions.append([target, prediction["fruit_id"],
                                heldout[prediction["fruit_id"]]["targets"][target]["value"],
                                prediction["prediction"]])
    source_files = ["test_video/test_query_multiview_banks.py", "test_video/query_multiview_banks.py",
                    "scripts/test_morphology_baseline.py", "scripts/morphology_baseline.py",
                    "scripts/build_core_review.py"]
    return {
        "schema_version": 1, "review_kind": "core_code",
        "sources": {
            "git_snapshot": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in source_files},
            "fixture_only": True,
            "limits": "Synthetic fixture executions only; not real dataset evaluation, label approval, or project PASS. Temporary synthetic banks were removed after execution; raw bank paths are ephemeral.",
            "prior_regression_evidence": {
                "passed_tests": 65, "git_snapshot": "2b8d59b",
                "source": "docs/plans/evidence/durian-two-track-pilot/integration.log",
                "notice": "Previously verified by coordinator; this generator does not rerun or extend that test count.",
            },
        },
        "cases": [
            {
                "id": "fingerprint-core", "title": "Vân tay: kết quả chạy mã trên dữ liệu tổng hợp",
                "track": "fingerprint", "priority": "review", "sample_ids": ["Original-ID"],
                "findings": [
                    "SYNTHETIC: Original-ID là mã giả trong fixture, không phải trái thật.",
                    "Hai bộ mã hóa khác nhau chạy độc lập; bằng chứng hình học được nhóm theo mã đã ghi.",
                    "Fixture chỉ có một mã trái: không đo khả năng phân biệt nhiều trái hay độ chính xác thực tế.",
                    "identity_verdict vẫn null; thứ hạng không phải kết luận nhận dạng.",
                ],
                "questions": ["Anh có duyệt cách hiển thị thứ hạng, bằng chứng hình học và giới hạn của bản code này không?"],
                "facts": [
                    {"label": "Điểm đặc trưng truy vấn tổng hợp", "value": fingerprint["query_features"], "source": fingerprint_source},
                    {"label": "Bộ mã hóa độc lập", "value": len(fingerprint["roots"]), "source": fingerprint_source},
                    {"label": "Phạm vi duyệt", "value": "Chức năng code; chưa duyệt độ chính xác mô hình", "source": "fixture-only contract"},
                ],
                "media": [],
                "result_tables": [
                    {"title": "Xếp hạng mã giả", "columns": ["Hạng", "Mã ghi nhận", "Inliers tốt nhất", "Dòng bằng chứng (index)"],
                     "rows": [[row["rank"], row["sample_id"], row["best_candidate"]["geometric_inliers"],
                               ", ".join(map(str, row["supporting_candidate_indexes"]))] for row in fingerprint["fruit_ranking"]]},
                    {"title": "Bằng chứng từng bộ mã hóa", "columns": ["Encoder [index]", "Camera / Phiên", "Inliers", "Không tối", "Sai số (px)"],
                     "rows": [[f"{Path(row['bank_root']).name} [{index}]", f"{row['camera']} / {row['session_id']}",
                               row["geometric_inliers"], row["non_dark_inliers"], row["median_epipolar_error_px"]]
                              for index, row in enumerate(fingerprint["candidates"])]},
                ],
                "raw_result": fingerprint,
            },
            {
                "id": "morphology-core", "title": "Hộc · Múi · Vỏ: baseline trung vị trên dữ liệu tổng hợp",
                "track": "morphology", "priority": "review",
                "sample_ids": [row["fruit_id"] for row in data["fruits"]],
                "findings": [
                    "SYNTHETIC: 2 trái train và 2 trái test giả; nhãn approved chỉ là dữ liệu kiểm thử.",
                    "Dự đoán là trung vị nhãn train cho từng mục tiêu; đặc trưng được kiểm tra nhưng chưa dùng để học.",
                    "Sai số dưới đây chỉ chứng minh phép tính trên fixture, không phải độ chính xác dự đoán trái thật.",
                ],
                "questions": ["Anh có duyệt luồng train/test, dự đoán và cách báo sai số của baseline code này không?"],
                "facts": [
                    {"label": "Train", "value": ", ".join(morphology["splits"]["train"]), "source": morphology_source},
                    {"label": "Test giữ riêng", "value": ", ".join(morphology["splits"]["test"]), "source": morphology_source},
                    {"label": "Đơn vị", "value": "locule_count: hộc; aril_count: múi; shell_thickness_mm: mm; bias = dự đoán - nhãn", "source": "scripts/morphology_baseline.py:evaluate"},
                ],
                "media": [],
                "result_tables": [
                    {"title": "Nhãn và dự đoán từng trái test giả", "columns": ["Mục tiêu", "Trái test", "Nhãn fixture", "Dự đoán"], "rows": predictions},
                    {"title": "Sai số trên fixture", "columns": ["Mục tiêu", "Trung vị train", "MAE", "RMSE", "Bias"], "rows": metrics},
                ],
                "raw_result": {"input": data, "output": morphology},
            },
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New JSON file; parent directory must exist")
    args = parser.parse_args(argv)
    try:
        serialized = json.dumps(build_pack(), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"core review: {exc}", file=sys.stderr)
        return 1
    print(f"Created fixture-only review pack: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
