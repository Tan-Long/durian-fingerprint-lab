import csv
from pathlib import Path
import tempfile
import unittest

from build_dataset_index import build_index, MEDIA_FIELDS, SAMPLE_FIELDS


class DatasetIndexTest(unittest.TestCase):
    def test_indexes_media_preserves_review_and_leaves_sources_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            collection = root / "collection"
            manifests = collection / "manifests"
            manifests.mkdir(parents=True)
            samples = manifests / "samples.csv"
            files = manifests / "files.csv"
            with samples.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=SAMPLE_FIELDS)
                writer.writeheader()
                writer.writerow(dict(collection_id="c", sample_id="A", sample_uid="c/A", status="UNREVIEWED"))
            video = collection / "A/CAM_TREN/rgb.mp4"
            video.parent.mkdir(parents=True)
            video.touch()
            with files.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=MEDIA_FIELDS + ["action"])
                writer.writeheader()
                for modality, sample, path in [
                    ("rig", "A", video),
                    ("rig", "A", video.with_name("depth.png")),
                    ("random_photo", "A", collection / "query.HEIC"),
                    ("chamber_photo", "unknown", collection / "locule.JPG"),
                ]:
                    writer.writerow(dict(action="COPY", collection_id="c", sample_id=sample,
                                         modality=modality, destination_path=str(path), dataset_eligible="REVIEW"))
            original = (samples.read_bytes(), files.read_bytes())
            output = root / "output"
            result = build_index(collection, output)
            self.assertEqual(result["media_records"], 3)
            self.assertEqual(result["missing_media_files"], 2)
            self.assertEqual(result["unresolved_media_sample_links"], 1)
            with (output / "media.csv").open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["camera"], "CAM_TREN")
            self.assertEqual(rows[0]["sample_link_status"], "RECORDED_UNVERIFIED")
            self.assertEqual(rows[0]["manifest_row"], "2")
            self.assertTrue(all(row["dataset_eligible"] == "REVIEW" for row in rows))
            self.assertEqual((samples.read_bytes(), files.read_bytes()), original)

    def test_rejects_output_inside_source_collection(self):
        with tempfile.TemporaryDirectory() as directory:
            collection = Path(directory)
            with self.assertRaisesRegex(ValueError, "outside the read-only collection"):
                build_index(collection, collection / "output")


if __name__ == "__main__":
    unittest.main()
