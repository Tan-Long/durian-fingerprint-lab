from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from multiview_retrieval_logic import geometric_match, project_features, view_vector
from query_multiview_banks import main, query_banks, query_batch, rank_fruits, read_bank, read_batch, read_model


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
        self.assertEqual(query_banks(empty, [Path("unused")])["fruit_ranking"], [])

    def test_uses_each_encoder_and_keeps_recorded_ids_and_ready_filter(self):
        query, reference = sample_features()
        with tempfile.TemporaryDirectory() as directory:
            roots = [Path(directory) / "first", Path(directory) / "second"]
            for index, root in enumerate(roots):
                write_root(root, query, reference, reverse=bool(index))
            result = query_banks(query, roots, top_k=1)
        self.assertIsNone(result["identity_verdict"])
        self.assertEqual(len(result["candidates"]), 2)
        self.assertEqual(len(result["fruit_ranking"]), 1)
        self.assertEqual(result["fruit_ranking"][0]["supporting_candidate_indexes"], [0, 1])
        self.assertNotEqual(result["roots"][0]["encoder_sha256"], result["roots"][1]["encoder_sha256"])
        self.assertEqual([row["skipped_sessions"] for row in result["roots"]], [1, 1])
        for row in result["candidates"]:
            self.assertEqual((row["sample_id"], row["session_id"], row["camera"]), ("Original-ID", "session-1", "CAM_TREN"))
            self.assertEqual(row["frame_index"], 42)
            self.assertGreaterEqual(row["geometric_inliers"], 28)
            self.assertAlmostEqual(row["coarse_similarity_within_root"], 1, places=5)

    def test_duplicate_sessions_cameras_and_roots_keep_traceable_support(self):
        query, reference = sample_features()
        with tempfile.TemporaryDirectory() as directory:
            roots = [Path(directory) / "first", Path(directory) / "second"]
            for reverse, root in enumerate(roots):
                _, path, _ = write_root(root, query, reference, reverse=bool(reverse))
                # Two READY sessions and two cameras of the same literal ID.
                manifest_path = path.parent / "manifest.json"
                manifest = json.loads(manifest_path.read_text())
                manifest["banks"]["CAM_SIDE"] = {}
                shutil.copyfile(path, path.parent / "CAM_SIDE.bank.npz")
                manifest_path.write_text(json.dumps(manifest))
                other = path.parent.parent / "session-3"
                shutil.copytree(path.parent, other)
                manifest["session_id"] = "session-3"
                (other / "manifest.json").write_text(json.dumps(manifest))
            result = query_banks(query, roots, top_k=4)
            reversed_result = query_banks(query, list(reversed(roots)), top_k=4)
        self.assertEqual(result["fruit_ranking"], reversed_result["fruit_ranking"])
        self.assertEqual(len(result["candidates"]), 8)
        fruit, = result["fruit_ranking"]
        self.assertEqual(fruit["sample_id"], "Original-ID")
        self.assertEqual(fruit["rank"], 1)
        self.assertEqual(fruit["supporting_candidate_indexes"], list(range(8)))
        self.assertEqual(fruit["best_candidate"], result["candidates"][0])
        for row in result["candidates"]:
            self.assertGreaterEqual(row["geometric_inliers"], 28)
        self.assertIsNone(result["identity_verdict"])

    def test_rank_uses_best_geometry_not_support_count_or_coarse_score(self):
        def candidate(sample, session="one", inliers=10, non_dark=8, error=0.5, coarse=0):
            return dict(sample_id=sample, session_id=session, camera="C1", bank_root="root",
                        bank_path=f"root/{sample}/{session}/C1.bank.npz", view_index=0,
                        geometric_inliers=inliers, non_dark_inliers=non_dark,
                        median_epipolar_error_px=error, coarse_similarity_within_root=coarse)

        rows = [candidate("weak", str(i), inliers=9, coarse=1000) for i in range(12)]
        rows += [candidate("B", coarse=999), candidate("A", coarse=-999),
                 candidate("strong", inliers=11), candidate("dark", non_dark=7),
                 candidate("error", error=1), candidate("missing-error", error=None),
                 candidate("A ", coarse=10)]
        ranking = rank_fruits(rows)
        self.assertEqual([row["sample_id"] for row in ranking],
                         ["strong", "A", "A ", "B", "error", "missing-error", "dark", "weak"])
        for ranked in ranking:
            support = [rows[index] for index in ranked["supporting_candidate_indexes"]]
            self.assertEqual(ranked["best_candidate"], support[0])
            self.assertTrue(all(row["sample_id"] == ranked["sample_id"] for row in support))
        reversed_ranking = rank_fruits(list(reversed(rows)))
        self.assertEqual([row["best_candidate"] for row in ranking],
                         [row["best_candidate"] for row in reversed_ranking])
        self.assertEqual(rank_fruits([]), [])

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


class BatchQueryTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("magick"), "existing image loader requires ImageMagick")
    def test_batch_cli_reads_generated_raster_and_emits_evidence(self):
        query, reference = sample_features()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            root = directory / "bank"
            write_root(root, query, reference)
            rng = np.random.default_rng(7)
            raster = rng.integers(0, 100, (240, 240, 3), dtype=np.uint8)
            raster[:, :, 1] += 120  # Generated green texture; no dataset images.
            self.assertTrue(cv2.imwrite(str(directory / "texture.png"), raster))
            batch = directory / "queries.json"
            batch.write_text('[{"query_id":"synthetic","image":"texture.png"}]')
            completed = subprocess.run(
                [sys.executable, "-B", str(Path(__file__).with_name("query_multiview_banks.py")),
                 "--batch", str(batch), "--bank-root", str(root), "--top-k", "1"],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            row, = json.loads(completed.stdout)["queries"]
            self.assertEqual(row["status"], "ok")
            self.assertGreater(row["result"]["query_features"], 0)
            self.assertEqual(len(row["result"]["candidates"]), 1)
            self.assertEqual(row["result"]["fruit_ranking"][0]["sample_id"], "Original-ID")
            self.assertIsNone(row["result"]["identity_verdict"])

    def test_batch_validation_and_relative_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "queries.json"
            invalid = ["", "{", "[]", "{}", "null", '[null]',
                       json.dumps([{"query_id": " ", "image": "photo.jpg"}]),
                       json.dumps([{"query_id": "one", "image": ""}]),
                       json.dumps([{"query_id": "one", "image": 1}]),
                       json.dumps([{"query_id": "one", "image": "a", "extra": True}]),
                       json.dumps([{"query_id": "one"}]),
                       json.dumps([{"query_id": "one", "image": "a\x00.jpg"}]),
                       json.dumps([{"query_id": "same", "image": "a"}] * 2)]
            for value in invalid:
                with self.subTest(value=value):
                    path.write_text(value)
                    with self.assertRaises(ValueError):
                        read_batch(path)
            absolute = str(Path(directory) / "absolute.jpg")
            path.write_text(json.dumps([{"query_id": "phone-1", "image": "relative.jpg"},
                                        {"query_id": "phone-2", "image": absolute}]))
            queries = read_batch(path)
            self.assertEqual(queries, [{"query_id": "phone-1", "image": str(Path(directory).resolve() / "relative.jpg")},
                                       {"query_id": "phone-2", "image": str(Path(absolute).resolve())}])

    def test_batch_reuses_single_image_pipeline_and_continues_after_failure(self):
        query, reference = sample_features()
        with tempfile.TemporaryDirectory() as directory:
            roots = [Path(directory) / "first", Path(directory) / "second"]
            for reverse, root in enumerate(roots):
                write_root(root, query, reference, reverse=bool(reverse))
            queries = [{"query_id": name, "image": str(Path(directory) / f"{name}.jpg")}
                       for name in ("good", "missing", "also-good")]
            image = np.zeros((16, 16, 3), np.uint8)
            with patch("query_multiview_banks.read_image", side_effect=[image, OSError("missing fixture"), image]) as read, \
                    patch("query_multiview_banks.fruit_mask", return_value=np.ones((16, 16), bool)), \
                    patch("query_multiview_banks.extract_features", return_value=query):
                report = query_batch(queries, roots, top_k=1)
            self.assertEqual([call.args for call in read.call_args_list],
                             [(Path(item["image"]), 1000) for item in queries])
        self.assertEqual([row["status"] for row in report["queries"]], ["ok", "error", "ok"])
        self.assertIsNone(report["identity_verdict"])
        self.assertGreaterEqual(report["elapsed_seconds"], 0)
        for row in report["queries"]:
            self.assertGreaterEqual(row["elapsed_seconds"], 0)
            if row["status"] == "ok":
                self.assertIsNone(row["result"]["identity_verdict"])
                self.assertEqual(len(row["result"]["roots"]), 2)
                self.assertEqual(len(row["result"]["fruit_ranking"]), 1)
                for candidate in row["result"]["candidates"]:
                    self.assertGreaterEqual(candidate["geometric_inliers"], 28)
            else:
                self.assertEqual(row["error"], {"type": "OSError", "message": "missing fixture"})
                self.assertNotIn("result", row)

    def test_cli_json_and_failure_exit_preserve_successful_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = Path(directory) / "batch.json"
            batch.write_text(json.dumps([{"query_id": "ok", "image": "ok.jpg"},
                                         {"query_id": "bad", "image": "bad.jpg"}]))
            argv = ["query_multiview_banks.py", "--batch", str(batch), "--bank-root", directory]
            stdout, stderr = io.StringIO(), io.StringIO()
            success = {"candidates": [], "fruit_ranking": [], "identity_verdict": None}
            with patch.object(sys, "argv", argv), redirect_stdout(stdout), redirect_stderr(stderr), \
                    patch("query_multiview_banks.query_image", side_effect=[success, ValueError("bad fixture")]):
                with self.assertRaises(SystemExit) as exc:
                    main()
            self.assertEqual(exc.exception.code, 2)
            report = json.loads(stdout.getvalue())
            self.assertEqual(report["queries"][0]["result"], success)
            self.assertEqual(report["queries"][1]["error"]["message"], "bad fixture")
            self.assertEqual(stderr.getvalue(), "")
            batch.write_text("[]")
            with patch.object(sys, "argv", argv), redirect_stderr(io.StringIO()), \
                    patch("query_multiview_banks.query_image") as query:
                with self.assertRaises(SystemExit) as exc:
                    main()
                self.assertEqual(exc.exception.code, 2)
                query.assert_not_called()

    def test_cli_success_and_single_image_compatibility(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = Path(directory) / "batch.json"
            batch.write_text('[{"query_id":"one","image":"one.jpg"}]')
            for option, path in (("--image", "one.jpg"), ("--batch", str(batch))):
                with self.subTest(option=option):
                    stdout = io.StringIO()
                    with patch.object(sys, "argv", ["query", option, path, "--bank-root", directory]), \
                            redirect_stdout(stdout), patch("query_multiview_banks.query_image", return_value={"identity_verdict": None}):
                        main()
                    result = json.loads(stdout.getvalue())
                    self.assertIsNone(result["identity_verdict"])
                    if option == "--batch":
                        self.assertEqual(result["queries"][0]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
