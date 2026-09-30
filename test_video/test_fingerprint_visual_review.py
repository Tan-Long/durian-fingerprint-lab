"""Focused synthetic proof; never reads the real dataset."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from scripts import build_fingerprint_visual_review as visual
from test_query_multiview_banks import sample_features, write_root


class VisualReviewTest(unittest.TestCase):
    def test_exact_frame_provenance_and_generated_media(self):
        query, reference = sample_features()
        rgb = np.full((720, 960, 3), (60, 130, 40), np.uint8)
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory).resolve()
            roots = [directory / "bank-a", directory / "bank-b"]
            for reverse, root in enumerate(roots):
                write_root(root, query, reference, reverse=bool(reverse))
            video = directory / "Original-ID/session-1/CAM_TREN/rgb.mp4"
            video.parent.mkdir(parents=True)
            video.write_bytes(b"synthetic decoder stub; not real video")
            image_path = directory / "phone.jpg"
            image_path.write_bytes(b"synthetic image loader stub")
            image_before, video_before = image_path.read_bytes(), video.read_bytes()
            with patch.object(visual, "ROOT", directory), \
                    patch.object(visual, "read_image", return_value=rgb), \
                    patch.object(visual, "fruit_mask", return_value=np.ones((720, 960), bool)), \
                    patch.object(visual, "extract_features", return_value=query), \
                    patch.object(visual, "decode_selected_frames", return_value={42: rgb}) as decode, \
                    patch.object(visual.subprocess, "check_output", return_value="synthetic-git\n"):
                pack = visual.build_pack(directory / "output/demo", image_path, roots)
            fingerprint, pending = pack["cases"]
            self.assertEqual(decode.call_args.args, (video, [42]))
            self.assertEqual(decode.call_args.kwargs, {"size": (960, 720)})
            self.assertEqual(len(fingerprint["media"]), 3)  # One distinct fixture ID.
            for item in fingerprint["media"]:
                path = Path(item["source_path"])
                self.assertEqual(visual.provenance(path)["sha256"], item["sha256"])
                self.assertIsNotNone(cv2.imread(str(path)))
            evidence, = fingerprint["raw_result"]["visual_evidence"]
            self.assertEqual(evidence["source_video"]["path"], str(video))
            self.assertEqual(evidence["reference_size_wh"], [960, 720])
            self.assertEqual(evidence["frame_index_zero_based"], 42)
            self.assertEqual(len(evidence["inlier_correspondences"]), evidence["candidate"]["geometric_inliers"])
            self.assertIsNone(fingerprint["raw_result"]["identity_verdict"])
            self.assertIsNone(fingerprint["raw_result"]["confidence"])
            self.assertEqual(pending["raw_result"], {"status": "no_image_predictor", "predictions": None, "confidence": None})
            self.assertEqual(pending["result_tables"], [])
            self.assertEqual(image_path.read_bytes(), image_before)
            self.assertEqual(video.read_bytes(), video_before)

    def test_native_point_coordinates_only_inliers_and_no_mutation(self):
        q = np.zeros((90, 120, 3), np.uint8)
        r = np.zeros((100, 140, 3), np.uint8)
        features = {"points": np.array([[25, 30], [70, 60]], np.float32), "dark": np.array([False, True])}
        match = {"matches": [cv2.DMatch(0, 0, 0), cv2.DMatch(1, 1, 0)], "inlier_mask": [True, False]}
        rendered, evidence = visual.overlay(q, r, features, features, match, "fixture")
        self.assertEqual(rendered.shape, (164, 284, 3))
        self.assertEqual(evidence["reference_offset_xy"], [144, 64])
        self.assertEqual(evidence["query_offset_xy"], [0, 64])
        point, = evidence["inlier_correspondences"]
        self.assertEqual(point["query_xy"], [25, 30])
        self.assertTrue(point["non_dark"])
        self.assertGreater(rendered[94, 25].sum(), 0)
        self.assertGreater(rendered[94, 169].sum(), 0)
        self.assertFalse(q.any())
        self.assertFalse(r.any())
        features["points"][0] = [2000, 30]
        with self.assertRaisesRegex(ValueError, "outside"):
            visual.overlay(q, r, features, features, match, "fixture")

    def test_output_boundary_and_existing_directory_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory).resolve()
            with patch.object(visual, "ROOT", directory):
                path = visual.new_output(directory / "output/new")
                self.assertTrue(path.is_dir())
                with self.assertRaises(FileExistsError):
                    visual.new_output(path)
                for bad in (directory / "source", directory / "output"):
                    with self.assertRaisesRegex(ValueError, "NEW directory"):
                        visual.new_output(bad)
                (directory / "output/redirect").symlink_to(directory)
                with self.assertRaisesRegex(ValueError, "NEW directory"):
                    visual.new_output(directory / "output/redirect/escape")


if __name__ == "__main__":
    unittest.main()
