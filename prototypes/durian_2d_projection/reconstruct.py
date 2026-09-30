#!/usr/bin/env python3
"""PROTOTYPE: reconstruct one durian mesh from masked turntable frames."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np

import project


HERE = Path(__file__).resolve().parent


def reconstruct(args: argparse.Namespace, view: str) -> None:
    videos = [
        v
        for v in project.discover(project.ROOT)
        if v.fruit == args.fruit.upper()
        and v.orientation == args.orientation
        and (view == "combined" or v.view == view)
    ]
    if not videos:
        raise RuntimeError(f"No {view} video found for {args.fruit}")

    label = f"{args.fruit.upper()}-{args.orientation}"
    if view != "combined":
        label += f"-{view}"
    target = args.output / label
    images = target / "images"
    images.mkdir(parents=True, exist_ok=True)
    for old in images.glob("*.png"):
        old.unlink()

    written = 0
    for video in videos:
        with tempfile.TemporaryDirectory(prefix="durian-3d-") as temporary:
            source = Path(temporary) / "source.mov"
            with zipfile.ZipFile(video.archive) as bundle:
                with bundle.open(video.member) as incoming, source.open("wb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing, length=8 * 1024 * 1024)
            duration = float(project.probe(source)["format"]["duration"])
            frames = project.active_frames(
                project.decode_frames(
                    source,
                    duration,
                    width=args.width,
                    height=args.width * 9 // 16,
                    samples=max(36, args.frames_per_video * 2),
                )
            )

        indexes = np.linspace(0, len(frames) - 1, args.frames_per_video).round().astype(int)
        for number, index in enumerate(indexes):
            frame = frames[index]
            mask = project.fruit_mask(frame)
            if mask is None:
                continue
            masked = np.zeros((*frame.shape[:2], 4), dtype=np.uint8)
            masked[mask, :3] = frame[mask]
            masked[..., 3] = mask.astype(np.uint8) * 255
            assert not masked[~mask].any()
            project.write_png(masked, images / f"{video.slug}-{number:03d}.png")
            written += 1

    if written < 20:
        raise RuntimeError(f"Only {written} usable images")
    model = target / f"{label}.usdz"
    model.unlink(missing_ok=True)
    bridge = target / "reconstruct"
    subprocess.run(
        [
            "swiftc",
            "-parse-as-library",
            str(HERE / "reconstruct.swift"),
            "-o",
            str(bridge),
        ],
        check=True,
    )
    print(f"images {written}: {images}", flush=True)
    subprocess.run(
        [str(bridge), str(images), str(model), args.detail],
        check=True,
    )
    if shutil.which("usdrecord"):
        subprocess.run(
            ["usdrecord", str(model), str(target / "render.png"), "-w", "1200"],
            check=True,
        )
    subprocess.run(
        [sys.executable, str(HERE / "heightmap.py"), str(model), "--output", str(target)],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fruit", help="Fruit ID, for example Q21")
    parser.add_argument("--orientation", choices=("dung", "ngang"), default="dung")
    parser.add_argument(
        "--view", choices=("separate", "tren", "duoi", "combined"), default="separate"
    )
    parser.add_argument("--frames-per-video", type=int, default=36)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--detail", choices=("reduced", "medium", "full"), default="reduced")
    parser.add_argument("--output", type=Path, default=HERE / "output-3d")
    args = parser.parse_args()

    views = ("duoi", "tren") if args.view == "separate" else (args.view,)
    failures = []
    for view in views:
        try:
            reconstruct(args, view)
        except Exception as error:
            failures.append(view)
            print(f"{args.fruit.upper()} {view} failed: {error}", file=sys.stderr)
    if failures:
        raise SystemExit(f"Failed views: {', '.join(failures)}")


if __name__ == "__main__":
    main()
