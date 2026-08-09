#!/usr/bin/env python3
"""PROTOTYPE: summarize 2.5D reconstruction quality without rerunning it."""

from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fruits", nargs="*", default=["Q1", "Q10", "Q21"])
    parser.add_argument("--views", nargs="+", choices=("tren", "duoi"), default=("duoi", "tren"))
    parser.add_argument("--output", type=Path, default=HERE / "output-3d")
    args = parser.parse_args()

    rows = []
    for fruit in args.fruits:
        for view in args.views:
            label = f"{fruit.upper()}-dung-{view}"
            folder = args.output / label
            model = folder / f"{label}.usdz"
            render = folder / "render.png"
            height = folder / "height-map.png"
            data = folder / "height-normalized.npy"
            coverage = float(np.isfinite(np.load(data)).mean()) if data.is_file() else 0.0
            if coverage >= 0.4:
                status = "pass"
            elif data.is_file():
                status = "partial"
            elif model.is_file():
                status = "mesh_unusable"
            else:
                status = "reconstruction_failed"
            rows.append(
                {
                    "fruit": fruit.upper(),
                    "view": view,
                    "status": status,
                    "coverage": f"{coverage:.4f}",
                    "model": model.relative_to(args.output).as_posix() if model.is_file() else "",
                    "render": render.relative_to(args.output).as_posix() if render.is_file() else "",
                    "height_map": height.relative_to(args.output).as_posix() if height.is_file() else "",
                }
            )

    with (args.output / "pilot-manifest.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    cards = []
    for row in rows:
        images = "".join(
            f'<img src="{html.escape(row[key])}" alt="{key}">'
            for key in ("render", "height_map")
            if row[key]
        )
        cards.append(
            f"<article><h2>{html.escape(row['fruit'])} / {row['view']}</h2>"
            f"<p class='{row['status']}'>{row['status']} · {float(row['coverage']):.0%} coverage</p>"
            f"{images}</article>"
        )
    passed = sum(row["status"] == "pass" for row in rows)
    passed_fruits = sum(
        any(row["fruit"] == fruit.upper() and row["status"] == "pass" for row in rows)
        for fruit in args.fruits
    )
    document = f"""<!doctype html><meta charset="utf-8">
<title>Durian 2.5D pilot</title>
<style>body{{font:15px system-ui;background:#111;color:#eee;margin:24px}}article{{margin:32px 0}}
img{{max-width:720px;width:100%;display:block;margin:10px 0;background:#000}}.pass{{color:#65d879}}
.mesh_unusable,.reconstruction_failed{{color:#ff756d}}</style>
<h1>PROTOTYPE — separate-view 2.5D pilot</h1><p>{passed}/{len(rows)} views passed; {passed_fruits}/{len(args.fruits)} fruits have at least one passing map.</p>
{''.join(cards)}"""
    (args.output / "index.html").write_text(document)
    print(f"pilot {passed}/{len(rows)} pass: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
