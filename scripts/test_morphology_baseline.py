"""Synthetic-only proof: python3 -B -m unittest scripts.test_morphology_baseline -v"""

import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.morphology_baseline import run


def fixture():
    targets = ["locule_count", "aril_count", "shell_thickness_mm"]
    values = [(2, 0, 10), (4, 8, 14), (6, 2, 11), (2, 10, 15)]
    return {
        "schema_version": 1,
        "feature_definitions": {"synthetic_weight_g": {
            "timing": "before_opening", "attested_by": "synthetic-test",
            "evidence": "synthetic fixture; not a real timing or label approval"}},
        "targets": targets,
        "fruits": [{"fruit_id": f"synthetic-F{index + 1}",
                    "split": "train" if index < 2 else "test",
                    "features": {"synthetic_weight_g": 1000 + index},
                    "targets": {target: {"value": value, "review_status": "approved",
                                         "reviewed_by": "synthetic-test", "evidence": "synthetic-only"}
                                for target, value in zip(targets, labels)}}
                   for index, labels in enumerate(values)],
    }


class MorphologyBaselineTests(unittest.TestCase):
    def test_train_predict_target_specific_metrics(self):
        result = run(fixture())
        self.assertEqual(result["status"], "evaluated")
        self.assertEqual(result["user_acceptance"], "pending")
        self.assertEqual(result["features_used"], [])
        self.assertIn("UNUSED", result["limits"])
        for target, constant, mae, rmse, bias in [
            ("locule_count", 3, 2, math.sqrt(5), -1),
            ("aril_count", 4, 4, math.sqrt(20), -2),
            ("shell_thickness_mm", 12, 2, math.sqrt(5), -1),
        ]:
            actual = result["targets"][target]
            self.assertEqual(actual["model"]["constant"], constant)
            self.assertEqual(actual["model"]["train_count"], 2)
            self.assertEqual([p["fruit_id"] for p in actual["predictions"]], ["synthetic-F3", "synthetic-F4"])
            self.assertEqual(actual["metrics"]["n"], 2)
            for metric, expected in [("mae", mae), ("rmse", rmse), ("bias", bias)]:
                self.assertAlmostEqual(actual["metrics"][metric], expected)

    def test_test_labels_and_features_cannot_change_trained_constant(self):
        data = fixture()
        before = run(data)
        data["fruits"][2]["targets"]["locule_count"]["value"] = 100
        for row in data["fruits"]:
            row["features"]["synthetic_weight_g"] = 999999
        after = run(data)
        self.assertEqual(before["targets"]["locule_count"]["model"], after["targets"]["locule_count"]["model"])
        self.assertEqual(before["targets"]["locule_count"]["predictions"], after["targets"]["locule_count"]["predictions"])
        self.assertNotEqual(before["targets"]["locule_count"]["metrics"], after["targets"]["locule_count"]["metrics"])

    def test_fractional_median_is_not_rounded(self):
        data = fixture()
        data["fruits"][1]["targets"]["locule_count"]["value"] = 3
        self.assertEqual(run(data)["targets"]["locule_count"]["model"]["constant"], 2.5)

    def test_duplicate_and_cross_split_fruits_rejected(self):
        for index in (1, 2):
            data = fixture()
            data["fruits"][index]["fruit_id"] = data["fruits"][0]["fruit_id"]
            with self.assertRaisesRegex(ValueError, "duplicate fruit or train/test overlap"):
                run(data)

    def test_split_and_schema_gates(self):
        for split in (None, "validation", "", {}):
            data = fixture()
            data["fruits"][0]["split"] = split
            with self.assertRaisesRegex(ValueError, "explicit train/test assignment"):
                run(data)
        data = fixture()
        for row in data["fruits"]:
            row["split"] = "train"
        with self.assertRaisesRegex(ValueError, "nonempty train and test"):
            run(data)
        data = fixture()
        data["targets"].append("locule_count")
        with self.assertRaisesRegex(ValueError, "unique targets"):
            run(data)

    def test_no_after_opening_or_unattested_features(self):
        for timing in ("after_opening", "unknown", None):
            data = fixture()
            data["feature_definitions"]["synthetic_weight_g"]["timing"] = timing
            with self.assertRaisesRegex(ValueError, "only before_opening inputs allowed"):
                run(data)
        for key in ("attested_by", "evidence"):
            data = fixture()
            del data["feature_definitions"]["synthetic_weight_g"][key]
            with self.assertRaisesRegex(ValueError, "timing attestation missing"):
                run(data)

    def test_feature_missing_nonfinite_bool_and_undeclared_rejected(self):
        for value in (None, True, "12", float("nan"), float("inf")):
            data = fixture()
            data["fruits"][0]["features"]["synthetic_weight_g"] = value
            with self.assertRaisesRegex(ValueError, "finite numeric feature required"):
                run(data)
        for features in ({}, {"post_opening_arils": 4}):
            data = fixture()
            data["fruits"][0]["features"] = features
            with self.assertRaisesRegex(ValueError, "match declarations exactly"):
                run(data)

    def test_target_failure_blocks_target_not_shell_or_rows(self):
        for value in (None, True, "4", float("nan"), float("inf"), -1, 0, 2.5):
            data = fixture()
            data["fruits"][0]["targets"]["locule_count"]["value"] = value
            result = run(data)
            self.assertEqual(result["status"], "partial_block")
            self.assertEqual(result["targets"]["locule_count"]["status"], "blocked")
            shell = result["targets"]["shell_thickness_mm"]
            self.assertEqual(shell["model"]["train_count"], 2)
            self.assertEqual(shell["metrics"]["n"], 2)
        data = fixture()
        del data["fruits"][2]["targets"]["locule_count"]
        blocked = run(data)["targets"]["locule_count"]
        self.assertEqual(blocked["problems"][0]["fruit_id"], "synthetic-F3")
        self.assertIn("missing label", blocked["problems"][0]["reasons"])

    def test_zero_arils_valid_but_zero_shell_rejected(self):
        data = fixture()
        data["fruits"][0]["targets"]["shell_thickness_mm"]["value"] = 0
        result = run(data)
        self.assertEqual(result["targets"]["aril_count"]["status"], "evaluated")
        self.assertEqual(result["targets"]["shell_thickness_mm"]["status"], "blocked")

    def test_audit_valid_not_approval_and_review_evidence_required(self):
        for changes in ({"review_status": "valid"}, {"review_status": False},
                        {"reviewed_by": ""}, {"evidence": None}):
            data = fixture()
            data["fruits"][1]["targets"]["aril_count"].update(changes)
            result = run(data)
            self.assertEqual(result["targets"]["aril_count"]["status"], "blocked")
            self.assertEqual(result["targets"]["shell_thickness_mm"]["status"], "evaluated")

    def test_cli_pipeline_partial_exit_hash_and_no_source_overwrite(self):
        script = Path(__file__).with_name("morphology_baseline.py")
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "synthetic.json", Path(directory) / "result.json"
            data = fixture()
            source.write_text(json.dumps(data), encoding="utf-8")
            before = source.read_bytes()
            command = [sys.executable, "-B", str(script), str(source), "--output", str(output)]
            process = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads(output.read_text())
            self.assertEqual(result["source"]["sha256"], hashlib.sha256(before).hexdigest())
            self.assertEqual(result["targets"]["shell_thickness_mm"]["metrics"]["mae"], 2)
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
            command[-1] = str(source)
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
            self.assertEqual(source.read_bytes(), before)
            symlink = Path(directory) / "linked-result.json"
            symlink.symlink_to(source)
            command[-1] = str(symlink)
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
            self.assertEqual(source.read_bytes(), before)
            data["fruits"][2]["targets"]["locule_count"]["review_status"] = "unreviewed"
            source.write_text(json.dumps(data), encoding="utf-8")
            command[-1] = str(Path(directory) / "partial.json")
            process = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(process.returncode, 2, process.stderr)
            partial = json.loads(Path(command[-1]).read_text())
            self.assertEqual(partial["targets"]["shell_thickness_mm"]["status"], "evaluated")
            self.assertEqual(partial["targets"]["locule_count"]["status"], "blocked")

    def test_cli_overlap_and_post_opening_reject_without_artifact(self):
        script = Path(__file__).with_name("morphology_baseline.py")
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "synthetic.json", Path(directory) / "result.json"
            for violation in ("overlap", "after_opening"):
                data = fixture()
                if violation == "overlap":
                    data["fruits"][2]["fruit_id"] = data["fruits"][0]["fruit_id"]
                    diagnostic = "duplicate fruit or train/test overlap"
                else:
                    data["feature_definitions"]["synthetic_weight_g"]["timing"] = "after_opening"
                    diagnostic = "only before_opening inputs allowed"
                source.write_text(json.dumps(data), encoding="utf-8")
                before = source.read_bytes()
                process = subprocess.run([sys.executable, "-B", str(script), str(source),
                                          "--output", str(output)], capture_output=True, text=True)
                self.assertEqual(process.returncode, 1)
                self.assertIn(diagnostic, process.stderr)
                self.assertFalse(output.exists())
                self.assertEqual(source.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
