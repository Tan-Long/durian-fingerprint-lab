import unittest

import numpy as np
from scipy import ndimage

from prototypes.durian_2d_projection.spike_graph import extract_spikes
from prototypes.durian_2d_projection.heightmap import HEIGHT, WIDTH, atlas_points, select_reliable_surface
from prototypes.durian_2d_projection.frame_spikes import detect_spikes_2d
from prototypes.durian_2d_projection.image_pattern_map import rectify_front
from prototypes.durian_2d_projection.center_strip_map import cylindrical_band_atlas, minimum_cost_seam
from prototypes.durian_2d_projection.video_spike_pattern import (
    connect_grooves,
    merge_observations,
    phases_from_shifts,
    project_binary,
    render_pattern,
    skeletonize,
)


class SpikeGraphTest(unittest.TestCase):
    def test_dynamic_seam_follows_low_cost_path(self):
        cost = np.full((8, 8), 100.0)
        expected = np.arange(8)
        cost[np.arange(8), expected] = 0

        seam = minimum_cost_seam(cost)

        np.testing.assert_array_equal(seam, expected)

    def test_blended_atlas_averages_overlapping_frames(self):
        frames = np.stack(
            [
                np.full((60, 100, 3), 100, dtype=np.uint8),
                np.full((60, 100, 3), 200, dtype=np.uint8),
            ]
        )
        yy, xx = np.ogrid[:60, :100]
        mask = ((xx - 50) / 42) ** 2 + ((yy - 30) / 27) ** 2 <= 1

        result, valid = cylindrical_band_atlas(
            frames, [mask, mask], max_view_degrees=24, phases=np.zeros(2), blend=True
        )

        self.assertAlmostEqual(float(result[valid].mean()), 150, delta=1)

    def test_consensus_band_reduces_to_a_connected_centerline(self):
        band = np.zeros((20, 30), dtype=bool)
        band[7:13, 4:26] = True

        centerline = skeletonize(band)

        _, components = ndimage.label(centerline, np.ones((3, 3)))
        self.assertEqual(components, 1)
        self.assertLess(centerline.sum(), band.sum() / 2)

    def test_binary_edge_projects_to_registered_phase(self):
        edges = np.zeros((20, 30), dtype=bool)
        edges[10, 15] = True

        projected = project_binary(
            edges,
            phase=np.pi,
            axis_y=10,
            x0=10,
            radius=np.full(10, 8.0),
            map_width=100,
            max_view=np.deg2rad(12),
        )

        self.assertTrue(projected[5, 50])

    def test_registration_replaces_opposite_direction_outlier(self):
        phases, rejected = phases_from_shifts(
            np.array([20.0, 22.0, -100.0, 21.0]), 100, 30
        )

        self.assertEqual(rejected, [2])
        self.assertTrue(np.all(np.diff(phases) > 0))

    def test_video_map_connects_a_one_pixel_gap_between_grooves(self):
        grooves = np.zeros((9, 12), dtype=bool)
        grooves[4, 2:5] = True
        grooves[4, 6:9] = True

        rendered = render_pattern([], connect_grooves(grooves))

        self.assertTrue(rendered[4, 5].any())

    def test_video_observations_merge_across_map_seam_and_keep_best(self):
        candidates = [
            {"tip": [40, 2], "frame": 0, "quality": 0.5, "base_boundary": []},
            {"tip": [42, 718], "frame": 1, "quality": 0.9, "base_boundary": []},
            {"tip": [80, 100], "frame": 1, "quality": 0.8, "base_boundary": []},
        ]

        merged = merge_observations(candidates, 720)

        self.assertEqual(len(merged), 2)
        winner = next(item for item in merged if item["support_frames"] == 2)
        self.assertEqual(winner["tip"], [42, 718])

    def test_front_band_atlas_keeps_a_two_dimensional_patch(self):
        frames = np.zeros((8, 60, 100, 3), dtype=np.uint8)
        masks = []
        yy, xx = np.ogrid[:60, :100]
        mask = ((xx - 50) / 42) ** 2 + ((yy - 30) / 27) ** 2 <= 1
        for index, frame in enumerate(frames, 1):
            frame[25:36, 35:66] = index * 25
            masks.append(mask)

        result, valid = cylindrical_band_atlas(frames, masks, max_view_degrees=24)

        self.assertGreater(result.shape[0], 40)
        self.assertGreater(valid.mean(), 0.7)

    def test_image_rectification_keeps_front_pattern_order(self):
        image = np.zeros((100, 120, 3), dtype=np.uint8)
        yy, xx = np.ogrid[:100, :120]
        mask = ((xx - 60) / 50) ** 2 + ((yy - 50) / 45) ** 2 <= 1
        image[:, 60] = 255

        pattern, valid = rectify_front(image, mask, size=101)

        self.assertGreater(pattern[:, 50, 0].mean(), pattern[:, 30, 0].mean() + 100)
        self.assertGreater(valid.mean(), 0.9)

    def test_rgb_grooves_define_four_spike_feet(self):
        image = np.full((120, 120, 3), (95, 145, 55), dtype=np.uint8)
        mask = np.zeros((120, 120), dtype=bool)
        mask[10:110, 10:110] = True
        image[9:12, 10:110] = image[58:62, 10:110] = image[108:111, 10:110] = (70, 38, 25)
        image[10:110, 9:12] = image[10:110, 58:62] = image[10:110, 108:111] = (70, 38, 25)

        detections = detect_spikes_2d(image, mask, min_spacing=20)

        self.assertEqual(len(detections), 4)
        expected = [(35, 35), (35, 85), (85, 35), (85, 85)]
        for row, column in expected:
            self.assertLess(
                min(np.hypot(item["tip"][0] - row, item["tip"][1] - column) for item in detections),
                5,
            )
        self.assertTrue(all(len(item["base_boundary"]) >= 20 for item in detections))

    def test_rgb_detector_uses_visible_apex_instead_of_cell_center(self):
        image = np.full((120, 120, 3), (95, 145, 55), dtype=np.uint8)
        mask = np.zeros((120, 120), dtype=bool)
        mask[10:110, 10:110] = True
        image[9:12, 10:110] = image[58:62, 10:110] = image[108:111, 10:110] = (70, 38, 25)
        image[10:110, 9:12] = image[10:110, 58:62] = image[10:110, 108:111] = (70, 38, 25)
        expected = [(29, 41), (29, 91), (79, 41), (79, 91)]
        for row, column in expected:
            image[row - 2 : row + 3, column - 2 : column + 3] = (82, 45, 18)

        detections = detect_spikes_2d(image, mask, min_spacing=20)

        for row, column in expected:
            self.assertLess(
                min(np.hypot(item["tip"][0] - row, item["tip"][1] - column) for item in detections),
                4,
            )

    def test_canonical_tip_projects_back_to_its_mesh_longitude(self):
        angles = np.linspace(0, 2 * np.pi, 32, endpoint=False)
        points = np.array(
            [[np.cos(angle), y, np.sin(angle)] for y in (0.0, 1.0) for angle in angles],
            dtype=np.float32,
        )

        projected = atlas_points(
            points,
            np.array([HEIGHT // 2, HEIGHT // 2]),
            np.array([0, WIDTH // 4]),
            np.array([0.2, 0.2]),
        )

        actual = np.mod(np.arctan2(projected[:, 2], projected[:, 0]), 2 * np.pi)
        np.testing.assert_allclose(actual, [0, np.pi / 2], atol=0.02)

    def test_full_surface_is_not_cut_down_by_partial_mesh_filter(self):
        surface = np.ones((40, 80), dtype=np.float32)
        surface[:2] = np.nan

        selected = select_reliable_surface(surface)

        self.assertEqual(np.isfinite(selected).sum(), np.isfinite(surface).sum())

    def test_extracts_tip_and_base_for_each_surface_spike(self):
        y, x = np.mgrid[:96, :192]
        surface = np.zeros((96, 192), dtype=np.float32)
        expected = [(25, 30), (55, 95), (35, 160)]
        for tip_y, tip_x in expected:
            surface += np.exp(-((y - tip_y) ** 2 + (x - tip_x) ** 2) / (2 * 7**2))

        graph = extract_spikes(surface, min_distance=18, min_prominence=0.2)

        self.assertEqual(len(graph["spikes"]), 3)
        actual = [(spike["tip"]["row"], spike["tip"]["column"]) for spike in graph["spikes"]]
        for expected_tip in expected:
            self.assertLess(min(np.hypot(y - expected_tip[0], x - expected_tip[1]) for y, x in actual), 2)
        self.assertTrue(all(spike["base"]["area_pixels"] > 100 for spike in graph["spikes"]))
        self.assertTrue(graph["edges"])


if __name__ == "__main__":
    unittest.main()
