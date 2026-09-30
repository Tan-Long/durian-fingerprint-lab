#!/usr/bin/env python3
"""Build a separate, conservative manifest for durian chamber photos."""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".heic", ".heif", ".png", ".tif", ".tiff", ".dng", ".webp"}
NON_SAMPLE_NAMES = {
    *(f"IMG_{number:04d}.JPG" for number in range(23, 31)),
    "IMG_9648.JPG", "IMG_9688.JPG", "IMG_9731.JPG", "IMG_9732.JPG",
    "IMG_9733.PNG", "IMG_9734.JPG", "IMG_9898.PNG", "IMG_9899.JPG",
    "IMG_9900.JPG", "IMG_9901.PNG", "IMG_2679.HEIC",
}
FIELDS = [
    "stt", "ma_mau", "hoc", "ma_hoc_goi_y", "trang_thai_nhan",
    "diem_khop_nhan", "may_chup", "file_goc", "kich_thuoc",
    "phan_loai", "su_dung_database", "ban_chinh_sua_cua", "ocr_tho", "ghi_chu",
]


def normalize(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def read_manager_codes(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows or any(len(row) != 12 for row in rows):
        raise ValueError("CSV quản lý phải có đúng 12 cột ở mọi dòng")
    try:
        code_index = rows[0].index("Mã mẫu")
    except ValueError as error:
        raise ValueError("Không tìm thấy cột 'Mã mẫu'") from error
    codes = [row[code_index].strip() for row in rows[1:] if row[code_index].strip()]
    if len(codes) != len(set(codes)):
        raise ValueError("CSV quản lý có mã mẫu lặp")
    return codes


def discover_images(source: Path) -> list[Path]:
    return sorted(
        (path for path in source.rglob("*")
         if path.is_file() and not path.name.startswith("._") and path.suffix.lower() in IMAGE_EXTENSIONS),
        key=lambda path: str(path).casefold(),
    )


def edited_original(path: Path) -> Path | None:
    match = re.fullmatch(r"IMG_E(\d+)\.(JPE?G)", path.name, re.IGNORECASE)
    if not match:
        return None
    wanted = f"IMG_{match.group(1)}.{match.group(2)}".casefold()
    return next((candidate for candidate in path.parent.iterdir() if candidate.name.casefold() == wanted), None)


def run_vision(paths: list[Path], helper: Path) -> dict[str, dict]:
    if not paths:
        return {}
    command = ["/usr/bin/swift", str(helper), *(str(path) for path in paths)]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
    assert process.stdout is not None
    records = {}
    for line in process.stdout:
        record = json.loads(line)
        records[record["path"]] = record
    if process.wait() != 0:
        raise RuntimeError("Apple Vision OCR thất bại")
    return records


def best_label(texts: list[dict], valid_labels: list[str]) -> tuple[str, float, float, str]:
    ranked: list[tuple[float, str, str]] = []
    for item in texts:
        observed = normalize(item.get("text", ""))
        if not observed or len(observed) > 24:
            continue
        for label in valid_labels:
            score = difflib.SequenceMatcher(None, observed, label).ratio()
            ranked.append((score, label, observed))
    if not ranked:
        return "", 0.0, 0.0, ""
    ranked.sort(reverse=True)
    best = ranked[0]
    second_score = next((score for score, label, _ in ranked[1:] if label != best[1]), 0.0)
    return best[1], best[0], best[0] - second_score, best[2]


def machine_name(source: Path, path: Path) -> str:
    relative = path.relative_to(source)
    return relative.parts[0] if len(relative.parts) > 1 else ""


def build_rows(source: Path, codes: list[str], records: dict[str, dict]) -> list[dict[str, str]]:
    valid_labels = [f"{code}H{hoc}" for code in codes for hoc in range(1, 6) if "BONUS" not in code]
    rows = []
    for index, path in enumerate(discover_images(source), 1):
        original = edited_original(path)
        record = records.get(str(path), {})
        texts = record.get("texts", [])
        raw_text = " | ".join(item.get("text", "") for item in texts)
        suggestion, score, margin, observed = best_label(texts, valid_labels)
        exact = suggestion and observed == suggestion
        strong = not exact and score >= 0.92 and margin >= 0.06

        if path.name.upper() in NON_SAMPLE_NAMES:
            category, status, use, note = "khong_phai_anh_hoc", "KHONG_CO_NHAN", "KHONG", "Ảnh giấy tờ/hiện trường, không dùng huấn luyện"
        elif original:
            category, status, use, note = "ban_chinh_sua", "TRUNG_BAN_GOC", "KHONG", "Ưu tiên bản gốc"
        elif exact:
            category, status, use, note = "anh_hoc", "OCR_RO", "CO", ""
        elif strong:
            category, status, use, note = "anh_hoc", "GOI_Y_MANH_CAN_DUYET", "CHUA", "Chưa tự động xác nhận mã"
        else:
            category, status, use, note = "anh_hoc", "CAN_DUYET_NHAN", "CHUA", "Nhãn mờ hoặc OCR chưa đủ chắc chắn"

        accepted = suggestion if exact else ""
        label_match = re.fullmatch(r"(.+)(H[1-5])", accepted)
        width, height = record.get("width", 0), record.get("height", 0)
        rows.append({
            "stt": str(index),
            "ma_mau": label_match.group(1) if label_match else "",
            "hoc": label_match.group(2) if label_match else "",
            "ma_hoc_goi_y": suggestion,
            "trang_thai_nhan": status,
            "diem_khop_nhan": f"{score:.3f}" if suggestion else "",
            "may_chup": machine_name(source, path),
            "file_goc": str(path),
            "kich_thuoc": f"{width}x{height}" if width and height else "",
            "phan_loai": category,
            "su_dung_database": use,
            "ban_chinh_sua_cua": str(original) if original else "",
            "ocr_tho": raw_text,
            "ghi_chu": note if not record.get("error") else f"Lỗi OCR: {record['error']}",
        })

    by_label = defaultdict(list)
    for row in rows:
        if row["ma_mau"]:
            by_label[row["ma_mau"] + row["hoc"]].append(row)
    for label, duplicates in by_label.items():
        if len(duplicates) > 1:
            for row in duplicates:
                row["trang_thai_nhan"] = "TRUNG_MA_HOC_CAN_DUYET"
                row["su_dung_database"] = "CHUA"
                row["ghi_chu"] = f"Có {len(duplicates)} ảnh cùng nhãn {label}; cần xác nhận ảnh chụp lại hay ghi nhầm H"
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        assert all(len(row) == len(FIELDS) for row in csv.reader(handle))


def write_report(path: Path, rows: list[dict[str, str]], codes: list[str]) -> None:
    category = Counter(row["phan_loai"] for row in rows)
    accepted = defaultdict(set)
    duplicate_labels = defaultdict(list)
    for row in rows:
        if row["ma_mau"]:
            accepted[row["ma_mau"]].add(row["hoc"])
            duplicate_labels[row["ma_mau"] + row["hoc"]].append(row["file_goc"])
    duplicate_labels = {label: files for label, files in duplicate_labels.items() if len(files) > 1}
    missing = {code: sorted({f"H{i}" for i in range(1, 6)} - accepted[code]) for code in accepted}
    review = [row for row in rows if row["phan_loai"] == "anh_hoc" and row["su_dung_database"] != "CO"]
    database_ready = sum(row["su_dung_database"] == "CO" for row in rows)

    lines = [
        "# Báo cáo dữ liệu ảnh hộc sầu riêng", "",
        f"- Cập nhật: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- Tổng file ảnh: {len(rows)}", f"- Ảnh hộc: {category['anh_hoc']}",
        f"- Ảnh ngoài bộ dữ liệu: {category['khong_phai_anh_hoc']}",
        f"- Bản chỉnh sửa trùng bản gốc: {category['ban_chinh_sua']}",
        f"- Nhãn OCR khớp chính xác và không lặp, tạm đủ điều kiện nhập database: {database_ready}",
        f"- Nhãn cần người duyệt: {len(review)}", f"- Số quả nhận chắc chắn: {len(accepted)}/{len(codes)}", "",
        "## Mã hộc lặp trong phần đã xác nhận", "",
    ]
    lines.extend(f"- {label}: {len(files)} file" for label, files in sorted(duplicate_labels.items()))
    if not duplicate_labels:
        lines.append("- Không có")
    lines.extend(["", "## Hộc H1-H5 còn thiếu trong các quả đã nhận chắc chắn", ""])
    lines.extend(f"- {code}: {', '.join(hocs) if hocs else 'đủ H1-H5'}" for code, hocs in sorted(missing.items()))
    lines.extend(["", "## File cần duyệt nhãn", ""])
    lines.extend(
        f"- {Path(row['file_goc']).name}: gợi ý {row['ma_hoc_goi_y'] or 'không đọc được'} "
        f"(điểm {row['diem_khop_nhan'] or '0'})"
        for row in review
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def self_check() -> None:
    assert normalize("N1 - V13 - C1 - H2") == "N1V13C1H2"
    label, score, margin, _ = best_label([{"text": "N1 - V13 - C1 - H2"}], ["N1V13C1H1", "N1V13C1H2"])
    assert label == "N1V13C1H2" and score == 1.0 and margin > 0.1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--manager", type=Path, default=Path("/Users/jin/Downloads/quan_ly_tat_ca_mau_28.8.2026_cursor.csv"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output or source / "BANG_KE_HOC.csv"
    if not source.is_dir() or not args.manager.is_file():
        parser.error("Không tìm thấy thư mục nguồn hoặc CSV quản lý")

    self_check()
    codes = read_manager_codes(args.manager)
    images = discover_images(source)
    ocr_paths = [path for path in images if path.name.upper() not in NON_SAMPLE_NAMES and not edited_original(path)]
    records = run_vision(ocr_paths, Path(__file__).with_name("vision_text.swift"))
    rows = build_rows(source, codes, records)
    write_csv(output, rows)
    report = output.with_name("BAO_CAO_HOC.md")
    write_report(report, rows, codes)
    print(f"Đã tạo {output} ({len(rows)} ảnh)")
    print(f"Báo cáo: {report}")


if __name__ == "__main__":
    main()
