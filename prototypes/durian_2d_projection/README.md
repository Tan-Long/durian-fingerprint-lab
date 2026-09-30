# PROTOTYPE — Durian 2D Projection

Question: can the existing turntable videos be inverse-projected onto a
spherical equal-area UV map that preserves whole spike shapes?

Compare one 360° Scanner video with arbitrary consumer photos using the
throwaway full-map/partial-map prototype:

```sh
python3 prototypes/durian_2d_projection/prototype_pattern_match.py test_video
```

Build a full-detail mesh, radial height surface, and tip/base spike graph from
the Scanner turntable capture:

```sh
python3 prototypes/durian_2d_projection/scan_to_spikes.py test_video
```

The mesh scale is estimated from Scanner depth and `camera_matrix.csv`. Pass a
measured meters-per-model-unit value with `--scale` when a calibration marker is
available.

Project the reconstructed tip/base graph back onto the source RGB video for a
human audit (`red = tip`, `cyan = base boundary`):

```sh
python3 prototypes/durian_2d_projection/audit_overlay.py test_video
```

Run every fruit:

```sh
python3 prototypes/durian_2d_projection/project.py
```

Run selected fruits while iterating:

```sh
python3 prototypes/durian_2d_projection/project.py Q11 Q16
```

Process the renamed ColdHead dataset directly from its ZIP archives:

```sh
python3 prototypes/durian_2d_projection/project.py V8C3 --source /Volumes/ColdHead
```

Run only the black-background iPhone 11 capture. The turntable protocol is one
constant-speed revolution; captures with less than 60° of detected texture
motion are rejected. Tune `--min-motion` only when inspection justifies it.

```sh
python3 prototypes/durian_2d_projection/project.py V8C3 --source /Volumes/ColdHead --capture iphone11-20-den
```

Audit the Excel-to-video mapping without decoding videos:

```sh
python3 prototypes/durian_2d_projection/project.py --source /Volumes/ColdHead --list
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
SciPy, OpenPyXL (for `RENAME.xlsx`), FFmpeg, and ffprobe.
