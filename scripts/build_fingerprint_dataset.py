#!/usr/bin/env python3
"""Build a read-only canonical fingerprint dataset from SoilTECH sources.

Run:
  python3 -B scripts/build_fingerprint_dataset.py \
    --enrollment-root /Volumes/SoilTECH/DurianScan \
    --query-root '/Volumes/SoilTECH/Ảnh chụp sầu riêng' \
    --output output/fingerprint-dataset-v1
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


FIELDS = [
    "asset_id", "fruit_id", "role", "capture_session_id", "captured_at",
    "captured_at_source", "camera_id", "media_type", "source_path", "raw_path",
    "label_status", "label_provenance", "split", "sha256", "bytes", "notes",
]
IMAGE_SUFFIXES = {".heic", ".heif", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".dng", ".webp"}
QUERY_DIR = re.compile(r"^(N\d+V\d+C\d+)(?:_(LAN_\d+|BONUS))?$")
ENROLLMENT_DIR = re.compile(r"^(N\d+V\d+C\d+)(?:[-_].*)?$")
SESSION_TIME = re.compile(r"^(\d{8})-(\d{6})")
CAMERAS = {"CAM_TREN", "CAM_DUOI"}
SPLIT_SEED = "durian-fingerprint-pilot-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def asset_id(role: str, source: Path) -> str:
    digest = hashlib.sha256(f"{role}\0{source}".encode()).hexdigest()[:20]
    return f"{'enr' if role == 'enrollment' else 'qry'}-{digest}"


def split_fruits(fruit_ids: set[str], calibration_fruits: int) -> dict[str, str]:
    if not 0 < calibration_fruits < len(fruit_ids):
        raise ValueError("calibration-fruits must leave nonempty dev and calibration sets")
    ranked = sorted(
        fruit_ids,
        key=lambda fruit: hashlib.sha256(f"{SPLIT_SEED}\0{fruit}".encode()).hexdigest(),
    )
    calibration = set(ranked[:calibration_fruits])
    return {fruit: "calibration" if fruit in calibration else "dev" for fruit in fruit_ids}


def source_file(path: Path) -> Path:
    resolved = path.resolve(strict=True)
    if path.is_symlink() or not resolved.is_file():
        raise ValueError(f"source must be a regular non-symlink file: {path}")
    return resolved


def captured_at(session: str) -> tuple[str, str]:
    match = SESSION_TIME.match(session)
    if not match:
        return "", "unknown"
    value = datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S")
    return value.isoformat(timespec="seconds") + "+07:00", "folder_date"


def discover_queries(root: Path) -> tuple[list[dict[str, str]], set[str]]:
    records, fruit_ids = [], set()
    for folder in sorted(root.iterdir(), key=lambda path: path.name):
        match = QUERY_DIR.fullmatch(folder.name)
        if not match or not folder.is_dir() or folder.is_symlink():
            continue
        fruit_id = match.group(1)
        fruit_ids.add(fruit_id)
        session = f"query-{folder.name}"
        for path in sorted(folder.iterdir(), key=lambda item: item.name.casefold()):
            if (not path.is_file() or path.name.startswith("._")
                    or path.suffix.lower() not in IMAGE_SUFFIXES):
                continue
            source = source_file(path)
            records.append({
                "fruit_id": fruit_id,
                "role": "query",
                "capture_session_id": session,
                "captured_at": "",
                "captured_at_source": "unknown",
                "camera_id": "PHONE",
                "media_type": "photo",
                "source_path": str(source),
                "label_status": "confirmed",
                "notes": "",
            })
    if not records:
        raise ValueError(f"no query images found in {root}")
    return records, fruit_ids


def discover_enrollments(root: Path) -> tuple[list[dict[str, str]], dict[str, set[str]]]:
    records = []
    cameras_by_session: dict[str, set[str]] = defaultdict(set)
    for date_root in sorted(root.iterdir(), key=lambda path: path.name):
        if not date_root.is_dir() or not re.fullmatch(r"\d{8}", date_root.name):
            continue
        for fruit_root in sorted(date_root.iterdir(), key=lambda path: path.name):
            match = ENROLLMENT_DIR.fullmatch(fruit_root.name)
            if not match or not fruit_root.is_dir():
                continue
            fruit_id = match.group(1)
            for path in sorted(fruit_root.glob("*/CAM_*/rgb.mp4")):
                camera = path.parent.name
                if camera not in CAMERAS:
                    continue
                source = source_file(path)
                session_name = path.parent.parent.name
                session = f"{date_root.name}-{session_name}"
                timestamp, timestamp_source = captured_at(session_name)
                cameras_by_session[f"{fruit_id}/{session}"].add(camera)
                records.append({
                    "fruit_id": fruit_id,
                    "role": "enrollment",
                    "capture_session_id": session,
                    "captured_at": timestamp,
                    "captured_at_source": timestamp_source,
                    "camera_id": camera,
                    "media_type": "video",
                    "source_path": str(source),
                    "label_status": "confirmed",
                    "notes": f"source_folder={fruit_root.name}",
                })
    return records, cameras_by_session


def validate_content_labels(records: list[dict[str, str]]) -> dict[str, list[str]]:
    by_hash: dict[str, list[dict[str, str]]] = defaultdict(list)
    for record in records:
        source = Path(record["source_path"])
        record["sha256"] = sha256(source)
        record["bytes"] = str(source.stat().st_size)
        by_hash[record["sha256"]].append(record)
    conflicts = {
        digest: sorted({row["fruit_id"] for row in rows})
        for digest, rows in by_hash.items()
        if len({row["fruit_id"] for row in rows}) > 1
    }
    if conflicts:
        raise ValueError(f"identical content assigned to different fruit_id values: {conflicts}")
    return {
        digest: [row["source_path"] for row in rows]
        for digest, rows in by_hash.items() if len(rows) > 1
    }


def prepare_output(output: Path, source_roots: tuple[Path, Path]) -> Path:
    output = output.parent.resolve() / output.name
    if output.exists() or output.is_symlink():
        raise ValueError(f"output must be a new path: {output}")
    for source_root in source_roots:
        if output.is_relative_to(source_root):
            raise ValueError("output must be outside read-only source roots")
    return output


def build_dataset(
    enrollment_root: Path,
    query_root: Path,
    output: Path,
    calibration_fruits: int = 12,
    label_provenance: str = "user_confirmed_2026-09-30",
) -> dict:
    enrollment_root = enrollment_root.resolve(strict=True)
    query_root = query_root.resolve(strict=True)
    output = prepare_output(output, (enrollment_root, query_root))
    query_records, query_fruits = discover_queries(query_root)
    enrollment_records, cameras_by_session = discover_enrollments(enrollment_root)
    enrolled_fruits = {row["fruit_id"] for row in enrollment_records}
    positive_fruits = query_fruits & enrolled_fruits
    query_only_fruits = query_fruits - enrolled_fruits
    enrollment_only_fruits = enrolled_fruits - query_fruits
    splits = split_fruits(positive_fruits, calibration_fruits)
    complete_fruits = {
        key.split("/", 1)[0] for key, cameras in cameras_by_session.items() if cameras == CAMERAS
    }
    missing_complete_session = sorted(positive_fruits - complete_fruits)
    enrollment_only_without_complete_session = sorted(enrollment_only_fruits - complete_fruits)

    records = enrollment_records + query_records
    for record in records:
        source = Path(record["source_path"])
        record["asset_id"] = asset_id(record["role"], source)
        record["label_provenance"] = label_provenance
        if record["role"] == "enrollment":
            record["split"] = "enrollment"
            if record["fruit_id"] in enrollment_only_fruits:
                record["notes"] = ";".join(filter(None, (record["notes"], "candidate_only_no_query")))
        elif record["fruit_id"] in query_only_fruits:
            record["split"] = "open_set_dev"
            record["label_status"] = "unregistered"
        else:
            record["split"] = splits[record["fruit_id"]]
        extension = source.suffix.lower()
        record["raw_path"] = str(Path("raw") / record["role"] / record["fruit_id"]
                                 / record["capture_session_id"] / record["camera_id"]
                                 / f"{record['asset_id']}{extension}")
    duplicate_content = validate_content_labels(records)
    records.sort(key=lambda row: (row["role"], row["fruit_id"], row["capture_session_id"],
                                  row["camera_id"], row["source_path"]))

    output.mkdir(parents=True)
    (output / "processed").mkdir()
    for record in records:
        link = output / record["raw_path"]
        link.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(record["source_path"], link)

    manifest = output / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)

    counts = Counter(row["role"] for row in records)
    query_split_by_fruit = {**splits, **{fruit: "open_set_dev" for fruit in query_only_fruits}}
    split_counts = Counter(query_split_by_fruit.values())
    all_fruits = query_fruits | enrolled_fruits
    summary = {
        "schema_version": 1,
        "enrollment_root": str(enrollment_root),
        "query_root": str(query_root),
        "fruit_count": len(all_fruits),
        "positive_fruit_count": len(positive_fruits),
        "enrollment_fruit_count": len(enrolled_fruits),
        "query_fruit_count": len(query_fruits),
        "asset_count": len(records),
        "assets_by_role": dict(sorted(counts.items())),
        "query_fruits_by_split": dict(sorted(split_counts.items())),
        "split_seed": SPLIT_SEED,
        "calibration_fruits": sorted(fruit for fruit, split in splits.items() if split == "calibration"),
        "dev_fruits": sorted(fruit for fruit, split in splits.items() if split == "dev"),
        "enrollment_only_fruits": sorted(enrollment_only_fruits),
        "query_only_fruits": sorted(query_only_fruits),
        "missing_complete_two_camera_session": missing_complete_session,
        "enrollment_only_without_complete_two_camera_session": enrollment_only_without_complete_session,
        "duplicate_content_same_fruit": duplicate_content,
        "manifest_sha256": sha256(manifest),
        "benchmark_ready": not missing_complete_session,
        "limits": [
            "Current query photos are dev/calibration only, never blind 30-day evidence.",
            "Query capture timestamps remain unknown unless independently sourced.",
            "Symlinks depend on the SoilTECH volume remaining mounted at the recorded paths.",
        ],
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enrollment-root", type=Path, required=True)
    parser.add_argument("--query-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--calibration-fruits", type=int, default=12)
    parser.add_argument("--label-provenance", default="user_confirmed_2026-09-30")
    args = parser.parse_args()
    try:
        summary = build_dataset(**vars(args))
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
