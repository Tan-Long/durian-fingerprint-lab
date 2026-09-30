"""Synthetic contract proof; no real source files accessed."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from scripts import build_rgbd_sample_review as review
from scripts import build_fingerprint_visual_review as visual
from test_query_multiview_banks import sample_features


class RGBDSampleReviewTest(unittest.TestCase):
    def test_metadata_only_sampling_and_independent_clock_bases(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bank.npz"
            # Object descriptors cannot be read with allow_pickle=False: only frame_indexes is accessed.
            np.savez(path, frame_indexes=np.array([8, 2, 2], np.int32), descriptors=np.array([None], object))
            self.assertEqual(review.sampled_indexes(path), [2, 8])
            for bad in (np.array([-1]), np.array([2.5]), np.array([]), np.arange(37), np.zeros((2, 2), int)):
                np.savez(path, frame_indexes=bad)
                with self.assertRaises(ValueError):
                    review.sampled_indexes(path)
            csv = Path(directory) / "timestamps.csv"
            for base in (100.0, 468822.0):
                csv.write_text(f"frame,timestamp_unix\n0,{base}\n2,{base + 0.5}\n8,{base + 2}\n")
                timing = review.timestamps(csv, [2, 8], 0)
                self.assertEqual(timing[8]["seconds_from_cached_light_edge"], 2)
                self.assertEqual(timing[2]["timestamp_unix_recorded"], base + 0.5)
            with self.assertRaisesRegex(ValueError, "missing"):
                review.timestamps(csv, [9], 0)

    def test_two_camera_fixture_fresh_extraction_best_frames_and_layer_contract(self):
        query, reference = sample_features()
        rgb = np.full((720, 960, 3), 80, np.uint8)
        rgba = np.zeros((720, 960, 4), np.uint8)
        rgba[200:400, 200:400] = (0, 255, 0, 100)
        mask = np.ones((720, 960), bool)
        layer_calls = []

        def layers(camera, frame, image, *, include_exterior=False):
            layer_calls.append((camera.name, frame, include_exterior))
            return {"mask": mask, "stats": {"valid_depth_pixels": int(mask.sum())},
                    "layers": {"mask": rgba, "depth": rgba, "confidence": rgba},
                    "sources": {}, "intrinsics": {"note": "synthetic"}}

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory).resolve()
            session, banks = directory / "session", directory / "banks"
            session.mkdir()
            banks.mkdir()
            image = directory / "phone.jpg"
            image.write_bytes(b"explicit synthetic query")
            sync = {"sample_id": "synthetic-F1", "session_id": "session"}
            (session / "sync.json").write_text(json.dumps(sync))
            manifest = {**sync, "quality_gate": {"status": "READY"}, "camera_timing": {}}
            for camera, base in (("CAM_TREN", 100), ("CAM_DUOI", 999000)):
                folder = session / camera
                folder.mkdir()
                (folder / "rgb.mp4").write_bytes(b"decoder fixture")
                (folder / "frame_transforms.csv").write_text(f"frame,timestamp_unix\n0,{base}\n2,{base + 1}\n4,{base + 2}\n")
                np.savez(banks / f"{camera}.bank.npz", frame_indexes=np.array([4, 2]), descriptors=np.array([None], object))
                manifest["camera_timing"][camera] = {"flash_frame": 0}
            (banks / "manifest.json").write_text(json.dumps(manifest))
            with patch.object(visual, "ROOT", directory), patch.object(review, "ROOT", directory), \
                    patch.object(review, "read_image", return_value=rgb), \
                    patch.object(review, "fruit_mask", return_value=mask), \
                    patch.object(review, "extract_features", side_effect=[query, reference, reference, reference, reference]) as extract, \
                    patch.object(review, "read_layers", side_effect=layers), \
                    patch.object(review, "decode_selected_frames", return_value={2: rgb, 4: rgb}) as decode, \
                    patch.object(review.subprocess, "check_output", return_value="fixture-sha\n"):
                pack = review.build_pack(image, session, banks, directory / "output/new")
            self.assertEqual(extract.call_count, 5)
            self.assertEqual(decode.call_count, 2)
            self.assertEqual([call.args[1] for call in decode.call_args_list], [[2, 4], [2, 4]])
            self.assertEqual(len(layer_calls), 6)
            self.assertEqual(sum(call[2] for call in layer_calls), 2)
            case, = pack["cases"]
            raw = case["raw_result"]
            self.assertEqual(raw["mode"], "known_sample_alignment")
            self.assertEqual(len(raw["sampled_frames"]), 4)
            self.assertEqual([row["frame_index"] for row in raw["best_per_camera"]], [2, 2])
            self.assertEqual([row["seconds_from_cached_light_edge"] for row in raw["best_per_camera"]], [1, 1])
            self.assertNotEqual(raw["best_per_camera"][0]["timestamp_unix_recorded"], raw["best_per_camera"][1]["timestamp_unix_recorded"])
            self.assertIsNone(raw["identity_verdict"])
            self.assertIsNone(raw["confidence"])
            self.assertEqual(pack["sources"]["query"]["sha256"], visual.provenance(image)["sha256"])
            layer_media = [item for item in case["media"] if item["kind"] == "rgbd_layer"]
            self.assertEqual(len(layer_media), 8)
            self.assertEqual(sum(item["layer"] == "rgb" for item in layer_media), 2)
            self.assertEqual(len({item["layer_group"] for item in layer_media}), 2)
            for item in case["media"]:
                self.assertEqual(item["sha256"], visual.provenance(Path(item["source_path"]))["sha256"])

    def test_rgba_flattening_preserves_size_and_inputs(self):
        rgb = np.full((2, 3, 3), 40, np.uint8)
        rgba = np.full((2, 3, 4), (100, 200, 50, 0), np.uint8)
        self.assertTrue(np.array_equal(review.flat_layer(rgb, rgba), rgb))
        rgba[:, :, 3] = 255
        self.assertTrue(np.array_equal(review.flat_layer(rgb, rgba), rgba[:, :, :3]))
        self.assertTrue((rgb == 40).all())
        with self.assertRaisesRegex(ValueError, "exact RGB"):
            review.flat_layer(rgb, rgba[:1])


if __name__ == "__main__":
    unittest.main()
