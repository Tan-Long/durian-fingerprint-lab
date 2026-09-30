#!/usr/bin/env python3
"""Combine real source alignment, unchanged retrieval diagnostics and reference labels.

Reference labels are NEVER inputs to either matcher or a morphology predictor.
This only assembles the read-only evidence after both diagnostic runs finish.
"""
import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    raw = path.read_bytes()
    return json.loads(raw), {"path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest()}


def assemble(alignment_path, retrieval_path, evidence_path):
    alignment, alignment_source = read(alignment_path)
    retrieval, retrieval_source = read(retrieval_path)
    evidence, evidence_source = read(evidence_path)
    sample = evidence["sample_id"]
    for name, pack in (("alignment", alignment), ("retrieval", retrieval)):
        if (pack["sources"].get("fixture_only") is not False
                or pack["sources"]["query"]["sha256"] != evidence["query"]["sha256"]):
            raise ValueError(f"{name}: must use the same real independent query as selected sample evidence")
    align_case, = [case for case in alignment["cases"] if case["raw_result"].get("mode") == "known_sample_alignment"]
    winners = align_case["raw_result"]["best_per_camera"]
    if not any(row["geometric_inliers"] for row in winners):
        align_case["findings"].insert(0, "CHƯA KHỚP: cả hai camera có 0 inlier hình học. Ảnh đặt cạnh nhau chỉ để kiểm tra nguồn; không có cặp điểm được xác nhận. Các frame đồng hạng được chọn theo chỉ số nhỏ nhất, không phải góc nhìn đã khớp.")
    retrieval_case, = [case for case in retrieval["cases"] if case["track"] == "fingerprint"]
    retrieval_case["git_snapshot"] = retrieval["sources"]["git_snapshot"]
    # Do not hide a failed retrieval when displaying the easier known-sample task.
    retrieval_case["title"] = f"Tìm mã trong dataset — đối chiếu với {sample}"
    retrieval_case["findings"].insert(0, f"Mã mẫu đã đối chiếu nguồn: {sample}; đây chưa phải nhãn chuẩn được người dùng duyệt.")
    ranking = retrieval_case["raw_result"]["fruit_ranking"]
    top_ids = [item["sample_id"] for item in ranking[:3]]
    retrieval_case["findings"].insert(1, f"Top 3 thực tế: {', '.join(top_ids)}. " +
                                    ("Không có mã mẫu đã đối chiếu trong top 3." if sample not in top_ids else "Có mã mẫu trong top 3; vẫn cần duyệt điểm khớp."))
    media = []
    for index, item in enumerate(evidence["label_evidence"][:1] + evidence["chamber_photos"]):
        actual = hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest()
        if actual != item["sha256"]:
            raise ValueError(f"reference image changed: {item['path']}")
        chamber = "visible_locule" in item
        media.append({"id": f"reference-{index}", "source_path": item["path"], "sha256": actual,
                      "kind": "chamber_photo" if chamber else "identity_photo",
                      "label": f"{sample} · " + (item["visible_locule"] + " — đối chứng sau bổ" if chamber else "thẻ mã đầy đủ"),
                      "link_status": "Đã đối chiếu bằng mắt; chờ người dùng duyệt, không phải đầu vào dự đoán"})
    workbook = evidence["workbook"]
    if hashlib.sha256(Path(workbook["path"]).read_bytes()).hexdigest() != workbook["sha256"]:
        raise ValueError("reference workbook changed after sample selection")
    labels = {"locule_count": "Số hộc", "aril_count": "Số múi", "shell_thickness_mm": "Độ dày vỏ (mm)"}
    reference = {
        "id": "morphology-reference", "title": f"{sample} · Hộc/múi/vỏ: ảnh đối chứng, chưa có dự đoán",
        "track": "morphology", "sample_ids": [sample], "priority": "review",
        "findings": ["Đầu vào dự đoán được yêu cầu là quả nguyên (RGB–LiDAR). Ảnh sau bổ và Excel chỉ dùng đối chứng.",
                     "Các số dưới đây là số đo trong Excel, không phải đầu ra mô hình; chưa có dự đoán hoặc lớp hộc/múi bên trong.",
                     "Ảnh thẻ mã và H1–H5 đã được đọc bằng mắt; nhãn qua đối soát nhưng chưa được người dùng phê duyệt.",
                     "Mẫu đủ các nguồn cho demo này, không đầy đủ mọi trường: còn thiếu hộc lép, thể tích, chiều cao/mật độ gai và cờ nứt."],
        "questions": ["Bạn xác nhận ảnh, mã và các số đo đối chứng này có cùng mẫu không? Việc duyệt không xác nhận mô hình dự đoán."],
        "facts": [{"label": labels[key], "value": target["value"], "source": f"{workbook['path']}#{target['sheet']}!{target['cell']}"}
                  for key, target in evidence["targets"].items()],
        "media": media,
        "result_tables": [{"title": "ĐỐI CHỨNG SAU BỔ — KHÔNG PHẢI DỰ ĐOÁN", "columns": ["Đại lượng", "Excel", "Dự đoán từ quả nguyên"],
                           "rows": [[labels[key], target["value"], "Chưa có mô hình"] for key, target in evidence["targets"].items()]}],
        "raw_result": {"status": "no_image_predictor", "predictions": None, "reference_evidence": evidence}}
    return {"schema_version": 1, "review_kind": "core_code", "sources": {
        **alignment["sources"], "assembly_inputs": [alignment_source, retrieval_source, evidence_source],
        "selected_sample": sample, "user_approved": False,
        "limits": "Real demo only. Known-sample frame alignment is not dataset identification. Reference targets are not model predictions. Source-correlated identity is provisional, not user-approved gold truth."},
        "cases": [align_case, reference, retrieval_case]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alignment-pack", required=True, type=Path)
    parser.add_argument("--retrieval-pack", required=True, type=Path)
    parser.add_argument("--sample-evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    pack = assemble(args.alignment_pack, args.retrieval_pack, args.sample_evidence)
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(pack, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
