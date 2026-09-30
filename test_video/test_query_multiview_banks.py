import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from multiview_retrieval_logic import geometric_match, project_features, view_vector
from query_multiview_banks import query_banks, read_bank, read_model


def sample_features():
    xyz = np.random.default_rng(42).uniform((-1, -1, 3), (1, 1, 6), (32, 3))
    points = (xyz[:, :2] / xyz[:, 2:] * 500 + 400).astype(np.float32)
    other = ((xyz[:, :2] + [0.3, 0]) / xyz[:, 2:] * 500 + 400).astype(np.float32)
    features = {"points": points, "descriptors": np.eye(32, 128, dtype=np.float32), "dark": np.zeros(32, bool)}
    return features, {**features, "points": other}


def write_root(root, query, reference, reverse=False):
    root.mkdir()
    vocabulary = np.stack((query["descriptors"][:24].mean(0), query["descriptors"][24:].mean(0)))
    components = np.eye(32, 128, dtype=np.float32)
    if reverse:
        vocabulary, components = vocabulary[::-1], components[::-1]
    np.savez(root / "shared_model.npz", vocabulary=vocabulary, projection_mean=np.zeros(128, np.float32),
             projection_components=components, projection_scale=np.full(32, 1 / 127, np.float32))
    model = read_model(root / "shared_model.npz")
    folder = root / "samples" / "Original-ID" / "session-1"
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps({
        "sample_id": "Original-ID", "session_id": "session-1", "quality_gate": {"status": "READY"},
        "banks": {"CAM_TREN": {}},
    }))
    skipped = root / "samples" / "Review-ID" / "session-2"
    skipped.mkdir(parents=True)
    (skipped / "manifest.json").write_text(json.dumps({"quality_gate": {"status": "REVIEW"}}))
    projected = project_features(reference, model["projection"], quantized=True)
    arrays = dict(counts=np.array([32], np.int16), frame_indexes=np.array([42], np.int32),
                  angle_degrees=np.array([10], np.float32), vectors=view_vector(reference["descriptors"], vocabulary)[None],
                  points=reference["points"].astype(np.float16), dark=reference["dark"],
                  descriptors=np.rint(projected["descriptors"] / model["projection"]["scale"]).astype(np.int8))
    bank_path = folder / "CAM_TREN.bank.npz"
    np.savez(bank_path, **arrays)
    return model, bank_path, arrays


class QueryBanksTest(unittest.TestCase):
    def test_geometric_evidence_and_empty_or_sparse_inputs(self):
        query, reference = sample_features()
        matched = geometric_match(query, reference)
        self.assertGreaterEqual(matched["inliers"], 28)
        self.assertEqual(matched["inliers"], matched["non_dark_inliers"])
        self.assertIsNotNone(matched["visual_transform"])
        for query_count, reference_count in ((0, 0), (0, 32), (32, 0), (32, 1), (1, 32), (7, 7)):
            with self.subTest(query_count=query_count, reference_count=reference_count):
                q = {key: value[:query_count] for key, value in query.items()}
                r = {key: value[:reference_count] for key, value in reference.items()}
                # Empty SIFT outputs currently have float64 dtype.
                if not query_count:
                    q["descriptors"] = q["descriptors"].astype(np.float64)
                if not reference_count:
                    r["descriptors"] = r["descriptors"].astype(np.float64)
                result = geometric_match(q, r)
                self.assertEqual(result["inliers"], 0)
                self.assertIsNone(result["visual_transform"])
        empty = {key: value[:0] for key, value in query.items()}
        self.assertEqual(query_banks(empty, [Path("unused")])["query_issue"], "no query features")

    def test_uses_each_encoder_and_keeps_recorded_ids_and_ready_filter(self):
        query, reference = sample_features()
        with tempfile.TemporaryDirectory() as directory:
            roots = [Path(directory) / "first", Path(directory) / "second"]
            for index, root in enumerate(roots):
                write_root(root, query, reference, reverse=bool(index))
            result = query_banks(query, roots, top_k=1)
        self.assertIsNone(result["identity_verdict"])
        self.assertEqual(len(result["candidates"]), 2)
        self.assertNotEqual(result["roots"][0]["encoder_sha256"], result["roots"][1]["encoder_sha256"])
        self.assertEqual([row["skipped_sessions"] for row in result["roots"]], [1, 1])
        for row in result["candidates"]:
            self.assertEqual((row["sample_id"], row["session_id"], row["camera"]), ("Original-ID", "session-1", "CAM_TREN"))
            self.assertEqual(row["frame_index"], 42)
            self.assertGreaterEqual(row["geometric_inliers"], 28)
            self.assertAlmostEqual(row["coarse_similarity_within_root"], 1, places=5)

    def test_rejects_corrupt_schema_instead_of_reinterpreting_descriptors(self):
        query, reference = sample_features()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            model, path, arrays = write_root(root, query, reference)
            for key, invalid in (("descriptors", arrays["descriptors"].astype(np.float32)),
                                 ("counts", np.array([-1], np.int16)),
                                 ("points", np.zeros((1, 2), np.float32)),
                                 ("vectors", np.array([[np.nan, 0]], np.float32))):
                with self.subTest(key=key):
                    np.savez(path, **{**arrays, key: invalid})
                    with self.assertRaisesRegex(ValueError, key):
                        read_bank(path, model, geometry=True)
            np.savez(path, **{key: value for key, value in arrays.items() if key != "counts"})
            with self.assertRaisesRegex(ValueError, "manifest.json.*counts"):
                query_banks(query, [root])


if __name__ == "__main__":
    unittest.main()
