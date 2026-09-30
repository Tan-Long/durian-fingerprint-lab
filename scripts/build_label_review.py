#!/usr/bin/env python3
"""Build a Vietnamese review pack from read-only audits and existing photographs.

No label corrections, decisions, splits or image conversion are performed.
Source photo links remain provisional. Chamber photos, cross-identity duplicates
and supplemental images are hashed during this run; other hashes are historical.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re


RASTER_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp"}
TARGET_NAMES = {"locule_count": "Số hộc", "aril_count": "Tổng số múi",
                "shell_thickness_mm": "Độ dày vỏ (mm)", "empty_locule_count": "Số hộc lép"}
TARGET_FIELDS = {"locule_count": "Số lượng hộc", "aril_count": "Tổng số múi",
                 "shell_thickness_mm": "dày vỏ", "empty_locule_count": "Số hộc lép"}


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def explicit_ocr_identity(text):
    """Read complete literal codes only; do not repair OCR characters or H numbers."""
    pattern = (r"(?<![A-Z0-9])N\s*(\d+)[\s_-]*V\s*(\d+)[\s_-]*C\s*(\d+)"
               r"([\s_-]*BONUS)?(?:[\s_-]*H\s*\d+)?(?![A-Z0-9])")
    identities = {f"N{n}V{v}C{c}" + ("_BONUS" if bonus else "")
                  for n, v, c, bonus in re.findall(pattern, text, flags=re.IGNORECASE)}
    return next(iter(identities)) if len(identities) == 1 else None


def new_case(identifier, title, track, priority, sample_ids):
    return {"id": identifier, "title": title, "track": track, "priority": priority,
            "sample_ids": sample_ids, "findings": [], "questions": [], "facts": [], "media": []}


def fact(case, label, value, source):
    case["facts"].append({"label": label, "value": value, "source": source})


def build_pack(audit_path, media_path, summary_path, chamber_path=None, preview_roots=(), observations_path=None):
    audit = json.loads(Path(audit_path).read_text(encoding="utf-8"))
    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    if audit.get("schema_version") != 1:
        raise ValueError("Phiên bản audit không được hỗ trợ")
    required_hashes = dict(summary["source_manifests"])
    for name in ["workbook", "samples"]:
        source, digest = audit["sources"][name], audit["sources"][name + "_sha256"]
        if source in required_hashes and required_hashes[source] != digest:
            raise ValueError(f"Audit và danh mục không cùng phiên bản nguồn: {source}")
        required_hashes[source] = digest
    for source, digest in required_hashes.items():
        if not digest or sha256(source) != digest:
            raise ValueError(f"Nguồn đã thay đổi; cần chạy lại audit/danh mục: {source}")
    sources = {"verified_source_hashes": required_hashes,
               "audit": {"path": str(Path(audit_path).resolve()), "sha256": sha256(audit_path)},
               "media_index": {"path": str(Path(media_path).resolve()), "sha256": sha256(media_path)},
               "index_summary": {"path": str(Path(summary_path).resolve()), "sha256": sha256(summary_path)},
               "notes": "Ảnh theo thư mục/OCR chưa xác nhận đúng quả. Hash ảnh từ danh mục là giá trị lịch sử trừ ảnh được ghi đã kiểm tra lại."}
    if summary.get("collection"):
        sources["collection_root"] = summary["collection"]
    media = read_csv(media_path)
    if media and not {"sample_id", "source_path", "destination_sha256", "modality"} <= media[0].keys():
        raise ValueError("Danh mục ảnh thiếu cột bắt buộc")
    photos = [m for m in media if m["modality"] in {"chamber_photo", "random_photo"}
              and Path(m["source_path"]).suffix.lower() in RASTER_SUFFIXES]
    ocr_rows = read_csv(chamber_path) if chamber_path else []
    if ocr_rows and not {"ma_mau", "ma_hoc_goi_y", "file_goc", "ocr_tho", "trang_thai_nhan"} <= ocr_rows[0].keys():
        raise ValueError("Bảng kê hộc thiếu cột bắt buộc")
    if chamber_path:
        sources["chamber_manifest"] = {"path": str(Path(chamber_path).resolve()), "sha256": sha256(chamber_path)}
    sources["preview_roots"] = [str(Path(p).resolve()) for p in preview_roots]
    verified_images = {}
    ocr_by_path = {str(Path(row["file_goc"]).resolve()): row for row in ocr_rows}
    for path in ocr_by_path:
        if Path(path).suffix.lower() in RASTER_SUFFIXES and Path(path).is_file():
            verified_images[path] = sha256(path)
    by_hash = defaultdict(list)
    for photo in photos:
        if photo["sample_id"] and photo["destination_sha256"]:
            by_hash[photo["destination_sha256"]].append(photo)
    cases = []
    for digest, duplicates in sorted(by_hash.items()):
        ids = sorted({m["sample_id"] for m in duplicates})
        if len(ids) < 2:
            continue
        case = new_case("identity-" + digest[:16], "Một ảnh nằm dưới nhiều mã quả: " + ", ".join(ids), "shared", 1, ids)
        for photo in duplicates:
            path = photo["source_path"]
            actual = sha256(path)
            if actual != digest:
                raise ValueError(f"Ảnh tranh chấp đã thay đổi: {path}")
            verified_images[path] = actual
            fact(case, "Bản ảnh trùng đã kiểm tra hash", photo["sample_id"], path)
        case["findings"].append("Cùng nội dung ảnh xuất hiện dưới nhiều mã quả; hash được kiểm tra lại, chưa xác định mã nào đúng.")
        case["questions"].append("Ảnh gốc thuộc quả nào? Các thư mục còn lại là bản sao hay đang mang mã sai? Ghi bằng chứng trước khi chốt.")
        cases.append(case)

    fruits = {f["row"]: f for f in audit["fruits"]}
    locules = audit["locules"]
    workbook = audit["sources"]["workbook"]

    def source(record, fields):
        return workbook + "#" + record["sheet"] + "!" + ",".join(record["cells"][f] for f in fields)

    def add_fruit(case, fruit, candidate=False):
        prefix = "Ứng viên chưa nối mã — " if candidate else ""
        for field in ["Fruit-ID", "Group-ID", "Farm-ID", "Tree-ID", *TARGET_FIELDS.values()]:
            fact(case, prefix + field, fruit["values"][field], source(fruit, [field]))
            if fruit["raw"][field] != fruit["values"][field]:
                fact(case, prefix + field + " — công thức/giá trị gốc", fruit["raw"][field], source(fruit, [field]))

    def add_locule(case, record, unassigned=False):
        label = f"Chi tiết hộc dòng {record['row']}"
        if unassigned:
            label += " — CHƯA GÁN cho quả này"
        fact(case, label, compact(record["values"]), source(record, list(record["values"])))

    for mapping in audit["crosswalk"]:
        sample_id = mapping["sample_id"]
        if mapping["status"] != "matched":
            case = new_case("unmatched-" + sample_id, "Chưa nối được mã: " + sample_id, "shared", 1, [sample_id])
            case["findings"].append("Không có liên kết workbook chính xác, duy nhất; chưa coi ảnh hoặc nhãn tương tự là cùng quả.")
            fact(case, "Mã trong danh sách mẫu", sample_id, audit["sources"]["samples"] + f":{mapping['samples_csv_row']}")
            if "BONUS" in sample_id:
                base = sample_id.split("_BONUS")[0]
                for fruit in fruits.values():
                    normalized = re.sub(r"[^A-Z0-9]", "", str(fruit["fruit_id"]).upper())
                    if base in normalized and "BONUS" in normalized:
                        add_fruit(case, fruit, candidate=True)
                for record in locules:
                    normalized = re.sub(r"[^A-Z0-9]", "", str(record["fruit_id"]).upper())
                    if base in normalized and "BONUS" in normalized:
                        add_locule(case, record, unassigned=True)
                case["questions"].append("Mã BONUS trong video, ảnh, bảng quả và bảng hộc có cùng một quả không? Phân biệt với quả thường cùng gốc mã.")
            else:
                case["questions"].append("Mã đang ghi có đúng không, hay thiếu dòng trong workbook? Cần người lấy mẫu xác nhận; không tự sửa theo mã gần giống.")
            cases.append(case)
            continue
        fruit = fruits[mapping["workbook_rows"][0]]
        bad_counts = [t for t in ["locule_count", "aril_count"] if fruit["targets"][t]["status"] != "valid"]
        if bad_counts:
            case = new_case("counts-" + sample_id, "Đối soát hộc và múi: " + sample_id, "morphology", 2, [sample_id])
            add_fruit(case, fruit)
            detail = fruit["detail_summary"]
            total_locules = fruit["values"]["Số lượng hộc"]
            total_arils = fruit["values"]["Tổng số múi"]
            case["findings"].append(
                f"Bảng tổng: {total_locules if total_locules is not None else 'trống'} hộc / "
                f"{total_arils if total_arils is not None else 'trống'} múi. Chi tiết ghép được: "
                f"{detail['row_count']} dòng, {detail['unique_locule_count']} số hộc khác nhau, "
                f"tổng múi {detail['aril_sum'] if detail['aril_sum'] is not None else 'chưa tính được'}.")
            fact(case, "Dòng chi tiết đang nối theo mã quả", compact(detail["rows"]), source(fruit, ["Fruit-ID"]))
            fact(case, "Thứ tự hộc dạng số đọc được", compact(detail["locule_numbers"]), source(fruit, ["Fruit-ID"]))
            repeated = {number: count for number, count in Counter(detail["locule_numbers"]).items() if count > 1}
            fact(case, "Số hộc bị lặp và số lần xuất hiện", compact(repeated), source(fruit, ["Fruit-ID"]))
            for record in locules:
                if record["row"] in detail["rows"]:
                    add_locule(case, record)
                elif not record["fruit_id"] and detail["rows"] and record["row"] == max(detail["rows"]) + 1:
                    add_locule(case, record, unassigned=True)
                    case["findings"].append("Có dòng liền kề thiếu Fruit-ID; chỉ hiển thị vị trí để đối soát, chưa cộng vào tổng hoặc gán cho quả.")
            case["findings"].append("Cần duyệt riêng: " + ", ".join(TARGET_NAMES[t] for t in bad_counts) + ". Số dòng, số hộc khác nhau và tổng múi không được dùng thay thế lẫn nhau.")
            case["questions"].append("Giá trị nào được ảnh/phiếu gốc xác nhận? Nếu đề nghị sửa, ghi rõ ô, giá trị mới và bằng chứng; có thể giữ chưa rõ.")
            cases.append(case)
        if fruit["targets"]["shell_thickness_mm"]["status"] != "valid":
            case = new_case("shell-" + sample_id, "Nhãn độ dày vỏ cần kiểm tra: " + sample_id, "morphology", 3, [sample_id])
            fact(case, "Độ dày vỏ (mm)", fruit["values"]["dày vỏ"], source(fruit, ["dày vỏ"]))
            case["findings"].append("Nhãn vỏ không qua kiểm tra. Ô trống không phải 0; ảnh có thước chưa đủ để tự suy ra số đo vỏ.")
            case["questions"].append("Có số đo vỏ gốc và đơn vị mm để đối soát không? Nếu không, giữ thiếu riêng nhãn vỏ.")
            cases.append(case)

    scope = new_case("scope-input-timing", "Phạm vi riêng: thời điểm đo và nhãn còn thiếu", "shared", 4, [])
    matched = [fruits[c["workbook_rows"][0]] for c in audit["crosswalk"] if c["status"] == "matched"]
    for field in ["Fruit-Weight", "Fruit-Length (L)", "Fruit-Width", "Fruit-Chu vi", "Fruit-Length (L)- đo khi bổ", "Fruit-Width- đo khi bổ quả", "Số hộc lép"]:
        fact(scope, "Số dòng có giá trị: " + field, sum(f["values"].get(field) is not None for f in matched), workbook + "#Fruit-list")
    scope["findings"] = ["Các cột ghi đo khi bổ, độ dày vỏ, thông tin hộc và ảnh sau bổ chỉ dùng làm nhãn/đối chứng.",
                         "Cần xác nhận thời điểm đo cân nặng, chiều dài, chiều rộng và chu vi trước khi dùng làm đầu vào.",
                         "Duyệt hồ sơ này không tạo bộ chia đánh giá, không xác nhận độ chính xác mô hình và không biến ô trống thành 0."]
    scope["questions"] = ["Bốn số đo ngoài quả có thực sự được lấy trước khi bổ không? Có phiếu hoặc quy trình của đợt lấy mẫu để đối chiếu không?",
                          "Nhãn hộc lép thiếu có được đo ở đợt này không? Nếu không có bằng chứng, giữ thiếu và hoãn mục tiêu này."]
    cases.append(scope)
    if chamber_path:
        archive = new_case("chamber-archive", "Kho toàn bộ ảnh hộc gốc để tìm ảnh còn thiếu", "shared", 4, [])
        archive["findings"] = ["Hiển thị mọi ảnh gốc có sẵn trong bảng kê hộc, kể cả ảnh chưa đọc được mã hoặc được ghi không phải ảnh hộc.",
                               "Đây là kho tìm bằng chứng, không phải danh sách ảnh đã xác nhận thuộc từng quả. Không tự gán ảnh đứng cạnh nhau."]
        archive["questions"] = ["Ảnh nào thuộc quả/hộc đang duyệt? Ghi tên ảnh và bằng chứng nhận diện; giữ chưa rõ nếu không đọc được mã."]
        fact(archive, "Số dòng ảnh trong bảng kê", len(ocr_rows), str(chamber_path))
        cases.append(archive)

    def attach(case):
        selected = []
        for photo in photos:
            if photo["sample_id"] in case["sample_ids"]:
                selected.append((photo["source_path"], photo["modality"], photo["destination_sha256"],
                                 "Theo mã thư mục/danh mục, chưa xác nhận đúng quả", photo["sample_id"],
                                 photo.get("manifest_path", str(media_path)) + ":" + photo.get("manifest_row", "")))
        for row_number, row in enumerate(ocr_rows, 2):
            related = []
            explicit = explicit_ocr_identity(row["ocr_tho"])
            for sample_id in case["sample_ids"]:
                base = sample_id.split("_BONUS")[0]
                if row["ma_mau"] == sample_id or re.fullmatch(re.escape(base) + r"H\d+", row["ma_hoc_goi_y"]):
                    if "BONUS" not in sample_id or "BONUS" in row["ocr_tho"].upper():
                        related.append(sample_id)
                if explicit == sample_id and sample_id not in related:
                    related.append(sample_id)
            if not related and case["id"] != "chamber-archive":
                continue
            path = row["file_goc"]
            if Path(path).suffix.lower() not in RASTER_SUFFIXES:
                continue
            digest = next((p["destination_sha256"] for p in photos if p["source_path"] == path), "")
            status = "Theo bảng kê/OCR, chưa xác nhận mã/hộc"
            if explicit and explicit in related:
                status = "Có mã đầy đủ trong OCR gốc, vẫn là ứng viên chưa xác nhận"
            selected.append((path, "chamber_photo", digest, status,
                             ", ".join(related) or row["ma_mau"] or "Chưa có mã xác nhận", f"{chamber_path}:{row_number}"))
            fact(case, "OCR gốc — " + Path(path).name,
                 compact({key: row.get(key, "") for key in ["ma_mau", "hoc", "ma_hoc_goi_y", "trang_thai_nhan", "phan_loai", "ocr_tho"]}), f"{chamber_path}:{row_number}")
        if not selected:
            for sample_id in case["sample_ids"]:
                for root in preview_roots:
                    directory = (Path(root) / "samples" / sample_id).resolve()
                    if not directory.is_relative_to(Path(root).resolve()):
                        raise ValueError("Mã mẫu không hợp lệ cho thư mục ảnh ghép")
                    for path in sorted(directory.glob("*/contact-sheet.jpg")):
                        selected.append((str(path), "rig_preview", "", "Ảnh ghép đã xử lý từ rig, chưa xác nhận mã", sample_id, str(path.parent)))
        grouped = {}
        seen_paths = set()
        for raw_path, kind, digest, status, sample_ids, provenance in selected:
            path = Path(raw_path)
            fact(case, "Liên kết ảnh tạm — " + path.name, sample_ids + " | " + status + " | " + str(path), provenance)
            if not path.is_file():
                case["findings"].append("Không đọc được ảnh gốc: " + str(path))
                continue
            path = path.resolve()
            if path in seen_paths:
                continue
            seen_paths.add(path)
            digest = verified_images.get(str(path), digest)
            if not digest:
                digest = sha256(path)
                verified_images[str(path)] = digest
            if digest in grouped:
                fact(case, "Bản sao cùng hash, chỉ hiển thị một ảnh", str(path), digest)
                continue
            grouped[digest] = path
            record = {"id": "media-" + hashlib.sha256(str(path).encode()).hexdigest(),
                                  "label": path.name + " — " + sample_ids, "kind": kind,
                                  "source_path": str(path), "sha256": digest, "link_status": status}
            if str(path) in ocr_by_path:
                row = ocr_by_path[str(path)]
                literal_hocs = sorted(set(re.findall(r"(?<![A-Z])H\s*(\d+)(?![A-Z0-9])", row["ocr_tho"], re.IGNORECASE)))
                hint = row.get("hoc") or row["ma_hoc_goi_y"] or "Chưa đọc rõ hộc"
                if explicit_ocr_identity(row["ocr_tho"]) and literal_hocs:
                    hint = "OCR nguyên văn: " + ", ".join("H" + number for number in literal_hocs)
                record["locule_hint"] = hint + " — gợi ý chưa duyệt"
            case["media"].append(record)
        if case["sample_ids"] and not case["media"]:
            case["findings"].append("Chưa có ảnh bằng chứng đọc được cho mã này trong các nguồn đã kiểm tra.")
        if case["media"]:
            case["findings"].append("Ảnh là bằng chứng để người duyệt kiểm tra; quan hệ theo thư mục hoặc gợi ý OCR có thể sai. OCR cũ chỉ xét H1–H5.")
        if case["sample_ids"]:
            chamber_count = sum(m["kind"] == "chamber_photo" for m in case["media"])
            declared = [str(fr["values"]["Số lượng hộc"]) for mapping in audit["crosswalk"]
                        if mapping["sample_id"] in case["sample_ids"] and mapping["status"] == "matched"
                        for fr in [fruits[mapping["workbook_rows"][0]]]]
            case["findings"].append(f"Có {chamber_count} ảnh hộc ứng viên khác nội dung; bảng quả ghi "
                                    f"{', '.join(declared) if declared else 'chưa nối nhãn'} hộc; chưa xác nhận đủ bộ. "
                                    "Số ảnh không phải số hộc. Có thể tìm thêm trong kho toàn bộ ảnh hộc.")
            case["questions"].append("Đã có ảnh của những hộc nào, còn thiếu hộc nào? Có ảnh trùng/chụp lại hoặc sai mã không? Xem kho toàn bộ ảnh hộc nếu bộ ứng viên chưa đủ.")

    for case in cases:
        attach(case)
    observed_hashes = set()
    if observations_path:
        observations = json.loads(Path(observations_path).read_text(encoding="utf-8"))
        by_id = {case["id"]: case for case in cases}
        for case_id, findings in observations["findings"].items():
            if case_id not in by_id or not isinstance(findings, list) or not all(isinstance(f, str) for f in findings):
                raise ValueError(f"Ghi chú tự kiểm tra không khớp hồ sơ: {case_id}")
            by_id[case_id]["findings"].extend("Tự kiểm tra của điều phối, chưa xác nhận nhãn: " + f for f in findings)
        sources["observations"] = {"path": str(Path(observations_path).resolve()),
                                   "sha256": sha256(observations_path), "sources": observations.get("sources", {})}
        observed_hashes = {value for value in observations.get("sources", {}).values()
                           if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)}
    for case in cases:
        disputed_prefix = case["id"].removeprefix("identity-") if case["id"].startswith("identity-") else None
        case["media"].sort(key=lambda media: (
            not (disputed_prefix and media["sha256"].startswith(disputed_prefix)),
            media["sha256"] not in observed_hashes,
        ))
    sources["verified_image_hashes"] = verified_images
    return {"schema_version": 1, "sources": sources, "cases": sorted(cases, key=lambda c: (c["priority"], c["id"]))}


def write_pack(pack, output):
    output = Path(output)
    if output.is_symlink():
        raise ValueError("Không ghi đè file đầu ra là symlink")
    inputs = list(pack["sources"]["verified_source_hashes"])
    inputs += [value["path"] for value in pack["sources"].values() if isinstance(value, dict) and "path" in value]
    protected = [Path(p).resolve().parent for p in inputs]
    if pack["sources"].get("collection_root"):
        protected.append(Path(pack["sources"]["collection_root"]).resolve())
    protected += [Path(p).resolve() for p in pack["sources"].get("preview_roots", [])]
    protected += [Path(m["source_path"]).resolve().parent for c in pack["cases"] for m in c["media"]]
    if any(output.resolve().is_relative_to(root) for root in protected):
        raise ValueError("Đầu ra phải nằm ngoài thư mục dữ liệu nguồn")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--media-index", type=Path, required=True)
    parser.add_argument("--index-summary", type=Path, required=True)
    parser.add_argument("--chamber-manifest", type=Path)
    parser.add_argument("--preview-root", type=Path, action="append", default=[])
    parser.add_argument("--observations", type=Path, help="JSON ghi chú tự kiểm tra của điều phối; không phải nhãn đã duyệt")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        pack = build_pack(args.audit, args.media_index, args.index_summary, args.chamber_manifest, args.preview_root, args.observations)
        write_pack(pack, args.output)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, str(error) + "\n")
    print(f"Đã tạo {len(pack['cases'])} hồ sơ, {sum(len(c['media']) for c in pack['cases'])} lượt ảnh: {args.output}")


if __name__ == "__main__":
    main()
