#!/usr/bin/env python3

import csv
import tempfile
import unittest
from pathlib import Path

from build_groundtruth_viewer import build_viewer


class GroundtruthViewerTest(unittest.TestCase):
    def test_builds_an_offline_viewer_with_relative_contact_sheets(self):
        fields = [
            "order", "recorded_sample_id", "session_id", "status",
            "ready_for_search", "views_per_camera", "period_sec",
            "minimum_source_features", "maximum_angle_error_deg",
            "minimum_loop_inliers", "bank_bytes", "result_directory", "note",
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (root / "PROCESSING_RESULTS.csv").open("w", newline="", encoding="utf-8-sig") as output:
                writer = csv.DictWriter(output, fieldnames=fields)
                writer.writeheader()
                writer.writerow({
                    "order": "001", "recorded_sample_id": "N1V11C3",
                    "session_id": "session-a", "status": "READY",
                    "ready_for_search": "YES", "views_per_camera": "36",
                    "period_sec": "20.001", "minimum_source_features": "1400",
                    "maximum_angle_error_deg": "0.59", "minimum_loop_inliers": "190",
                    "bank_bytes": "1900000", "result_directory": "ignored",
                    "note": "good",
                })

            viewer = build_viewer(root)
            html = viewer.read_text(encoding="utf-8")

        self.assertEqual(viewer.name, "groundtruth_viewer.html")
        self.assertIn("N1V11C3", html)
        self.assertIn("samples/N1V11C3/session-a/contact-sheet.jpg", html)
        self.assertIn('"status": "READY"', html)


if __name__ == "__main__":
    unittest.main()
