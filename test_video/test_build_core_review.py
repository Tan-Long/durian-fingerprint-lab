"""Synthetic-only proof: .venv Python -B -m unittest discover -s test_video -p test_build_core_review.py"""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

from scripts.build_core_review import build_pack, main
from scripts.serve_label_review import ReviewStore


class CoreReviewTest(unittest.TestCase):
    def test_two_cases_contain_executed_results_and_store_accepts_pack(self):
        pack = build_pack()
        self.assertEqual(pack["review_kind"], "core_code")
        self.assertTrue(pack["sources"]["fixture_only"])
        fingerprint, morphology = pack["cases"]
        self.assertEqual([row["id"] for row in pack["cases"]], ["fingerprint-core", "morphology-core"])
        result = fingerprint["raw_result"]
        self.assertEqual(len(result["candidates"]), 2)
        self.assertEqual(result["fruit_ranking"][0]["supporting_candidate_indexes"], [0, 1])
        self.assertIsNone(result["identity_verdict"])
        self.assertNotEqual(result["roots"][0]["encoder_sha256"], result["roots"][1]["encoder_sha256"])
        self.assertTrue(all(row["geometric_inliers"] >= 28 for row in result["candidates"]))
        metrics = morphology["raw_result"]["output"]["targets"]["locule_count"]["metrics"]
        self.assertEqual(metrics["mae"], 2)
        self.assertAlmostEqual(metrics["rmse"], math.sqrt(5))
        self.assertEqual(metrics["bias"], -1)
        self.assertEqual(morphology["result_tables"][0]["rows"][0], ["locule_count", "synthetic-F3", 6, 3.0])
        for case in pack["cases"]:
            self.assertEqual(case["media"], [])
            for table in case["result_tables"]:
                self.assertTrue(table["rows"])
                for row in table["rows"]:
                    self.assertEqual(len(row), len(table["columns"]))
                    self.assertTrue(all(value is None or isinstance(value, (str, int, float, bool)) for value in row))
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            path = directory / "pack.json"
            path.write_text(json.dumps(pack))
            media = directory / "empty-media"
            media.mkdir()
            store = ReviewStore(path, directory / "state", [media])
            self.assertEqual(store.cases, {"fingerprint-core", "morphology-core"})
            self.assertEqual(store.media, {})

    def test_cli_creates_new_output_and_refuses_overwrite_or_symlink(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            path = Path(directory) / "pack.json"
            self.assertEqual(main(["--output", str(path)]), 0)
            before = path.read_bytes()
            self.assertEqual(len(json.loads(before)["cases"]), 2)
            self.assertEqual(main(["--output", str(path)]), 1)
            self.assertEqual(path.read_bytes(), before)
            link = Path(directory) / "link.json"
            link.symlink_to(path)
            self.assertEqual(main(["--output", str(link)]), 1)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
