#!/usr/bin/env python3
"""Create a read-only migration plan for the August 2026 durian collection."""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path


COLLECTION = "202608_RIG_V1"
PHOTO_ROOT = Path("/Volumes/SoilTECH/Ảnh chụp sầu riêng")
RIG_ROOT = Path("/Volumes/SoilTECH/DurianScan")
MANAGER = Path("/Users/jin/Downloads/quan_ly_tat_ca_mau_28.8.2026_cursor.csv")
TARGET = Path("/Volumes/SoilTECH/DurianData/collections") / COLLECTION
SESSIONS = {"27082026": "20260827", "28082026": "20260828"}
JUNK_SUFFIXES = {".aae"}
FIELDS = [
    "action", "collection_id", "sample_id", "session_date", "capture_id", "modality",
    "mount_method", "quality", "dataset_eligible", "source_path",
    "destination_path", "size_bytes", "sha256_status", "reason",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def manager_codes() -> list[str]:
    with MANAGER.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) != 89 or any(len(row) != 12 for row in rows):
        raise ValueError("CSV quản lý không còn đúng 88 mẫu/12 cột")
    codes = [row[1].strip() for row in rows[1:]]
    if len(codes) != len(set(codes)):
        raise ValueError("CSV quản lý có mã lặp")
    return codes


def is_junk(path: Path) -> bool:
    return path.name == ".DS_Store" or path.name.startswith("._") or path.suffix.lower() in JUNK_SUFFIXES


def plan_row(path: Path, destination: Path | None, **values: str) -> dict[str, str]:
    return {
        "action": values.get("action", "COPY"),
        "collection_id": COLLECTION,
        "sample_id": values.get("sample_id", ""),
        "session_date": values.get("session_date", ""),
        "capture_id": values.get("capture_id", ""),
        "modality": values.get("modality", ""),
        "mount_method": values.get("mount_method", ""),
        "quality": values.get("quality", "UNREVIEWED"),
        "dataset_eligible": values.get("dataset_eligible", "REVIEW"),
        "source_path": str(path),
        "destination_path": str(destination) if destination else "",
        "size_bytes": str(path.stat().st_size),
        "sha256_status": values.get("sha256_status", "PENDING_COPY"),
        "reason": values.get("reason", ""),
    }


def qc_by_session() -> dict[str, dict[str, str]]:
    result = {}
    for day in SESSIONS:
        path = RIG_ROOT / day / "VIDEO_QUALITY_QC.csv"
        if path.is_file():
            result.update({row["session_id"]: row for row in read_csv(path) if row.get("session_id")})
    return result


def normalize_rig_sample(folder_name: str, qc: dict[str, str] | None) -> tuple[str, str]:
    if qc and qc.get("base_sample_id"):
        return qc["base_sample_id"], "MOC" if qc.get("moc", "").lower() == "yes" else "STANDARD"
    if folder_name == "N1V4C1_MOC_BONUS":
        return "N1V4C1_BONUS", "MOC"
    mount = "MOC" if "MOC" in folder_name.upper() else "STANDARD"
    sample = re.sub(r"[-_]MOC(?:_BONUS)?$", "", folder_name, flags=re.IGNORECASE)
    if folder_name.upper().endswith("_MOC_BONUS"):
        sample += "_BONUS"
    return sample, mount


def quality_from_qc(qc: dict[str, str] | None, mount: str) -> tuple[str, str]:
    status = (qc or {}).get("final_status", "").upper()
    if status == "PASS":
        return "PASS", "REVIEW" if mount == "MOC" else "YES"
    if status in {"FAIL", "IGNORE_DUPLICATE", "EXCLUDED"}:
        return "EXCLUDED", "NO"
    return "REVIEW", "REVIEW"


def plan_rig(codes: set[str]) -> list[dict[str, str]]:
    rows = []
    qc_rows = qc_by_session()
    for day, session_date in SESSIONS.items():
        session_root = RIG_ROOT / day
        for path in sorted(p for p in session_root.rglob("*") if p.is_file()):
            relative = path.relative_to(session_root)
            top = relative.parts[0]
            if is_junk(path):
                rows.append(plan_row(path, None, action="EXCLUDE", quality="EXCLUDED", dataset_eligible="NO", reason="macOS/iPhone sidecar"))
                continue
            if top in {"Demo1", "Test5", "recently_deleted"}:
                rows.append(plan_row(path, None, action="EXCLUDE", quality="EXCLUDED", dataset_eligible="NO", reason="calibration/deleted data"))
                continue
            if top == "processed_multiview_v1":
                rows.append(plan_row(path, None, action="EXCLUDE", quality="EXCLUDED", dataset_eligible="NO", reason="incomplete prototype output"))
                continue
            if len(relative.parts) == 1 and path.suffix.lower() in {".csv", ".md"}:
                destination = TARGET / "manifests" / "source" / "rig" / f"session_{session_date}" / path.name
                rows.append(plan_row(path, destination, modality="manifest", session_date=session_date, quality="PASS", dataset_eligible="NO"))
                continue

            capture_id = relative.parts[1] if len(relative.parts) > 1 else ""
            qc = qc_rows.get(capture_id)
            sample, mount = normalize_rig_sample(top, qc)
            quality, eligible = quality_from_qc(qc, mount)
            if sample not in codes:
                destination = TARGET / "staging" / "unverified" / "rig" / "invalid_sample_id" / relative
                rows.append(plan_row(path, destination, sample_id=sample, session_date=session_date, capture_id=capture_id, modality="rig", mount_method=mount, quality="REVIEW", dataset_eligible="REVIEW", reason="sample_id not confirmed in samples manager"))
                continue
            branch = "rig_moc_variant" if mount == "MOC" else "rig_standard"
            destination = TARGET / "samples" / sample / "raw" / branch / f"session_{session_date}" / Path(*relative.parts[1:])
            rows.append(plan_row(path, destination, sample_id=sample, session_date=session_date, capture_id=capture_id, modality="rig", mount_method=mount, quality=quality, dataset_eligible=eligible, reason=(qc or {}).get("reason_vi", (qc or {}).get("note", ""))))
    return rows


def chamber_manifest() -> dict[str, dict[str, str]]:
    path = PHOTO_ROOT / "Chụp Hộc" / "BANG_KE_HOC.csv"
    return {row["file_goc"]: row for row in read_csv(path)} if path.is_file() else {}


def plan_photos() -> list[dict[str, str]]:
    rows = []
    hoc = chamber_manifest()
    sorted_root = PHOTO_ROOT / "DA_SAP_XEP_28082026"
    chamber_root = PHOTO_ROOT / "Chụp Hộc"
    duplicate_root = PHOTO_ROOT / "N2V3C2"
    for path in sorted(p for p in PHOTO_ROOT.rglob("*") if p.is_file()):
        if is_junk(path):
            rows.append(plan_row(path, None, action="EXCLUDE", quality="EXCLUDED", dataset_eligible="NO", reason="macOS/iPhone sidecar"))
            continue
        if path.is_relative_to(duplicate_root):
            canonical = sorted_root / "N2V3C2" / path.relative_to(duplicate_root)
            rows.append(plan_row(path, canonical, action="SKIP_DUPLICATE", sample_id="N2V3C2", modality="random_photo", quality="REVIEW", dataset_eligible="NO", sha256_status="VERIFIED_DUPLICATE", reason="identical copy exists in DA_SAP_XEP_28082026/N2V3C2"))
            continue
        if path.is_relative_to(chamber_root):
            if path.name in {"BANG_KE_HOC.csv", "BAO_CAO_HOC.md"}:
                destination = TARGET / "manifests" / "source" / "chamber_photos" / path.name
                rows.append(plan_row(path, destination, modality="manifest", quality="PASS", dataset_eligible="NO"))
            else:
                info = hoc.get(str(path), {})
                destination = TARGET / "staging" / "unverified" / "chamber_photos" / path.relative_to(chamber_root)
                rows.append(plan_row(path, destination, sample_id=info.get("ma_mau", ""), modality="chamber_photo", quality="REVIEW", dataset_eligible="REVIEW", reason="chamber label not human-verified"))
            continue
        if path.is_relative_to(sorted_root):
            relative = path.relative_to(sorted_root)
            if path.name == "BANG_KE_ANH.csv":
                destination = TARGET / "manifests" / "source" / "random_photos" / path.name
                rows.append(plan_row(path, destination, modality="manifest", quality="PASS", dataset_eligible="NO"))
            else:
                sample = relative.parts[0] if relative.parts else ""
                destination = TARGET / "staging" / "unverified" / "random_photos" / "by_sample_unverified" / relative
                rows.append(plan_row(path, destination, sample_id=sample, modality="random_photo", quality="REVIEW", dataset_eligible="REVIEW", reason="existing folder assignment not fully audited"))
            continue
        destination = TARGET / "staging" / "unverified" / "random_photos" / "source_dump" / path.relative_to(PHOTO_ROOT)
        rows.append(plan_row(path, destination, modality="random_photo", quality="UNREVIEWED", dataset_eligible="REVIEW", reason="unassigned source photo"))
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def write_report(path: Path, rows: list[dict[str, str]], codes: list[str]) -> None:
    actions = Counter(row["action"] for row in rows)
    modalities = Counter(row["modality"] for row in rows if row["action"] == "COPY")
    bytes_by_action = Counter()
    for row in rows:
        bytes_by_action[row["action"]] += int(row["size_bytes"])
    destinations = [row["destination_path"] for row in rows if row["action"] == "COPY"]
    collisions = [path for path, count in Counter(destinations).items() if count > 1]
    invalid = sorted({row["sample_id"] for row in rows if "not confirmed" in row["reason"]})
    excluded_reasons = Counter(row["reason"] for row in rows if row["action"] == "EXCLUDE")
    rig_captures = {(row["sample_id"], row["capture_id"], row["mount_method"], row["quality"]) for row in rows if row["modality"] == "rig" and row["capture_id"]}
    capture_quality = Counter(item[3] for item in rig_captures)
    capture_mount = Counter(item[2] for item in rig_captures)
    lines = [
        "# Migration dry-run — 202608_RIG_V1", "",
        "Không có ảnh/video nào được copy hoặc xoá trong bước này.", "",
        f"- Tổng file đã kiểm kê: {len(rows):,}",
        f"- Dự kiến copy: {actions['COPY']:,} file ({bytes_by_action['COPY'] / 2**30:.2f} GiB)",
        f"- Loại khỏi kho mới: {actions['EXCLUDE']:,} file ({bytes_by_action['EXCLUDE'] / 2**30:.2f} GiB)",
        f"- Bỏ bản trùng đã xác minh: {actions['SKIP_DUPLICATE']:,} file",
        f"- Trùng đường dẫn đích: {len(collisions)}", "",
        f"- Capture rig: {len(rig_captures)} ({', '.join(f'{key}: {value}' for key, value in sorted(capture_quality.items()))})",
        f"- Kiểu treo: {', '.join(f'{key}: {value}' for key, value in sorted(capture_mount.items()))}", "",
        "## File dự kiến copy theo loại", "",
    ]
    lines.extend(f"- {name or 'unknown'}: {count:,}" for name, count in sorted(modalities.items()))
    lines.extend(["", "## Mã cần duyệt", ""])
    lines.extend(f"- {sample}" for sample in invalid)
    if not invalid:
        lines.append("- Không có")
    lines.extend(["", "## Lý do loại khỏi kho mới", ""])
    lines.extend(f"- {reason}: {count:,} file" for reason, count in excluded_reasons.most_common())
    lines.extend(["", "## Nguồn được phép", "", f"- {PHOTO_ROOT}", f"- {RIG_ROOT}", f"- {MANAGER} (chỉ copy manifest)", "", "Mọi thư mục SoilTECH khác nằm ngoài phạm vi."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def self_check() -> None:
    assert normalize_rig_sample("N1V6C2_MOC", None) == ("N1V6C2", "MOC")
    assert normalize_rig_sample("N1V4C1_MOC_BONUS", None) == ("N1V4C1_BONUS", "MOC")
    assert not is_junk(Path("IMG_0001.JPG")) and is_junk(Path("._IMG_0001.JPG"))


def write_summary(path: Path, rows: list[dict[str, str]]) -> None:
    grouped = {}
    keys = ["action", "sample_id", "session_date", "capture_id", "modality", "mount_method", "quality", "dataset_eligible", "reason"]
    for row in rows:
        key = tuple(row[field] for field in keys)
        item = grouped.setdefault(key, {field: row[field] for field in keys} | {"file_count": 0, "size_bytes": 0})
        item["file_count"] += 1
        item["size_bytes"] += int(row["size_bytes"])
    fields = keys + ["file_count", "size_bytes"]
    write_csv(path, sorted(grouped.values(), key=lambda item: tuple(str(item[field]) for field in keys)), fields)


def main() -> None:
    self_check()
    if not PHOTO_ROOT.is_dir() or not RIG_ROOT.is_dir() or not MANAGER.is_file():
        raise SystemExit("Thiếu một trong ba nguồn đã được phê duyệt")
    codes = manager_codes()
    manager_destination = TARGET / "manifests" / "source" / "samples" / MANAGER.name
    rows = [plan_row(MANAGER, manager_destination, modality="manifest", quality="PASS", dataset_eligible="NO")] + plan_rig(set(codes)) + plan_photos()
    output = TARGET / "manifests" / "dry_run"
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "migration_dry_run.csv", rows, FIELDS)
    write_summary(output / "migration_summary.csv", rows)
    sample_rows = [{"collection_id": COLLECTION, "sample_id": code, "sample_uid": f"{COLLECTION}/{code}", "status": "UNREVIEWED"} for code in codes]
    write_csv(output / "samples_dry_run.csv", sample_rows, ["collection_id", "sample_id", "sample_uid", "status"])
    write_report(output / "MIGRATION_DRY_RUN_REPORT.md", rows, codes)
    for sidecar in output.glob("._*"):
        sidecar.unlink()
    print(output)


if __name__ == "__main__":
    main()
