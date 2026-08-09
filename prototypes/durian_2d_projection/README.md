# PROTOTYPE — Durian 2D Projection

Question: can the existing turntable videos be inverse-projected onto a
spherical equal-area UV map that preserves whole spike shapes?

Run every fruit:

```sh
python3 prototypes/durian_2d_projection/project.py
```

Run selected fruits while iterating:

```sh
python3 prototypes/durian_2d_projection/project.py Q11 Q16
```

Open `prototypes/durian_2d_projection/output/index.html` when processing
finishes. The output is disposable and ignored by git.

The projection is spherical equal-area UV rather than literal UTM. UTM is a transverse
Mercator projection for narrow geographic zones; it is not suitable for one
continuous 360-degree fruit map. Each source pixel here is mapped from an
orthographic ellipsoid into longitude/latitude and overlapping views favor the
least-oblique camera angle.

Run the small projection check:

```sh
python3 prototypes/durian_2d_projection/project.py --self-check
```

The RGB atlas cannot retain radial spike height. Test a real mesh from one
fruit before building a comparable height map:

```sh
python3 prototypes/durian_2d_projection/reconstruct.py Q21 --orientation dung --view separate
```

The default is 36 frames from each of the two view videos (72 images per
fruit). RGB and alpha are both zero outside the fruit mask; transparent pixels
must not retain the stationary background.

This uses Apple RealityKit/Object Capture already available on this Mac and
writes independent `duoi` and `tren` meshes plus height maps under
`output-3d/Q21-dung-duoi/` and `output-3d/Q21-dung-tren/`. Never mix camera
rings or the `dung` and `ngang` captures in one reconstruction.

Summarize the Q1/Q10/Q21 quality-gate pilot without rebuilding meshes:

```sh
python3 prototypes/durian_2d_projection/report_3d.py Q1 Q10 Q21
```

After the pilot passes, resume the quality-gated salvage batch. Completed views
are skipped, so the command is safe to restart:

```sh
python3 prototypes/durian_2d_projection/batch_3d.py
```

Requirements already present on the development machine: Python 3, NumPy,
SciPy, FFmpeg, and ffprobe.
