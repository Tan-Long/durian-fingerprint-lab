#!/usr/bin/env python3
"""PROTOTYPE: quality-gated salvage batch for independent top/bottom maps."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import project


HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fruits", nargs="*")
    parser.add_argument("--output", type=Path, default=HERE / "output-3d")
    args = parser.parse_args()

    available = sorted(
        {video.fruit for video in project.discover(project.ROOT)},
        key=lambda fruit: int(fruit[1:]),
    )
    fruits = [fruit.upper() for fruit in args.fruits] or available
    failures = []
    for fruit in fruits:
        for view in ("duoi", "tren"):
            target = args.output / f"{fruit}-dung-{view}" / "height-normalized.npy"
            if target.is_file():
                print(f"skip {fruit} {view}: complete", flush=True)
                continue
            print(f"start {fruit} {view}", flush=True)
            result = subprocess.run(
                [
                    sys.executable,
                    str(HERE / "reconstruct.py"),
                    fruit,
                    "--orientation",
                    "dung",
                    "--view",
                    view,
                    "--output",
                    str(args.output),
                ],
                check=False,
            )
            if result.returncode:
                failures.append(f"{fruit}-{view}")

    subprocess.run(
        [sys.executable, str(HERE / "report_3d.py"), *fruits, "--output", str(args.output)],
        check=True,
    )
    if failures:
        raise SystemExit(f"Failed: {', '.join(failures)}")


if __name__ == "__main__":
    main()
