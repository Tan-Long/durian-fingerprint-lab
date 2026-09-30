import base64
from contextlib import contextmanager
import hashlib
import http.client
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import unittest

from serve_label_review import ReviewError, ReviewServer, ReviewStore


@contextmanager
def running(store, html):
    server = ReviewServer(store, html, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def request(server, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    content = json.dumps(body).encode() if body is not None else None
    connection.request(method, path, body=content, headers=headers or {})
    response = connection.getresponse()
    raw = response.read()
    result = json.loads(raw) if response.getheader("Content-Type", "").startswith("application/json") else raw
    status = response.status
    connection.close()
    return status, result


class LabelReviewTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.media = self.root / "source"
        self.media.mkdir()
        self.image = self.media / "image.png"
        self.image.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="))
        self.pack = self.root / "pack.json"
        self.content = {"schema_version": 1, "sources": {}, "cases": [{
            "id": "fruit-1", "title": "Confirm fruit", "track": "fingerprint", "priority": "high",
            "sample_ids": ["A", "B"], "findings": [], "questions": [], "facts": [],
            "media": [{"id": "photo-1", "label": "Photo", "kind": "photo", "source_path": str(self.image),
                       "sha256": hashlib.sha256(self.image.read_bytes()).hexdigest(), "link_status": "UNVERIFIED"}],
        }]}
        self.pack.write_text(json.dumps(self.content))
        self.state = self.root / "state"
        self.html = self.root / "index.html"
        self.html.write_text("<!doctype html><title>Review</title>")

    def store(self):
        return ReviewStore(self.pack, self.state, [self.media])

    def test_save_restart_comment_revision_and_pack_scoping(self):
        before = self.image.read_bytes(), self.pack.read_bytes()
        store = self.store()
        with running(store, self.html) as server:
            status, snapshot = request(server, "GET", "/api/review")
            self.assertEqual(status, 200)
            headers = {"Content-Type": "application/json", "X-Review-Token": snapshot["csrf_token"],
                       "Origin": f"http://127.0.0.1:{server.server_port}"}
            body = {"pack_id": snapshot["pack_id"], "case_id": "fruit-1", "decision": "approved",
                    "comment": "Confirmed A using the original label", "expected_revision": 0}
            status, saved = request(server, "POST", "/api/review", body, headers)
            self.assertEqual(status, 200)
            self.assertEqual(saved["current"]["revision"], 1)
            self.assertEqual(request(server, "POST", "/api/review", body, headers)[0], 409)
            body.update(decision="comment", comment="Label appears on frame 12", expected_revision=1)
            status, saved = request(server, "POST", "/api/review", body, headers)
            self.assertEqual(status, 200)
            self.assertEqual(saved["event"]["decision"], "comment")
            self.assertEqual(saved["current"]["decision"], "approved")
            self.assertEqual(saved["current"]["revision"], 2)
        restarted = self.store()
        with running(restarted, self.html) as server:
            status, export = request(server, "GET", "/api/export")
            self.assertEqual((status, len(export["events"])), (200, 2))
            self.assertEqual(restarted.snapshot()["current"]["fruit-1"]["comment"], "Label appears on frame 12")
        with sqlite3.connect(restarted.db) as db:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                db.execute("DELETE FROM events")
        self.assertEqual((self.image.read_bytes(), self.pack.read_bytes()), before)
        self.content["cases"][0]["title"] = "Updated question"
        self.pack.write_text(json.dumps(self.content))
        changed = self.store()
        self.assertEqual(changed.snapshot()["history"], [])
        with self.assertRaisesRegex(ReviewError, "changed"):
            changed.save(body)

    def test_rejects_unknown_ids_traversal_cross_origin_and_bad_writes(self):
        store = self.store()
        with running(store, self.html) as server:
            for path in ("/media/../pack.json", "/media/%2e%2e%2fpack.json", "/media/unknown", "/pack.json", "/media/photo-1?path=/etc/passwd"):
                self.assertEqual(request(server, "GET", path)[0], 404)
            self.assertEqual(request(server, "GET", "/api/review", headers={"Host": "evil.example"})[0], 403)
            body = {"pack_id": store.pack_id, "case_id": "fruit-1", "decision": "approved", "comment": "A confirmed", "expected_revision": 0}
            headers = {"Content-Type": "application/json", "X-Review-Token": store.token}
            self.assertEqual(request(server, "POST", "/api/review", body)[0], 403)
            self.assertEqual(request(server, "POST", "/api/review", body, {**headers, "Origin": "https://evil.example"})[0], 403)
            for bad in ({**body, "case_id": "unknown"}, {**body, "comment": " "}, {**body, "comment": "!"},
                        {**body, "unexpected": 1}, {**body, "expected_revision": True}, {**body, "comment": "x" * 4001}):
                self.assertEqual(request(server, "POST", "/api/review", bad, headers)[0], 400)
            self.assertEqual(request(server, "POST", "/api/review", {**body, "pack_id": "old"}, headers)[0], 409)
        self.assertEqual(store.snapshot()["history"], [])

    def test_source_roots_symlinks_and_changed_media_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            ReviewStore(self.pack, self.media / "state", [self.media])
        outside = self.root / "outside.png"
        outside.write_bytes(self.image.read_bytes())
        link = self.media / "link.png"
        link.symlink_to(outside)
        self.content["cases"][0]["media"][0]["source_path"] = str(link)
        self.pack.write_text(json.dumps(self.content))
        with self.assertRaisesRegex(ValueError, "inside"):
            self.store()
        link.unlink()
        link.symlink_to(self.image)
        store = self.store()
        link.unlink()
        link.symlink_to(outside)
        with self.assertRaisesRegex(ReviewError, "changed"):
            store.thumbnail("photo-1")
        store.cache.rmdir()
        store.cache.symlink_to(self.media, target_is_directory=True)
        with self.assertRaisesRegex(ReviewError, "state path changed"):
            store.thumbnail("photo-1")
        store.cache.unlink()
        store.cache.mkdir()
        store.db.unlink()
        store.db.symlink_to(self.image)
        with self.assertRaisesRegex(ReviewError, "state path changed"):
            store.snapshot()

    @unittest.skipUnless(shutil.which("magick"), "ImageMagick required for thumbnails")
    def test_serves_jpeg_thumbnail_and_rejects_changed_hash(self):
        # Phone-sized decoding must exercise ImageMagick's pixel-cache limits.
        self.image.write_bytes(subprocess.check_output(["magick", "-size", "4000x3000", "gradient:green-yellow", "png:-"]))
        self.content["cases"][0]["media"][0]["sha256"] = hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.pack.write_text(json.dumps(self.content))
        store = self.store()
        with running(store, self.html) as server:
            status, thumbnail = request(server, "GET", "/media/photo-1")
            self.assertEqual(status, 200)
            self.assertTrue(thumbnail.startswith(b"\xff\xd8"))
            dimensions = subprocess.check_output(["magick", "identify", "-format", "%w %h", "jpeg:-"], input=thumbnail)
            self.assertLessEqual(max(map(int, dimensions.split())), 1600)
            self.assertEqual(request(server, "GET", "/media/photo-1")[1], thumbnail)
            self.image.write_bytes(self.image.read_bytes() + b"changed")
            self.assertEqual(request(server, "GET", "/media/photo-1")[0], 409)


if __name__ == "__main__":
    unittest.main()
