#!/usr/bin/env python3
"""Index existing collection media without copying, decoding, or relabeling it.

Run: python3 scripts/build_dataset_index.py COLLECTION --output output/data-index
The result is an inventory, not a training split or approval of sample labels.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from apply_durian_data_migration import sha256


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".dng", ".webp"}
SAMPLE_FIELDS = ["collection_id", "sample_id", "sample_uid", "status"]
MEDIA_FIELDS = [
    "collection_id", "sample_id", "sample_uid", "sample_link_status",
    "session_date", "capture_id", "camera", "modality", "mount_method",
    "quality", "dataset_eligible", "source_path", "destination_path",
    "destination_exists", "destination_sha256", "verification_status",
    "reason", "manifest_path", "manifest_row",
]


def checked_reader(handle, required: list[str]) -> csv.DictReader:
    reader = csv.DictReader(handle)
    missing = set(required) - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"{handle.name}: missing columns {sorted(missing)}")
    return reader


def build_index(collection: Path, output: Path) -> dict:
    collection, output = collection.resolve(), output.resolve()
    if output.is_relative_to(collection):
        raise ValueError("Output must be outside the read-only collection; use output/data-index")
    samples_path = collection / "manifests/samples.csv"
    files_path = collection / "manifests/files.csv"
    with samples_path.open(encoding="utf-8-sig", newline="") as handle:
        samples = list(checked_reader(handle, SAMPLE_FIELDS))
    by_sample = {}
    for row in samples:
        key = (row["collection_id"], row["sample_id"])
        if not all(key) or not row["sample_uid"] or key in by_sample:
            raise ValueError(f"Empty or duplicate sample identity in {samples_path}: {key}")
        by_sample[key] = row
    if len({row["sample_uid"] for row in samples}) != len(samples):
        raise ValueError(f"Duplicate sample_uid in {samples_path}")

    media, scanned = [], 0
    counts = Counter()
    required = [field for field in MEDIA_FIELDS if field not in {
        "sample_uid", "sample_link_status", "camera", "destination_exists", "manifest_path", "manifest_row",
    }] + ["action"]
    with files_path.open(encoding="utf-8-sig", newline="") as handle:
        for line, row in enumerate(checked_reader(handle, required), 2):
            scanned += 1
            path = Path(row["destination_path"])
            modality = row["modality"]
            selected = (
                modality == "rig" and path.name.lower() == "rgb.mp4"
                or modality in {"random_photo", "chamber_photo"} and path.suffix.lower() in IMAGE_SUFFIXES
            )
            if row["action"] != "COPY" or not selected:
                continue
            sample = by_sample.get((row["collection_id"], row["sample_id"]))
            record = {field: row.get(field, "") for field in MEDIA_FIELDS}
            record.update(
                sample_uid=sample["sample_uid"] if sample else "",
                sample_link_status="RECORDED_UNVERIFIED" if sample else "UNRESOLVED",
                camera=next((part for part in reversed(path.parts) if part in {"CAM_TREN", "CAM_DUOI"}), ""),
                destination_exists="YES" if path.is_file() else "NO",
                manifest_path=str(files_path), manifest_row=str(line),
            )
            media.append(record)
            if sample:
                counts[(sample["sample_uid"], modality)] += 1

    summary = {
        "collection": str(collection),
        "source_manifests": {str(path): sha256(path) for path in (samples_path, files_path)},
        "sample_records": len(samples), "manifest_file_records": scanned,
        "media_records": len(media),
        "media_by_modality": dict(Counter(row["modality"] for row in media)),
        "missing_media_files": sum(row["destination_exists"] == "NO" for row in media),
        "unresolved_media_sample_links": sum(row["sample_link_status"] == "UNRESOLVED" for row in media),
        "samples_with_media": {
            modality: sum(counts[(row["sample_uid"], modality)] > 0 for row in samples)
            for modality in ("rig", "random_photo", "chamber_photo")
        },
        "limitations": [
            "Sample links are copied from source manifests, not human-verified here.",
            "Quality and dataset_eligible are source values, not recognition or training approval.",
            "Media hashes are historical migration values; only manifest hashes and file existence are checked now.",
            "Random photos can contain labels or opened fruit; review content before using as queries.",
            "This collection snapshot may omit newer source files, including morphology workbooks.",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    for name in ("media.csv", "samples.csv", "summary.json"):
        if (output / name).is_symlink():
            raise ValueError(f"Refusing to overwrite a symlink: {output / name}")
    with (output / "media.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MEDIA_FIELDS)
        writer.writeheader()
        writer.writerows(media)
    sample_fields = SAMPLE_FIELDS + ["rig_video_count", "random_photo_count", "chamber_photo_count"]
    with (output / "samples.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=sample_fields)
        writer.writeheader()
        for row in samples:
            writer.writerow({
                **{field: row[field] for field in SAMPLE_FIELDS},
                "rig_video_count": counts[(row["sample_uid"], "rig")],
                "random_photo_count": counts[(row["sample_uid"], "random_photo")],
                "chamber_photo_count": counts[(row["sample_uid"], "chamber_photo")],
            })
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("collection", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = build_index(args.collection, args.output)
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
