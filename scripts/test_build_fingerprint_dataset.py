import csv
from pathlib import Path
import tempfile
import unittest

from scripts.build_fingerprint_dataset import build_dataset, sha256


class FingerprintDatasetTests(unittest.TestCase):
    def test_builds_traceable_symlinks_and_keeps_sessions_in_one_split(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            enrollment, query = root / "enrollment", root / "query"
            originals = {}
            for fruit in ("N1V1C1-MOC", "N2V1C1"):
                for camera in ("CAM_TREN", "CAM_DUOI"):
                    path = enrollment / "27082026" / fruit / "20260827-120000-abcd" / camera / "rgb.mp4"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(f"{fruit}-{camera}".encode())
                    originals[path] = path.read_bytes()
            for folder, names in {
                "N1V1C1": ("a.HEIC", "b.JPG"),
                "N1V1C1_LAN_2": ("c.HEIC",),
                "N2V1C1": ("d.HEIC",),
            }.items():
                for name in names:
                    path = query / folder / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(f"{folder}-{name}".encode())
                    originals[path] = path.read_bytes()

            output = root / "output"
            summary = build_dataset(enrollment, query, output, calibration_fruits=1)
            self.assertTrue(summary["benchmark_ready"])
            self.assertEqual(summary["fruit_count"], 2)
            self.assertEqual(summary["assets_by_role"], {"enrollment": 4, "query": 4})
            self.assertEqual(summary["query_fruits_by_split"], {"calibration": 1, "dev": 1})
            self.assertEqual(summary["manifest_sha256"], sha256(output / "manifest.csv"))
            with (output / "manifest.csv").open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len({row["asset_id"] for row in rows}), len(rows))
            n1_splits = {row["split"] for row in rows if row["fruit_id"] == "N1V1C1" and row["role"] == "query"}
            self.assertEqual(len(n1_splits), 1)
            for row in rows:
                link = output / row["raw_path"]
                self.assertTrue(link.is_symlink())
                self.assertEqual(link.resolve(), Path(row["source_path"]))
                self.assertEqual(sha256(link), row["sha256"])
            self.assertEqual({path: path.read_bytes() for path in originals}, originals)
            with self.assertRaisesRegex(ValueError, "new path"):
                build_dataset(enrollment, query, output, calibration_fruits=1)

    def test_rejects_cross_fruit_duplicate_content_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            enrollment, query, output = root / "enrollment", root / "query", root / "output"
            for fruit in ("N1V1C1", "N2V1C1"):
                for camera in ("CAM_TREN", "CAM_DUOI"):
                    video = enrollment / "27082026" / fruit / "20260827-120000-abcd" / camera / "rgb.mp4"
                    video.parent.mkdir(parents=True, exist_ok=True)
                    video.write_bytes(f"{fruit}-{camera}".encode())
                photo = query / fruit / "same.HEIC"
                photo.parent.mkdir(parents=True)
                photo.write_bytes(b"same photo")
            with self.assertRaisesRegex(ValueError, "different fruit_id"):
                build_dataset(enrollment, query, output, calibration_fruits=1)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
