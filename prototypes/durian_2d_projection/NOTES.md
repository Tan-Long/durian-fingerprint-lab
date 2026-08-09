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

For a later capture batch, keep the fruit in one pose, record at least one full
turn plus overlap at constant speed/focus/exposure, and add high/low camera
rings without repositioning the fruit. An independent second capture of the
same intact fruit is still required to measure re-identification accuracy.
