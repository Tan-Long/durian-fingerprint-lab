import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.assemble_sample_demo import assemble


class SampleDemoTest(unittest.TestCase):
    def test_reference_labels_stay_separate_and_mismatched_query_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference = root / "reference.bin"
            reference.write_bytes(b"isolated test bytes")
            source = {"path": str(reference), "sha256": hashlib.sha256(reference.read_bytes()).hexdigest()}
            common = {"fixture_only": False, "query": {"sha256": "test-query"}, "git_snapshot": "test"}
            alignment = {"sources": common, "cases": [{"id": "align", "findings": [], "raw_result": {"mode": "known_sample_alignment", "best_per_camera": [{"geometric_inliers": 0}]}}]}
            retrieval = {"sources": common, "cases": [{"id": "retrieval", "track": "fingerprint", "findings": [],
                         "raw_result": {"fruit_ranking": [{"sample_id": "WRONG"}]}}]}
            evidence = {"sample_id": "EXPECTED", "query": {"sha256": "test-query"},
                        "label_evidence": [source], "chamber_photos": [], "workbook": source,
                        "targets": {"locule_count": {"value": 5, "sheet": "Fruit-list", "cell": "Q70"}}}
            paths = [root / name for name in ("alignment.json", "retrieval.json", "evidence.json")]
            for path, value in zip(paths, (alignment, retrieval, evidence)):
                path.write_text(json.dumps(value))
            result = assemble(*paths)
            self.assertEqual(len(result["cases"]), 3)
            self.assertIn("CHƯA KHỚP", result["cases"][0]["findings"][0])
            morphology = result["cases"][1]
            self.assertIsNone(morphology["raw_result"]["predictions"])
            self.assertEqual(morphology["raw_result"]["reference_evidence"]["targets"]["locule_count"]["value"], 5)
            self.assertIn("Không có mã mẫu", result["cases"][2]["findings"][1])
            self.assertEqual(json.loads(paths[1].read_text()), retrieval)
            evidence["query"]["sha256"] = "other-query"
            paths[2].write_text(json.dumps(evidence))
            with self.assertRaisesRegex(ValueError, "same real independent query"):
                assemble(*paths)


if __name__ == "__main__":
    unittest.main()
