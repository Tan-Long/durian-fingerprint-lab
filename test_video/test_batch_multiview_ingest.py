#!/usr/bin/env python3

import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from batch_multiview_ingest import StatusLedger, detect_flash_frame, detect_revolution_window, estimate_revolution_period, select_angle_frames, write_results_summary


class StatusLedgerTest(unittest.TestCase):
    def test_updates_one_session_without_losing_the_queue(self):
        rows = [
            {"order": "001", "recorded_sample_id": "A", "session_id": "session-a"},
            {"order": "002", "recorded_sample_id": "B", "session_id": "session-b"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            ledger = StatusLedger(Path(directory) / "PROCESSING_STATUS.csv", rows)
            ledger.update("session-a", stage="SYNCING", progress_pct=20, message="flash")

            with ledger.path.open(encoding="utf-8-sig") as source:
                saved = list(csv.DictReader(source))

        self.assertEqual([row["session_id"] for row in saved], ["session-a", "session-b"])
        self.assertEqual(saved[0]["stage"], "SYNCING")
        self.assertEqual(saved[0]["progress_pct"], "20")
        self.assertEqual(saved[1]["stage"], "QUEUED")
        self.assertTrue(saved[0]["updated_at"])

    def test_writes_search_ready_results_from_manifests(self):
        rows = [
            {"order": "001", "recorded_sample_id": "A", "session_id": "session-a", "stage": "READY"},
            {"order": "002", "recorded_sample_id": "B", "session_id": "session-b", "stage": "FAILED"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            target = output / "samples/A/session-a"
            target.mkdir(parents=True)
            (target / "manifest.json").write_text(json.dumps({
                "revolution_period_sec": 20.0,
                "quality_gate": {
                    "minimum_source_features": 900,
                    "maximum_pair_angle_error_deg": 0.4,
                    "minimum_camera_median_loop_non_dark_inliers": 100,
                },
                "banks": {"CAM_TREN": {"bytes": 10}, "CAM_DUOI": {"bytes": 20}},
            }))

            path = write_results_summary(output, rows)
            with path.open(encoding="utf-8-sig") as source:
                saved = list(csv.DictReader(source))

        self.assertEqual(saved[0]["ready_for_search"], "YES")
        self.assertEqual(saved[0]["bank_bytes"], "30")
        self.assertEqual(saved[1]["ready_for_search"], "NO")


class AnglePairingTest(unittest.TestCase):
    def test_uses_flash_relative_time_and_camera_azimuth(self):
        top = select_angle_frames(
            np.arange(100.0, 105.1, 0.1),
            flash_timestamp=100.0,
            revolution_start_sec=1.0,
            revolution_duration_sec=4.0,
            camera_offset_deg=0.0,
            views=4,
        )
        bottom = select_angle_frames(
            np.arange(250.0, 255.1, 0.1),
            flash_timestamp=250.0,
            revolution_start_sec=1.0,
            revolution_duration_sec=4.0,
            camera_offset_deg=90.0,
            views=4,
        )

        self.assertEqual([item["frame_index"] for item in top], [10, 20, 30, 40])
        self.assertEqual([item["frame_index"] for item in bottom], [40, 10, 20, 30])
        self.assertTrue(all(item["angle_error_deg"] < 0.01 for item in top + bottom))


class RevolutionDetectionTest(unittest.TestCase):
    def test_ignores_flash_spike_and_splits_two_continuous_turns(self):
        times = np.arange(0.0, 50.0, 0.2)
        motion = np.full(len(times), 0.2)
        motion[(times >= 5.0) & (times < 45.0)] = 10.0
        motion[(times >= 20.0) & (times < 20.4)] = 0.2
        motion[np.argmin(abs(times - 1.0))] = 50.0

        result = detect_revolution_window(times, motion, flash_timestamp=100.0, rotations=2)

        self.assertAlmostEqual(result["start_timestamp"], 105.0, delta=0.21)
        self.assertAlmostEqual(result["revolution_duration_sec"], 20.0, delta=0.21)


class FlashDetectionTest(unittest.TestCase):
    def test_uses_the_sharp_light_off_edge(self):
        timestamps = np.arange(100.0, 108.0, 0.1)
        luminance = np.full(len(timestamps), 170.0)
        luminance[30:40] = 130.0
        luminance[40:] = 175.0

        result = detect_flash_frame(timestamps, luminance, search_seconds=6.0)

        self.assertEqual(result["frame_index"], 30)
        self.assertAlmostEqual(result["timestamp"], 103.0)

    def test_falls_back_to_flash_on_and_ignores_camera_startup(self):
        timestamps = np.arange(100.0, 104.0, 0.1)
        luminance = np.full(len(timestamps), 150.0)
        luminance[1] = 110.0
        luminance[10:] = 180.0
        luminance[11:] = 178.0
        luminance[12:] = 176.0

        result = detect_flash_frame(timestamps, luminance, search_seconds=3.0)

        self.assertEqual(result["frame_index"], 10)
        self.assertEqual(result["edge_direction"], "on")


class RevolutionPeriodTest(unittest.TestCase):
    def test_finds_texture_repeat_period(self):
        rng = np.random.default_rng(3)
        pattern = rng.normal(size=(20, 8, 8)).astype(np.float32)
        frames = np.concatenate([pattern, pattern, pattern])
        timestamps = np.arange(len(frames)) * 0.1

        period = estimate_revolution_period(
            frames, timestamps, start_timestamp=0.0, end_timestamp=6.0,
            minimum_sec=1.5, maximum_sec=2.5,
        )

        self.assertAlmostEqual(period, 2.0, delta=0.01)


if __name__ == "__main__":
    unittest.main()
