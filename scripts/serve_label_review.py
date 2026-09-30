#!/usr/bin/env python3
"""Serve a local label-review pack; decisions are append-only and never edit labels.

python3 scripts/serve_label_review.py --pack output/review/pack.json \
  --state-dir output/review-state --media-root /Volumes/SoilTECH --port 8765

GET /api/review supplies csrf_token; send it as X-Review-Token on POST /api/review.
The server binds only 127.0.0.1. Restart with the same pack/state to retain history.
"""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import threading
from urllib.parse import urlsplit


RASTER_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".tif", ".tiff", ".bmp"}
ID = re.compile(r"[A-Za-z0-9_-]{1,160}\Z")
DECISIONS = {"approved", "needs_changes", "uncertain", "comment"}


class ReviewError(Exception):
    def __init__(self, status: int, message: str):
        self.status, self.message = status, message


class ReviewStore:
    def __init__(self, pack: Path, state: Path, media_roots: list[Path]):
        self.roots = [root.resolve(strict=True) for root in media_roots]
        if not self.roots or any(not root.is_dir() for root in self.roots):
            raise ValueError("At least one existing --media-root directory is required")
        self.state = state.resolve()
        self.pack_path = pack.resolve(strict=True)
        if any(self.state.is_relative_to(root) for root in self.roots):
            raise ValueError("State directory must be outside read-only media roots")
        raw = self.pack_path.read_bytes()
        self.pack_id = hashlib.sha256(raw).hexdigest()
        self.pack = json.loads(raw)
        if self.pack.get("schema_version") != 1 or not isinstance(self.pack.get("cases"), list):
            raise ValueError("Expected schema_version 1 and cases array")
        self.cases, self.media = set(), {}
        for case in self.pack["cases"]:
            case_id = case["id"]
            if not isinstance(case_id, str) or not ID.fullmatch(case_id) or case_id in self.cases:
                raise ValueError("Case IDs must be unique URL-safe identifiers")
            self.cases.add(case_id)
            for item in case.get("media", []):
                media_id = item["id"]
                if not isinstance(media_id, str) or not ID.fullmatch(media_id):
                    raise ValueError("Media IDs must be URL-safe identifiers")
                path = Path(item["source_path"])
                resolved = self.allowed_media(path)
                expected = item.get("sha256") or ""
                if expected and not re.fullmatch(r"[a-fA-F0-9]{64}", expected):
                    raise ValueError("Invalid media sha256")
                value = (path, resolved, expected.lower())
                if media_id in self.media and self.media[media_id] != value:
                    raise ValueError("Shared media ID must identify the same source and hash")
                self.media[media_id] = value
        self.state.mkdir(parents=True, exist_ok=True)
        self.db = self.state / "decisions.sqlite3"
        self.cache = self.state / "thumbnails"
        if self.db.is_symlink() or self.cache.is_symlink() or self.db == self.pack_path:
            raise ValueError("State files must not redirect or overwrite source files")
        self.cache.mkdir(exist_ok=True)
        with closing(self.connection()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id INTEGER PRIMARY KEY, pack_id TEXT NOT NULL,
                    case_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    decision TEXT NOT NULL, comment TEXT NOT NULL, created_at TEXT NOT NULL,
                    UNIQUE(pack_id, case_id, revision));
                CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
                    BEGIN SELECT RAISE(ABORT, 'review events are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
                    BEGIN SELECT RAISE(ABORT, 'review events are append-only'); END;
            """)
        self.token = secrets.token_urlsafe(32)
        self.conversions = threading.BoundedSemaphore(2)

    def allowed_media(self, path: Path) -> Path:
        resolved = path.resolve(strict=True)
        if (not path.is_absolute() or not resolved.is_file()
                or resolved.suffix.lower() not in RASTER_SUFFIXES
                or not any(resolved.is_relative_to(root) for root in self.roots)):
            raise ValueError("Media source must be an allowed raster file inside --media-root")
        return resolved

    def connection(self):
        self.check_state()
        db = sqlite3.connect(self.db, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    def check_state(self):
        if (self.state.resolve() != self.state or self.cache.resolve() != self.cache
                or any(Path(str(self.db) + suffix).is_symlink() for suffix in ("", "-journal", "-wal", "-shm"))):
            raise ReviewError(409, "Review state path changed; restart after restoring its directory")

    def events(self, db):
        return [dict(row) for row in db.execute("SELECT * FROM events WHERE pack_id=? ORDER BY event_id", (self.pack_id,))]

    @staticmethod
    def current(events):
        result = {}
        for event in events:
            previous = result.get(event["case_id"], {})
            decision = previous.get("decision") if event["decision"] == "comment" else event["decision"]
            result[event["case_id"]] = {**event, "decision": decision}
        return result

    def snapshot(self):
        with closing(self.connection()) as db:
            events = self.events(db)
        return {**self.pack, "pack_id": self.pack_id, "csrf_token": self.token,
                "current": self.current(events), "history": events}

    def save(self, body):
        fields = {"pack_id", "case_id", "decision", "comment", "expected_revision"}
        if not isinstance(body, dict) or set(body) != fields:
            raise ReviewError(400, "Expected exactly pack_id, case_id, decision, comment, expected_revision")
        if body["pack_id"] != self.pack_id:
            raise ReviewError(409, "Review pack changed; reload before saving")
        if not isinstance(body["case_id"], str) or body["case_id"] not in self.cases:
            raise ReviewError(400, "Unknown case_id")
        if not isinstance(body["decision"], str) or body["decision"] not in DECISIONS:
            raise ReviewError(400, "Unknown decision")
        comment = body["comment"]
        if not isinstance(comment, str) or not 1 <= len(comment.strip()) <= 4000 or not any(c.isalnum() for c in comment):
            raise ReviewError(400, "Provide a comment with the correct ID/value or supporting evidence (maximum 4000 characters)")
        revision = body["expected_revision"]
        if type(revision) is not int or revision < 0:
            raise ReviewError(400, "expected_revision must be a nonnegative integer")
        with closing(self.connection()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            current = self.current(self.events(db)).get(body["case_id"])
            if revision != (current["revision"] if current else 0):
                raise ReviewError(409, "Case changed; reload and review the latest comments")
            db.execute("INSERT INTO events(pack_id,case_id,revision,decision,comment,created_at) VALUES(?,?,?,?,?,?)",
                       (self.pack_id, body["case_id"], revision + 1, body["decision"], comment.strip(),
                        datetime.now(timezone.utc).isoformat(timespec="microseconds")))
            events = self.events(db)
            result = {"event": events[-1], "current": self.current(events)[body["case_id"]]}
        return result

    def thumbnail(self, media_id, full=False):
        self.check_state()
        if media_id not in self.media:
            raise ReviewError(404, "Unknown media ID")
        path, registered, expected = self.media[media_id]
        try:
            source = self.allowed_media(path)
            if source != registered:
                raise ValueError("Source path changed")
            stat = source.stat()
        except (OSError, ValueError):
            raise ReviewError(409, "Media source changed or is unavailable") from None
        size = 3000 if full else 1600
        key = hashlib.sha256(f"{source}:{expected}:{stat.st_size}:{stat.st_mtime_ns}:{size}".encode()).hexdigest()
        target = self.cache / f"{key}.jpg"
        if target.is_symlink():
            raise ReviewError(409, "Invalid cache entry")
        if target.is_file():
            return target.read_bytes()
        if not self.conversions.acquire(timeout=25):
            raise ReviewError(503, "Image conversion busy; retry shortly")
        try:
            # Read via an open descriptor, preventing path replacement from redirecting conversion.
            with os.fdopen(os.open(source, os.O_RDONLY | os.O_NOFOLLOW), "rb") as handle:
                opened = os.fstat(handle.fileno())
                if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns):
                    raise ReviewError(409, "Media source changed")
                if self.allowed_media(path) != registered:
                    raise ReviewError(409, "Media source changed")
                actual = hashlib.file_digest(handle, "sha256").hexdigest()
                if expected and actual != expected:
                    raise ReviewError(409, "Image hash differs from review evidence; rebuild the pack")
                handle.seek(0)
                converted = subprocess.run(
                    ["magick", "-limit", "memory", "128MiB", "-limit", "map", "256MiB", "-limit", "disk", "0",
                     f"{source.suffix[1:]}:-[0]", "-auto-orient", "-thumbnail", f"{size}x{size}>",
                     "-strip", "-quality", "85", "jpeg:-"], stdin=handle, capture_output=True, timeout=30,
                    env={**os.environ, "MAGICK_THREAD_LIMIT": "1"}, check=True)
                after = os.fstat(handle.fileno())
                if (after.st_size, after.st_mtime_ns) != (opened.st_size, opened.st_mtime_ns):
                    raise ReviewError(409, "Media source changed during conversion")
            # Conversion is bounded; atomic replacement prevents partial concurrent cache reads.
            self.check_state()
            temporary = self.cache / f"{key}-{secrets.token_hex(6)}.tmp"
            temporary.write_bytes(converted.stdout)
            temporary.replace(target)
            return converted.stdout
        except (subprocess.SubprocessError, OSError, ValueError):
            raise ReviewError(422, "Cannot convert this image; source files were not changed") from None
        finally:
            self.conversions.release()


class ReviewServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, store, html, port=8765):
        self.store, self.html = store, html.resolve(strict=True)
        super().__init__(("127.0.0.1", port), ReviewHandler)


class ReviewHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def reply(self, status, content, kind="application/json", attachment=False):
        if kind == "application/json":
            content = json.dumps(content, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", kind + ("; charset=utf-8" if kind != "image/jpeg" else ""))
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        if status == 503:
            self.send_header("Retry-After", "2")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if attachment:
            self.send_header("Content-Disposition", 'attachment; filename="review-events.json"')
        self.end_headers()
        self.wfile.write(content)

    def guard(self, write=False):
        host = self.headers.get("Host", "")
        port = self.server.server_port
        if len(self.headers.get_all("Host", [])) != 1 or host not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
            raise ReviewError(403, "Loopback Host required")
        if write:
            origin = self.headers.get("Origin")
            if origin is not None and origin != f"http://{host}":
                raise ReviewError(403, "Same-origin writes required")
            if not secrets.compare_digest(self.headers.get("X-Review-Token", "").encode(), self.server.store.token.encode()):
                raise ReviewError(403, "Review session token required; reload the page")

    def do_GET(self):
        try:
            self.guard()
            url = urlsplit(self.path)
            if url.path == "/" and not url.query:
                self.reply(200, self.server.html.read_bytes(), "text/html")
            elif url.path == "/api/review" and not url.query:
                self.reply(200, self.server.store.snapshot())
            elif url.path == "/api/export" and not url.query:
                snapshot = self.server.store.snapshot()
                self.reply(200, {"pack_id": snapshot["pack_id"], "events": snapshot["history"]}, attachment=True)
            elif url.path.startswith("/media/"):
                media_id = url.path[len("/media/"):]
                if not ID.fullmatch(media_id) or url.query not in {"", "full=1"}:
                    raise ReviewError(404, "Unknown media request")
                self.reply(200, self.server.store.thumbnail(media_id, bool(url.query)), "image/jpeg")
            else:
                raise ReviewError(404, "Unknown route")
        except ReviewError as error:
            self.reply(error.status, {"error": error.message})
        except (OSError, sqlite3.Error):
            self.reply(500, {"error": "Review storage unavailable"})

    def do_POST(self):
        try:
            self.guard(write=True)
            if self.path != "/api/review":
                raise ReviewError(404, "Unknown route")
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                raise ReviewError(415, "JSON body required")
            if self.headers.get("Transfer-Encoding"):
                raise ReviewError(400, "Transfer-Encoding is unsupported")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise ReviewError(400, "Invalid Content-Length") from None
            if not 1 <= length <= 65536:
                raise ReviewError(413, "Body must be 1–65536 bytes")
            body = json.loads(self.rfile.read(length))
            self.reply(200, self.server.store.save(body))
        except ReviewError as error:
            self.reply(error.status, {"error": error.message})
        except (ValueError, UnicodeError):
            self.reply(400, {"error": "Invalid JSON body"})
        except (OSError, sqlite3.Error):
            self.reply(500, {"error": "Review was not confirmed saved; reload before retrying"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--media-root", type=Path, action="append", required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--html", type=Path, default=Path(__file__).with_name("label_review.html"))
    args = parser.parse_args()
    try:
        store = ReviewStore(args.pack, args.state_dir, args.media_root)
        server = ReviewServer(store, args.html, args.port)
    except (OSError, ValueError, KeyError, TypeError, ReviewError) as error:
        parser.exit(1, f"Cannot start review: {error}\n")
    print(f"Review: http://127.0.0.1:{server.server_port}/ pack_id={store.pack_id}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
