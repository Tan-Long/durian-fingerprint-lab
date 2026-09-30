#!/usr/bin/env python3
"""Find blue shell markings and OCR isolated digits; never infer locule counts.

Run in test_video/.venv. Sources stay read-only; output must be new under output/.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "test_video"))
from pattern_map import read_image
from scripts.build_fingerprint_visual_review import jpeg_media, new_output, provenance
from scripts.build_hoc_manifest import run_vision


def candidates(rgb):
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    # ponytail: blue-ink proposal only; faint engravings/other inks need another detector.
    ink = cv2.inRange(hsv, (85, 10, 25), (150, 255, 210))
    r, g, b = np.moveaxis(rgb.astype(float), 2, 0)
    green = ((g > .9*r) & (g > 1.15*b) & (hsv[:,:,1] > 35)).astype(np.uint8)
    contours, _ = cv2.findContours(green, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    body = np.zeros(green.shape, np.uint8)
    if not contours:
        return np.zeros_like(ink), []
    cv2.drawContours(body, [cv2.convexHull(max(contours, key=cv2.contourArea))], -1, 1, -1)
    ink[body == 0] = 0
    size = max(3, round(min(rgb.shape[:2]) / 100))
    joined = cv2.dilate(ink, np.ones((size, size), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(joined)
    boxes = []
    for index in range(1, count):
        x, y, w, h, _ = map(int, stats[index])
        pixels = int(np.count_nonzero(ink[labels == index]))
        if pixels < 8 or min(w, h) < 4 or max(w, h) > min(rgb.shape[:2]) * .15:
            continue
        pad = max(8, size * 2)
        boxes.append([max(0, x-pad), max(0, y-pad), min(rgb.shape[1], x+w+pad), min(rgb.shape[0], y+h+pad)])
    return ink, boxes


def digit_candidates(records):
    # No S->5, I->1, missing-number filling, or workbook-based correction.
    return sorted({text["text"].strip() for record in records for text in record.get("texts", [])
                   if re.fullmatch(r"[1-9]", text["text"].strip())})


def detect(path, output, prefix):
    source = provenance(path)
    rgb = read_image(path, 1800)
    ink, boxes = candidates(rgb)
    paths, groups = [], []
    for index, (x0, y0, x1, y1) in enumerate(boxes):
        variants = []
        mono = 255 - ink[y0:y1, x0:x1]
        for kind, crop in (("rgb", rgb[y0:y1, x0:x1]), ("ink", cv2.cvtColor(mono, cv2.COLOR_GRAY2RGB))):
            for turn in range(4):
                rotated = np.rot90(crop, turn).copy()
                scale = 256 / max(rotated.shape[:2])
                enlarged = cv2.resize(rotated, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                enlarged = cv2.copyMakeBorder(enlarged, 32, 32, 32, 32, cv2.BORDER_CONSTANT, value=(255,255,255))
                item = jpeg_media(output, f"{prefix}-{index}-{kind}-{turn}", "OCR crop", "diagnostic", enlarged, source)
                paths.append(Path(item["source_path"]))
                variants.append(item["source_path"])
        groups.append(variants)
    ocr = run_vision(paths, ROOT / "scripts/vision_text.swift")
    errors = [record["error"] for record in ocr.values() if record.get("error")]
    if errors:
        raise RuntimeError("OCR failed: " + errors[0])
    marked = rgb.copy()
    detections = []
    for index, (box, variants) in enumerate(zip(boxes, groups)):
        reads = [ocr[path] for path in variants]
        values = digit_candidates(reads)
        digit = values[0] if len(values) == 1 else None
        x0, y0, x1, y1 = box
        color = (0,220,80) if digit else (255,150,0)
        cv2.rectangle(marked, (x0,y0), (x1,y1), color, 3)
        cv2.putText(marked, f"{index+1}: {digit or '?'}", (x0,max(20,y0-6)), cv2.FONT_HERSHEY_SIMPLEX, .7, color, 2)
        detections.append({"region": index+1, "box_xyxy": box, "digit_candidate": digit,
                           "alternatives": values, "status": "unverified_ocr" if digit else "unread_or_ambiguous", "ocr": reads})
    if provenance(path)["sha256"] != source["sha256"]:
        raise ValueError("source changed while processing")
    media = [jpeg_media(output, prefix+"-source", "Ảnh nguồn — " + path.name, "query_photo", rgb, source),
             jpeg_media(output, prefix+"-numbers", "Vị trí số đánh dấu — xanh: OCR ứng viên; cam: chưa đọc rõ", "match_overlay", marked, source)]
    return {"source": source, "size_wh": [rgb.shape[1],rgb.shape[0]], "detections": detections}, media


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", action="append", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    output = new_output(args.output_dir)
    results, media = [], []
    for index, path in enumerate(args.image):
        result, images = detect(path, output, f"shell-{index}")
        results.append(result)
        media.extend(images)
    raw = {"mode": "shell_number_ocr", "locule_count": None, "aril_count": None, "images": results}
    pack = {"schema_version": 1, "review_kind": "core_code", "sources": {
        "fixture_only": False, "git_snapshot": subprocess.check_output(["git", "rev-parse", "HEAD"],cwd=ROOT,text=True).strip(),
        "generator": provenance(Path(__file__)), "limits": "Blue markings + local Apple Vision OCR, not natural anatomy segmentation. No labels supplied to OCR."},
        "cases": [{"id": "shell-numbers", "title": "Nhận diện số đánh dấu trên vỏ — chưa phải đếm hộc", "track": "morphology", "sample_ids": [],
        "findings": ["Tự tìm vùng mực xanh trên quả, thử OCR ở bốn góc xoay. Khung xanh chỉ là ứng viên số chưa được duyệt.",
                     "Khung cam là chưa đọc rõ hoặc kết quả mâu thuẫn. Không tự điền số còn thiếu, không lấy số lớn nhất làm tổng hộc.",
                     "Chưa nhận diện ranh giới hộc hoặc số múi. Mực trên cuống, nét gai và bóng có thể gây nhận nhầm."],
        "questions": ["Các khung có trúng số trên vỏ và đọc đúng không?"], "facts": [], "media": media,
        "result_tables": [{"title": "OCR ứng viên — cần kiểm tra trên ảnh", "columns": ["Ảnh", "Vùng", "Số", "Các cách đọc"],
          "rows": [[Path(r["source"]["path"]).name, d["region"], d["digit_candidate"], ", ".join(d["alternatives"])] for r in results for d in r["detections"]]}],
        "raw_result": raw}]}
    (output / "pack.json").write_text(json.dumps(pack,ensure_ascii=False,indent=2)+"\n")
    print(output / "pack.json")
    for result in results:
        print(result["source"]["path"], [(d["region"], d["digit_candidate"], d["alternatives"]) for d in result["detections"]])


if __name__ == "__main__":
    main()
