# Prototype verdict

**REJECT the RGB strip/spherical atlas for fingerprint matching.** The first
narrow-strip atlas broke spikes at frame boundaries. Spherical projection also
failed the requirement because a frontal RGB pixel does not encode the radial
distance between a spike base and tip. Q21 additionally measured only about
230 degrees of useful rotation in one video, so forcing it to 360 degrees
stretched and duplicated surface features.

**PARTIAL GO for 2.5D photogrammetry.** The first reconstruction mask made pixels
transparent but accidentally retained the stationary background in their RGB
channels. Zeroing both RGB and alpha removed the background geometry. Increasing
sampling from 18 to 36 frames per video also fixed the broken Q1 mesh and the Q10
reconstruction failure.

The standardized 72-image pilot now produces spike geometry for all three
fruits, but only one passes the 40% connected-map gate: Q1 covers 37%, Q10 53%,
and Q21 27%. Object Capture consistently accepts most of one 36-frame view and
rejects most or all of the second `tren/duoi` view. The two camera rings therefore
still do not form one complete mesh.

Reconstructing the views independently removes that conflict. The separate-view
pilot produced meshes for all six inputs: Q1 `duoi` 50% and `tren` 47%; Q10
`duoi` 39% and `tren` 26%; Q21 `duoi` 37% and `tren` 49%. Three of six views pass
the 40% gate and two of three fruits have at least one passing map. This is a go
for quality-gated salvage batching, while keeping the two views separate.

The full Q1-Q21 salvage batch processed 42 independent views using 36 masked
frames per video. Seventeen views pass the 40% coverage gate, 21 are partial,
and four meshes are unusable. Thirteen of 21 fruits have at least one passing
view: Q1, Q2, Q3, Q5, Q8, Q9, Q12, Q13, Q16, Q17, Q18, Q19, and Q21. A visual
spot-check of high-coverage maps confirms spike relief and a removed background,
but also shows holes and edge distortion; `pass` therefore means a comparison
candidate, not a complete 360-degree fingerprint.

The current captures still cannot produce a defensible complete 360-degree map
with every spike base and tip. Partial maps may be matched only against the same
view class (`tren` to `tren`, `duoi` to `duoi`).

## ColdHead pilot (August 2026)

The external dataset contains 36 `V{garden}C{tree}` samples across nine capture
classes. The Excel mapping plus renamed LiDAR archives resolve 641 of 648
expected capture slots; seven are missing or ambiguous. The source reader now
opens those ZIPs in place and does not duplicate the roughly 64 GB dataset.
Opened-fruit photos cover 29 of 36 samples; `V4C2`, `V5C1`, `V7C2`, `V9C2`,
`V9C3`, `V10C2`, and `V12C3` have none. These photos are evidence, not training
labels: no machine-readable grade or defect annotation accompanies them.

A repeat-capture pilot processed `V1C1` and `V8C3` across iPhone 11 (18/7 and
20/7 black background) and LiDAR RGB (21/7 black background), both orientations:
12/12 selected videos produced maps. Texture displacement was not a reliable
absolute angle for near-symmetric fruit, so it is now only a motion gate; atlas
phase follows the recorded one-turn, constant-speed acquisition protocol.

The RGB verdict remains **REJECT for identification**. A simple cyclic edge-map
comparison gave overlapping score ranges: same-fruit 0.032–0.531 (median 0.118)
versus different-fruit 0.013–0.223 (median 0.056). With even the two-fruit pilot,
no threshold separates genuine and impostor pairs. The LiDAR depth stream is
256×192 at roughly 2–3 mm per fruit pixel; it can support coarse shape checks,
but not a claim that individual spike tips are measured reliably.

For a later capture batch, keep the fruit in one pose, record at least one full
turn plus overlap at constant speed/focus/exposure, and add high/low camera
rings without repositioning the fruit. An independent second capture of the
same intact fruit is still required to measure re-identification accuracy.

## Full-map/consumer-photo trial (August 2026)

The turntable video produced a 360-degree canonical map. A held-out video view
at 95 degrees was recovered at 100 degrees (5-degree error, NCC 0.138), so the
projection and circular search work when capture conditions match. The five
consumer photos scored only 0.0352–0.0738. This is not yet an identification
signal: retain the projection experiment, but reject these NCC scores as a
same-fruit decision until different-fruit controls establish a threshold.

## Multi-frame LiDAR spike fusion (August 2026)

Question: can the 256×192 Scanner depth stream be fused over one turn to retain
the height of each individual spike?

The prototype now tracks the non-uniform turntable motion with matched RGB
features plus LiDAR coordinates, fixes the axial coordinate across frames, and
compares two depth models from the same capture. The canonical model samples
one high-confidence centerline profile per tracked angle. The experimental
model fuses 41 depth samples over a ±22° front band per angle.

For `test_video`, centerline depth retained a 99th-percentile local relief of
4.15 mm. Front-band fusion averaged that signal down to 1.23 mm despite 86.3%
coverage and a median 38 observations per cell. The fused band is therefore
rejected as the canonical surface. Centerline depth is retained as a coarse
metric channel, while the RGB image must locate spike tips and bases. Visible
frame-wide LiDAR streaks mean depth cannot yet be treated as per-spike ground
truth.

Run the disposable prototype with:

```sh
test_video/.venv/bin/python test_video/rgbd_mesh.py \
  --dataset test_video/CAM-TURNTABLE-01 \
  --output test_video/processed/rgbd-spike-fusion \
  --rows 360 --columns 256 --mesh-rows 180 --mesh-columns 180
```
