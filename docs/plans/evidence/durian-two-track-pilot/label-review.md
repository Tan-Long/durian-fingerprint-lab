# Local label-review increment — 2026-09-30

## Scope and ownership

User requested a local photo-backed approval/comment page after coordinator
self-check, then reported image loading, zoom/main scrolling, and incomplete
photo evidence. Root owns UI/integration; fingerprint agent owns HTTP/storage
and thumbnail delivery; morphology agent owns pack generation. Communication
with agents is English; the review UI and user handoff are Vietnamese.

This is review tooling, not accepted labels or model PASS. Source Excel,
manifests, images and videos remain read-only. User acceptance is pending.

## Delivered evidence

- 17 review cases: identity conflict, two unmatched IDs, nine count conflicts,
  three missing shell measurements, scope/timing/empty-label questions, and the
  complete chamber-photo archive.
- All 427 chamber-manifest paths match the observed 427-photo directory
  inventory. Their content was rehashed; none are identical. Archive retains
  unreadable/unassigned photos, not only OCR matches.
- Pack contains 657 media appearances; repeated appearances across cases do
  not imply additional unique photos or additional locules.
- Independent UI review found no blocking navigation/data-loss issue. It
  caught misleading "after opening" wording for the archive (19 manifest
  entries are classified as non-locule photos). UI now labels the source
  as the chamber manifest without asserting every photo depicts a locule.
- Every per-case candidate is rendered, with other source photos separated.
  Complete literal OCR codes can add provisional candidates (including H6);
  incomplete/ambiguous codes and neighboring filenames do not establish IDs.
- Existing count-case candidate counts: N1V10C2=2, N1V11C1=2, N1V11C3=4,
  N1V1C2=6, N1V2C2=4, N1V4C1=3, N2V13C3=6, N2V17C3=2, N2V1C2=11.
  These are image counts, not verified locule counts. Per-fruit completeness
  remains unresolved; the archive lets the reviewer find further evidence.
- Coordinator inspected 12 original photos. Versioned findings and source
  hashes are in `label-review-observations.json`; findings never correct labels.

## Behavior and fixes

Localhost-only stdlib server; native HTML/CSS/JS, no frontend dependency.
Explicit save requires a comment. SQLite append-only events retain revision
history; optimistic writes reject stale edits. Decisions are bound to the
pack hash; changed evidence does not inherit approval. Sources are served only
through validated IDs and allowlisted paths. Image bytes are hash checked.

Real phone JPG/HEIC decoding initially failed with ImageMagick pixel-cache
exhaustion before resize. Bounded temporary disk spill (1 GiB per worker,
two workers) fixes this; temporary files are cleaned after conversion. A
4000×3000 regression image fails before the fix and passes after it.

The image dialog now has a bounded flex viewport, actual resized image
dimensions, zoom/fit, previous/next, native scroll and mouse drag. Main page
uses document scrolling rather than nested sidebar/history/table scroll
regions. Original facts are collapsible. No browser zoom setting is changed.

## Validation

- `python3 -B -m unittest discover -s scripts -p 'test_*.py' -v`: 19 passed.
- `test_video/.venv/bin/python -B -m unittest discover -s test_video -p 'test_*.py'`:
  11 passed.
- `test_video/.venv/bin/python -B -m unittest prototypes.durian_2d_projection.test_spike_graph`:
  14 passed. Total: 44 automated Python tests.
- Inline browser JavaScript passes `node --check`; `git diff --check` clean.
- Read-only HTTP/decode sweep: 589/589 unique media IDs passed (397 JPG,
  189 HEIC, 3 PNG sources); HTTP 200, JPEG content type/signature, successful
  decode, maximum dimension 1600 px. Zero failures; 147.1 seconds with at most
  two requests in flight. Pack hash unchanged and official history remained
  empty. This verifies image delivery, not visual label correctness.
- Isolated browser check `scripts/check_label_review_browser.js` on port 8765:
  main document scrolled 581 px; zoomed image viewport 618 px with content
  1390 px reached scrollTop 772; fit returned top 0/content 618. Mobile CSS
  viewport 390×640 had no horizontal overflow and zoomed image remained
  scrollable. All six N2V13C3 candidate images rendered separately from other
  photos; previous/next returned matching labels; all 427 archive images were
  present. Zero review writes.
- Earlier isolated port-8766 checks exercised comment/approval save and reload,
  per-case draft retention, stale-write rejection, refresh/retry, and retained
  event history. Those records are explicitly marked synthetic, never labels.
- Before switching the official pack, its export had no review events.
  Existing state and old pack were retained; test state was not deleted.

## Runtime and limits

Official page: `http://127.0.0.1:8765/`.
Active pack: `output/label-review/pack-all-chambers.json`, SHA-256
`fa265ca3339bd7af5c9334f15d1989ac16fb65eb8c2d3211c748b2a941ddea1c`.
Old pack `output/label-review/pack.json` remains available for recovery.
Official state: `output/label-review/state/decisions.sqlite3`.
Port 8766 is isolated test state, not the user review destination.
See README for build, start, export and restart commands.

Photos/state/generated packs stay local and ignored by Git. Browser images
are derived JPEGs up to 1600 px (preview) or 3000 px (enlarged), not rewritten
originals. SoilTECH must remain mounted. Saved reviews can be read again;
there is no background promise to monitor comments indefinitely. Browser
automation used available Playwright tools because the in-app skill's required
Node REPL was unavailable; this is a reported environment limitation, not a
change to Harness guidance.
