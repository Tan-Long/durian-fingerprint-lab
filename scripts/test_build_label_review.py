"""Run: python3 -B -m unittest scripts.test_build_label_review"""

import csv
import json
from pathlib import Path
import tempfile
import unittest

from scripts import test_audit_morphology as fixtures
from scripts.audit_morphology import audit
from scripts.build_label_review import build_pack, sha256, write_pack


class LabelReviewTests(unittest.TestCase):
    def fixture(self, root):
        source, inputs = root / "source", root / "inputs"
        source.mkdir()
        inputs.mkdir()
        workbook = fixtures.AuditMorphologyTests().fixture(
            source, fruits=[["F1", "N1", "V1", "C1", 3, 3, None, None]],
            locules=[["F1", 1, 1], ["F1", 2, 1], [None, 3, 1]])
        samples = source / "samples.csv"
        with samples.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["collection_id", "sample_id", "sample_uid"])
            writer.writerow(["august", "N1V1C1", "august/N1V1C1"])
            writer.writerow(["august", "N2V52C3", "august/N2V52C3"])
        audit_path = inputs / "audit.json"
        audit_path.write_text(json.dumps(audit(workbook, samples)))
        summary = inputs / "summary.json"
        summary.write_text(json.dumps({"source_manifests": {str(samples): sha256(samples)}}))
        photo = source / "one.jpg"
        photo.write_bytes(b"test image bytes")
        alias = source / "two.jpg"
        alias.write_bytes(photo.read_bytes())
        media = inputs / "media.csv"
        with media.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["sample_id", "source_path", "destination_sha256", "modality"])
            writer.writerow(["N1V1C1", str(photo), sha256(photo), "random_photo"])
            writer.writerow(["N2V4C3", str(alias), sha256(alias), "random_photo"])
        chamber = source / "chamber.csv"
        with chamber.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["ma_mau", "ma_hoc_goi_y", "file_goc", "ocr_tho", "trang_thai_nhan"])
            writer.writerow(["", "N1V1C1H1", str(alias), "unclear label", "CAN_DUYET_NHAN"])
        return audit_path, media, summary, chamber

    def test_cases_preserve_conflicts_unassigned_rows_and_dedupe_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.fixture(root)
            before = {str(p): sha256(p) for p in (root / "source").iterdir()}
            pack = build_pack(*args)
            cases = {c["id"]: c for c in pack["cases"]}
            conflict = next(c for c in pack["cases"] if c["id"].startswith("identity-"))
            self.assertEqual(conflict["sample_ids"], ["N1V1C1", "N2V4C3"])
            self.assertEqual(len(conflict["media"]), 1)
            self.assertTrue(any("two.jpg" in str(f["value"]) for f in conflict["facts"]))
            count = cases["counts-N1V1C1"]
            self.assertTrue(any("CHƯA GÁN" in f["label"] and "A5" in f["source"] for f in count["facts"]))
            self.assertEqual(count["media"][0]["source_path"], str((root / "source" / "one.jpg").resolve()))
            self.assertIn("shell-N1V1C1", cases)
            self.assertEqual(cases["shell-N1V1C1"]["facts"][0]["value"], None)
            self.assertFalse(cases["unmatched-N2V52C3"]["media"])
            write_pack(pack, root / "review" / "pack.json")
            self.assertEqual(before, {str(p): sha256(p) for p in (root / "source").iterdir()})
            self.assertEqual(pack, build_pack(*args))

    def test_changed_source_and_changed_disputed_photo_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.fixture(root)
            (root / "source" / "two.jpg").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "Ảnh tranh chấp đã thay đổi"):
                build_pack(*args)
            (root / "source" / "samples.csv").write_text("changed")
            with self.assertRaisesRegex(ValueError, "Nguồn đã thay đổi"):
                build_pack(*args)

    def test_output_guard_rejects_sources_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pack = build_pack(*self.fixture(root))
            with self.assertRaisesRegex(ValueError, "ngoài thư mục"):
                write_pack(pack, root / "source" / "pack.json")
            output = root / "pack.json"
            output.symlink_to(root / "source" / "labels.xlsx")
            with self.assertRaisesRegex(ValueError, "symlink"):
                write_pack(pack, output)

    def test_existing_preview_is_marked_derived_without_assigning_missing_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.fixture(root)
            preview_root = root / "previews"
            preview = preview_root / "samples" / "N2V52C3" / "capture" / "contact-sheet.jpg"
            preview.parent.mkdir(parents=True)
            preview.write_bytes(b"preview bytes")
            pack = build_pack(*args, preview_roots=[preview_root])
            case = next(c for c in pack["cases"] if c["id"] == "unmatched-N2V52C3")
            self.assertEqual(case["media"][0]["kind"], "rig_preview")
            self.assertIn("chưa xác nhận", case["media"][0]["link_status"])

    def test_observations_are_not_approval_and_unknown_case_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.fixture(root)
            observations = root / "observations.json"
            observations.write_text(json.dumps({"sources": {}, "findings": {"counts-N1V1C1": ["Cần đọc lại nhãn"]}}))
            pack = build_pack(*args, observations_path=observations)
            case = next(c for c in pack["cases"] if c["id"] == "counts-N1V1C1")
            self.assertTrue(any("chưa xác nhận nhãn" in f for f in case["findings"]))
            observations.write_text(json.dumps({"findings": {"nonexistent-case": ["Ghi chú"]}}))
            with self.assertRaisesRegex(ValueError, "không khớp hồ sơ"):
                build_pack(*args, observations_path=observations)

    def test_disputed_then_self_checked_images_are_first_without_losing_media(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.fixture(root)
            unrelated, inspected = root / "source" / "unrelated.jpg", root / "source" / "inspected.jpg"
            unrelated.write_bytes(b"unrelated image")
            inspected.write_bytes(b"visually inspected image")
            with args[1].open(newline="") as handle:
                rows = list(csv.reader(handle))
            rows.insert(1, ["N1V1C1", str(unrelated), sha256(unrelated), "random_photo"])
            rows.append(["N1V1C1", str(inspected), sha256(inspected), "random_photo"])
            with args[1].open("w", newline="") as handle:
                csv.writer(handle).writerows(rows)
            observations = root / "observations.json"
            observations.write_text(json.dumps({"sources": {"inspected.jpg": sha256(inspected)}, "findings": {}}))
            before = build_pack(*args)
            after = build_pack(*args, observations_path=observations)
            for original, ordered in zip(before["cases"], after["cases"]):
                self.assertEqual({m["id"] for m in original["media"]}, {m["id"] for m in ordered["media"]})
            identity = next(c for c in after["cases"] if c["id"].startswith("identity-"))
            self.assertEqual(Path(identity["media"][0]["source_path"]).name, "one.jpg")
            self.assertEqual(Path(identity["media"][1]["source_path"]).name, "inspected.jpg")
            count = next(c for c in after["cases"] if c["id"] == "counts-N1V1C1")
            self.assertEqual(Path(count["media"][0]["source_path"]).name, "inspected.jpg")


if __name__ == "__main__":
    unittest.main()
