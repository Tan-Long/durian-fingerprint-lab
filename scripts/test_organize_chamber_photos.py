import json
from pathlib import Path
import tempfile
import unittest

from scripts.organize_chamber_photos import copy_reviewed, digest, prepare


class ChamberOrganizationTests(unittest.TestCase):
    def test_verified_copies_preserve_all_sources_and_reject_unsafe_or_incomplete_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            camera = source / 'camera'
            camera.mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, 'outside'):
                prepare(source, source / 'review')
            files, reviews = [], {}
            for name, code, status in [('a.jpg', 'N1V4C1_BONUS', 'visual_read'),
                                       ('b.jpg', None, 'unclear'), ('c.jpg', None, 'not_labelled')]:
                path = camera / name
                path.write_bytes(name.encode())
                relative = 'camera/' + name
                files.append({'relative_path': relative, 'sha256': digest(path)})
                reviews[relative] = {'fruit_id': code, 'status': status, 'locule': None, 'note': 'Test visual evidence'}
            inventory = {'source': str(source), 'files': files}
            destination = root / 'organized'
            with self.assertRaisesRegex(ValueError, 'every original'):
                copy_reviewed(inventory, {}, destination)
            with self.assertRaisesRegex(ValueError, 'outside'):
                copy_reviewed(inventory, reviews, source / 'nested')
            with self.assertRaisesRegex(ValueError, 'every original'):
                copy_reviewed({'source': str(source), 'files': files + [files[0]]}, reviews, destination)
            reviews['camera/a.jpg']['fruit_id'] = '../escape'
            with self.assertRaisesRegex(ValueError, 'complete fruit code'):
                copy_reviewed(inventory, reviews, destination)
            reviews['camera/a.jpg']['fruit_id'] = 'N1V4C1_BONUS'
            copy_reviewed(inventory, reviews, destination)
            rows = json.loads((destination / 'DOI_CHIEU_ANH.json').read_text())
            self.assertEqual(len(rows), 3)
            self.assertEqual({Path(r['destination']).parent.parent.name for r in rows},
                             {'N1V4C1_BONUS', '_CHUA_RO_NHAN', '_KHONG_CO_NHAN_QUA'})
            for record in rows:
                self.assertEqual(digest(Path(record['destination'])), record['sha256'])
                self.assertEqual(digest(source / record['relative_path']), record['sha256'])
                self.assertFalse(record['user_approved'])
            with self.assertRaisesRegex(ValueError, 'new destination'):
                copy_reviewed(inventory, reviews, destination)
            (camera / 'a.jpg').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'Source content changed'):
                copy_reviewed(inventory, reviews, root / 'second')
            self.assertFalse((root / 'second').exists())


if __name__ == '__main__':
    unittest.main()
