"""Synthetic exact-frame and confidence proofs; no dataset decoding or writes."""

import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.rgbd_source_layers import read_depth_layers


class RGBDSourceLayersTests(unittest.TestCase):
    def fixture(self, root):
        root = Path(root).resolve()
        (root / "depth").mkdir()
        (root / "confidence").mkdir()
        depth = np.full((192, 256), 1200, np.uint16)
        depth[40:155, 40:210] = 500
        depth[70:75, 70:75] = 0
        confidence = np.full(depth.shape, 2, np.uint8)
        confidence[80:100, 100:120] = 0
        confidence[110:125, 80:100] = 1
        self.assertTrue(cv2.imwrite(str(root / "depth/000007.png"), depth))
        self.assertTrue(cv2.imwrite(str(root / "confidence/000007.png"), confidence))
        (root / "frame_transforms.csv").write_text("frame,timestamp_unix\n1,123.25\n7,456.75\n", encoding="utf-8")
        (root / "odometry.csv").write_text("timestamp, frame, fx, fy, cx, cy\n9, 000001, 9, 9, 9, 9\n10, 000007, 1400, 1401, 950, 720\n", encoding="utf-8")
        rgb = np.full((384, 512, 3), (160, 170, 70), np.uint8)
        return root, rgb

    def test_real_helper_pipeline_exact_frame_sources_no_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root, rgb = self.fixture(directory)
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            result = read_depth_layers(root, 7, rgb)
            self.assertTrue(result["mask"].any())
            self.assertEqual(result["mask"].shape, rgb.shape[:2])
            self.assertEqual(result["mask"].dtype, np.bool_)
            self.assertEqual(result["depth_mm"].dtype, np.uint16)
            self.assertEqual(result["confidence"].dtype, np.uint8)
            self.assertEqual(set(np.unique(result["confidence"])), {0, 1, 2})
            self.assertEqual(set(np.unique(result["depth_mm"])), {0, 500, 1200})
            self.assertEqual(result["timestamp_unix"], 456.75)
            self.assertEqual(result["intrinsics"]["fx"], 1400)
            self.assertFalse(result["intrinsics"]["applied"])
            self.assertIn("NOT rescaled", result["intrinsics"]["coordinate_space"])
            for name, info in result["sources"].items():
                p = Path(info["path"])
                self.assertEqual(info["sha256"], hashlib.sha256(before[p]).hexdigest())
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*") if p.is_file()})
            self.assertEqual(set(result["layers"]), {"mask", "depth", "confidence"})
            for layer in result["layers"].values():
                self.assertEqual(layer.shape, (*rgb.shape[:2], 4))
                self.assertEqual(layer.dtype, np.uint8)

    def test_confidence_and_zero_depth_excluded_even_if_foreground_fills_holes(self):
        with tempfile.TemporaryDirectory() as directory:
            root, rgb = self.fixture(directory)
            with patch("scripts.rgbd_source_layers.registration_mask", return_value=np.ones(rgb.shape[:2], bool)):
                result = read_depth_layers(root, 7, rgb)
            invalid = (result["confidence"] == 0) | (result["depth_mm"] == 0)
            self.assertTrue(invalid.any())
            self.assertFalse(result["mask"][invalid].any())
            self.assertFalse(result["valid_depth_mask"][invalid].any())
            self.assertTrue(result["mask"][result["confidence"] == 1].all())
            self.assertTrue((result["layers"]["depth"][invalid, 3] == 0).all())
            self.assertNotIn("weights", result)

    def test_missing_exact_frame_and_wrong_input_types_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root, rgb = self.fixture(directory)
            with self.assertRaisesRegex(FileNotFoundError, "no nearest-frame substitution"):
                read_depth_layers(root, 8, rgb)
            for frame in (-1, True, 7.5, "7"):
                with self.assertRaisesRegex(ValueError, "nonnegative integer"):
                    read_depth_layers(root, frame, rgb)
            with self.assertRaisesRegex(ValueError, "uint8 RGB"):
                read_depth_layers(root, 7, rgb.astype(np.float32))
            (root / "confidence/000007.png").unlink()
            with self.assertRaisesRegex(FileNotFoundError, "confidence/000007.png"):
                read_depth_layers(root, 7, rgb)

    def test_bad_png_units_dimensions_and_confidence_classes_rejected(self):
        for name, image, diagnostic in [
            ("depth", np.ones((192, 256), np.uint8), "uint16 millimetres"),
            ("depth", np.ones((96, 128), np.uint16), "192x256"),
            ("confidence", np.ones((192, 256), np.uint16), "confidence must be uint8"),
            ("confidence", np.ones((96, 128), np.uint8), "native depth shape"),
            ("confidence", np.full((192, 256), 3, np.uint8), "classes must be 0/1/2"),
        ]:
            with self.subTest(name=name, diagnostic=diagnostic), tempfile.TemporaryDirectory() as directory:
                root, rgb = self.fixture(directory)
                cv2.imwrite(str(root / name / "000007.png"), image)
                with self.assertRaisesRegex(ValueError, diagnostic):
                    read_depth_layers(root, 7, rgb)

    def test_no_valid_central_depth_never_fabricates_foreground(self):
        with tempfile.TemporaryDirectory() as directory:
            root, rgb = self.fixture(directory)
            cv2.imwrite(str(root / "confidence/000007.png"), np.zeros((192, 256), np.uint8))
            with patch("scripts.rgbd_source_layers.registration_mask") as registration:
                result = read_depth_layers(root, 7, rgb)
                registration.assert_not_called()
            self.assertFalse(result["mask"].any())
            self.assertFalse(result["valid_depth_mask"].any())
            self.assertIsNone(result["stats"]["foreground_median_depth_mm"])
            self.assertIn("No valid central depth", result["stats"]["issues"][0])

    def test_optional_detectors_only_run_when_requested_and_row_column_correct(self):
        with tempfile.TemporaryDirectory() as directory:
            root, rgb = self.fixture(directory)
            with patch("scripts.rgbd_source_layers.detect_grooves_2d", return_value=np.ones(rgb.shape[:2], bool)) as grooves, \
                 patch("scripts.rgbd_source_layers.detect_spikes_2d", return_value=[{"tip": [120, 180]}]) as spikes:
                read_depth_layers(root, 7, rgb)
                grooves.assert_not_called()
                spikes.assert_not_called()
                result = read_depth_layers(root, 7, rgb, include_exterior=True)
                grooves.assert_called_once()
                spikes.assert_called_once()
            self.assertTrue(result["layers"]["spike"][120, 184, 3] > 0)
            self.assertEqual(result["layers"]["spike"][180, 124, 3], 0)
            self.assertTrue((result["layers"]["groove"][~result["mask"], 3] == 0).all())
            self.assertIn("NOT internal anatomy", result["stats"]["limits"])
            self.assertEqual(result["stats"]["visible_spike_candidates"], 1)

    def test_missing_metadata_stays_unknown_and_duplicate_frame_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root, rgb = self.fixture(directory)
            (root / "frame_transforms.csv").unlink()
            (root / "odometry.csv").write_text("frame,fx,fy,cx,cy\n0,1,1,1,1\n", encoding="utf-8")
            result = read_depth_layers(root, 7, rgb)
            self.assertIsNone(result["timestamp_unix"])
            self.assertIsNone(result["intrinsics"])
            (root / "frame_transforms.csv").write_text("frame,timestamp_unix\n7,1\n7,2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate metadata rows"):
                read_depth_layers(root, 7, rgb)


if __name__ == "__main__":
    unittest.main()
