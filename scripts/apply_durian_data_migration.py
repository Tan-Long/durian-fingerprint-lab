#!/usr/bin/env python3
"""Apply the approved August 2026 migration plan without deleting sources."""

from __future__ import annotations

import csv
import hashlib
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


TARGET = Path("/Volumes/SoilTECH/DurianData/collections/202608_RIG_V1")
PLAN = TARGET / "manifests" / "dry_run" / "migration_dry_run.csv"
APPROVED_ROOTS = (
    Path("/Volumes/SoilTECH/Ảnh chụp sầu riêng"),
    Path("/Volumes/SoilTECH/DurianScan"),
)
APPROVED_FILE = Path("/Users/jin/Downloads/quan_ly_tat_ca_mau_28.8.2026_cursor.csv")
HASH_FIELDS = ["source_sha256", "destination_sha256", "verification_status", "verified_at"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def approved_source(path: Path) -> bool:
    return path == APPROVED_FILE or any(path.is_relative_to(root) for root in APPROVED_ROOTS)


def validate_row(row: dict[str, str]) -> tuple[Path, Path]:
    source = Path(row["source_path"])
    destination = Path(row["destination_path"])
    if not approved_source(source) or not source.is_file() or source.is_symlink():
        raise ValueError(f"Nguồn ngoài phạm vi hoặc không hợp lệ: {source}")
    if not destination.is_relative_to(TARGET) or destination == TARGET:
        raise ValueError(f"Đích ngoài collection: {destination}")
    return source, destination


def plan_totals() -> tuple[int, int]:
    count = size = 0
    with PLAN.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["action"] == "COPY":
                validate_row(row)
                count += 1
                size += int(row["size_bytes"])
    return count, size


def copy_verified(source: Path, destination: Path) -> tuple[str, str, str]:
    if destination.exists():
        source_hash = sha256(source)
        destination_hash = sha256(destination)
        if source_hash != destination_hash:
            raise RuntimeError(f"File đích đã tồn tại nhưng khác nội dung: {destination}")
        return source_hash, destination_hash, "VERIFIED_EXISTING"

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".partial")
    if partial.exists():
        partial.unlink()
    digest = hashlib.sha256()
    with source.open("rb") as source_handle, partial.open("wb") as destination_handle:
        for chunk in iter(lambda: source_handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
            destination_handle.write(chunk)
    source_hash = digest.hexdigest()
    destination_hash = sha256(partial)
    if source_hash != destination_hash:
        partial.unlink()
        raise RuntimeError(f"Checksum không khớp sau copy: {source}")
    os.replace(partial, destination)
    return source_hash, destination_hash, "COPIED_AND_VERIFIED"


def self_check() -> None:
    assert approved_source(APPROVED_FILE)
    assert approved_source(APPROVED_ROOTS[0] / "IMG_0001.HEIC")
    assert not approved_source(Path("/Volumes/SoilTECH/66-Durian/file"))


def main() -> None:
    self_check()
    if not PLAN.is_file():
        raise SystemExit("Không tìm thấy migration_dry_run.csv")
    total_files, total_bytes = plan_totals()
    free_bytes = shutil.disk_usage(TARGET).free
    if free_bytes < total_bytes * 3:
        raise SystemExit("Không đủ vùng trống an toàn trên SoilTECH")

    manifests = TARGET / "manifests"
    logs = TARGET / "logs"
    manifests.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    output = manifests / "files.csv"
    temporary = output.with_suffix(".csv.tmp")
    log_path = logs / "migration_copy.log"
    started = datetime.now().astimezone()
    copied = existing = copied_bytes = 0

    with PLAN.open(encoding="utf-8-sig", newline="") as source_plan, \
         temporary.open("w", encoding="utf-8-sig", newline="") as result_handle, \
         log_path.open("a", encoding="utf-8") as log:
        reader = csv.DictReader(source_plan)
        fields = list(reader.fieldnames or []) + HASH_FIELDS
        writer = csv.DictWriter(result_handle, fieldnames=fields)
        writer.writeheader()
        log.write(f"{started.isoformat(timespec='seconds')} START files={total_files} bytes={total_bytes}\n")
        for row in reader:
            if row["action"] != "COPY":
                continue
            source, destination = validate_row(row)
            source_hash, destination_hash, status = copy_verified(source, destination)
            row.update({
                "source_sha256": source_hash,
                "destination_sha256": destination_hash,
                "verification_status": status,
                "verified_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            })
            writer.writerow(row)
            copied_bytes += int(row["size_bytes"])
            if status == "COPIED_AND_VERIFIED":
                copied += 1
            else:
                existing += 1
            done = copied + existing
            if done % 1000 == 0 or done == total_files:
                result_handle.flush()
                message = f"COPY {done}/{total_files} {copied_bytes / 2**30:.2f}/{total_bytes / 2**30:.2f} GiB"
                print(message, flush=True)
                log.write(f"{datetime.now().astimezone().isoformat(timespec='seconds')} {message}\n")
                log.flush()

        finished = datetime.now().astimezone()
        log.write(f"{finished.isoformat(timespec='seconds')} COMPLETE copied={copied} existing={existing}\n")
    os.replace(temporary, output)

    samples_dry_run = manifests / "dry_run" / "samples_dry_run.csv"
    shutil.copyfile(samples_dry_run, manifests / "samples.csv")
    report = manifests / "MIGRATION_COPY_REPORT.md"
    report.write_text(
        "# Migration copy report — 202608_RIG_V1\n\n"
        f"- Bắt đầu: {started.isoformat(timespec='seconds')}\n"
        f"- Hoàn tất: {finished.isoformat(timespec='seconds')}\n"
        f"- File mới đã copy và xác minh SHA-256: {copied:,}\n"
        f"- File có sẵn đã xác minh: {existing:,}\n"
        f"- Dung lượng logic: {total_bytes / 2**30:.2f} GiB\n"
        "- File nguồn đã xoá: 0\n"
        "- Phạm vi ngoài hai nguồn được duyệt đã chạm: 0\n",
        encoding="utf-8",
    )
    for sidecar in TARGET.rglob("._*"):
        if sidecar.is_file():
            sidecar.unlink()
    print(report, flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"STOP: {error}", file=sys.stderr, flush=True)
        raise
