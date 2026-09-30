# Execution Plan: Durian fingerprint and morphology pilot

Date: 2026-09-30

## Status

Active. The user authorized publishing the existing code to GitHub and then
implementing the agreed plan incrementally with two sub-agents.

On 2026-09-30 the user explicitly accepted the first increment with "Duyệt"
after reviewing the Vietnamese report for commit
`2ef6f24e609670002ce0e3c52182ebae3c3d0d18`. Fingerprint tooling, morphology
auditing, and the shared index are PASS for that increment only. Individual
labels, model accuracy, and full pilot acceptance remain unapproved.
Project-specific logs, committed evidence, coordinator review, and user review
remain required for subsequent increments; automated checks do not grant PASS.

## Outcome

Produce reproducible, independently evaluated pilots for (1) identifying a
registered fruit from a phone image and (2) predicting locule count, aril count,
and shell thickness from observations available before opening the fruit.
Keep evidence and unresolved labels explicit; a runnable prototype is not an
accuracy claim.

## Context

- Product: `docs/durian-mvp-blueprint.md` and
  `docs/durian-sample-processing-procedure.md`.
- Existing matcher: `test_video/multiview_retrieval_logic.py` and
  `test_video/batch_multiview_ingest.py`.
- Existing photo manifest: `scripts/build_hoc_manifest.py`.
- Collection: `/Volumes/SoilTECH/DurianData/collections/202608_RIG_V1`.
- Existing banks: `/Volumes/SoilTECH/DurianScan/{27082026,28082026}/processed_multiview_v1`.
- Labels: `SAMPLE_Fruit_morphology.xlsx` inside the SoilTECH chamber-photo
  directory (`Ảnh chụp sầu riêng/Chụp Hộc`; on-disk Unicode is decomposed).
- Audit observed 88 collection IDs, 84 processed sessions (82 READY), and
  123 morphology records with 563 nonempty locule rows (562 have Fruit-ID).
  These are inventory counts,
  not counts of verified independent training examples.

## Scope And Ownership

- Coordinator: shared sample/media index, this plan, worktrees, integration,
  resource scheduling, validation, and GitHub publication.
- Fingerprint agent: matcher robustness and explicit reading/querying of the
  existing per-session feature banks, with executable checks.
- Morphology agent: read-only workbook audit and sample crosswalk; report
  missing, duplicate, malformed, and conflicting labels with cell provenance.
- Agents use separate worktrees based on the same published code snapshot.
- SoilTECH sources are read-only. Outputs go under ignored local `output/`.
- No automatic label correction, raw-data movement, production deployment,
  main-branch merge, or full video reprocessing in the first increment.

## Approach

1. Publish existing source, documentation, and this plan on the current branch;
   exclude media, generated artifacts, and environments.
2. Start two agents in isolated worktrees. Initially parallelize code and
   small checks, not bulk video decoding or model training.
3. Build a common index from collection manifests and read-only audits.
   Preserve original IDs, collection, camera, session, source paths, and
   workbook rows. Ambiguous IDs and conflicting values remain review items.
4. Review and integrate the first working slice from each agent. Run real
   data audits and limited query diagnostics; publish verified code.
5. Freeze reviewed labels and evaluation groups before model evaluation.
   Fingerprint evaluation requires independent enrollment/query captures,
   calibration identities separate from final evaluation identities, and
   held-out unregistered fruit. Morphology groups all views/locules of a fruit
   together and excludes after-opening measurements from model inputs.
6. Compare morphology baselines, then image features; measure fingerprint
   retrieval, false acceptance, abstention, and latency. Select thresholds on
   development data only. Product acceptance thresholds remain undecided.
7. Provide a label-review viewer before evaluation (user-requested on
   2026-09-30), then extend model-evidence viewing after benchmarks exist.

## Coordination And Acceptance

Use this one repository plan as the shared Harness record. Keep task evidence
in `docs/plans/evidence/durian-two-track-pilot/`; do not introduce a separate
task database or orchestration lifecycle.

| Track | Agent | Implementation | Coordinator review | User acceptance |
| --- | --- | --- | --- | --- |
| Fingerprint | `/root/fingerprint` | First increment integrated at `8b6ff5d` | Unit tests passed; real-data smoke is diagnostic only | PASS — increment 1 only |
| Morphology | `/root/morphology` | First increment integrated at `0dab7ce`, `14d28d4` | Six audit tests passed; real workbook audit reproduced | PASS — increment 1 only |
| Shared data | Coordinator | Inventory committed at `87fdda6` | Two tests passed; cross-review found no blocking issue | PASS — increment 1 only |

- Agents report files, commit SHA, exact check commands, observed results,
  artifacts, and unresolved risks to the coordinator.
- Each project has its own evidence log: `fingerprint.log` and `morphology.log`.
  Shared checks and publication evidence go in `integration.log`.
- After review and publication, each new increment is **AWAITING_USER_REVIEW**.
  Only explicit user acceptance changes the corresponding reviewed increment
  to **PASS**. Record the accepted commit and scope here.
- A rejection or new request stays in this plan as follow-up work. Full pilot
  completion additionally requires the outstanding evaluation milestones;
  accepting the first increment does not accept recognition accuracy.
- Commit each bounded increment and evidence before handoff; verify the remote
  branch SHA after pushing. No force-push, automatic main merge, or dataset edit.

### First Increment Review Package

- [Fingerprint log](../evidence/durian-two-track-pilot/fingerprint.log)
  and [query evidence](../evidence/durian-two-track-pilot/fingerprint-smoke.json).
- [Morphology log](../evidence/durian-two-track-pilot/morphology.log)
  and [coverage summary](../evidence/durian-two-track-pilot/morphology-summary.json).
- [Integration log](../evidence/durian-two-track-pilot/integration.log)
  and [33-test transcript](../evidence/durian-two-track-pilot/tests.log).
- User review scope: source traceability, diagnostic query behavior, workbook
  issue reporting, and safe output handling. Recognition accuracy and morphology
  prediction have not yet been evaluated.
- Current acceptance: **PASS — increment 1 only**, explicitly accepted by the
  user with "Duyệt" on 2026-09-30 at commit
  `2ef6f24e609670002ce0e3c52182ebae3c3d0d18` for the review scope above.
- Next bounded step: both agents assess evaluation readiness read-only;
  identify evidence gaps and decisions before freezing labels or evaluation
  groups. Approval of the audit does not approve or repair its input labels.
- Agent-to-agent coordination and reports use English; user-facing reports
  and approval requests use Vietnamese, as requested by the user.

### Increment 2: Local Label Review

Authority: the user requested self-checking disputed labels, an HTML host with
photos and data, and persistent approvals/comments the coordinator can read.
They explicitly selected "Duyệt trên máy này trước" (local-machine review).

- Coordinator: Vietnamese UI, visual self-check, integration, browser proof,
  runtime instructions and Git publication.
- Fingerprint agent: loopback-only HTTP server, allowlisted media delivery and
  append-only SQLite review events with snapshot IDs and stale-write protection.
  Worktree branch: `agent/label-review-server`, based on accepted `fe720a8`.
- Morphology agent: reproducible review pack from existing audit/index with
  exact cell references, provisional photo relations and explicit open questions.
  Worktree branch: `agent/label-review-data`, based on accepted `fe720a8`.
- Reuse the existing viewer's dependency-free HTML approach and visual palette;
  no new frontend framework or external host. Photos stay on SoilTECH.
- Reviews are application data, not a Harness task database. Store them under
  ignored `output/label-review/`; never overwrite them when rebuilding a pack.
  Bind each decision to the exact pack snapshot and retain earlier events.
- An approval/comment records the user's conclusion only; it does not rewrite
  Excel, silently resolve identity conflicts, freeze a split, or grant model PASS.
- Validate source boundaries, save/reload/restart, stale writes, image delivery,
  empty/error states and the browser workflow using isolated test review state.
- User feedback expanded the scope to all chamber/aril evidence, not a single
  example. Include every chamber-manifest photo in a searchable-case archive,
  preserve provisional associations, and flag incomplete per-fruit sets. No
  adjacency-based identity inference or automatic approval is authorized.
- Status: integrated validation passed (44 Python tests, isolated browser
  scroll/gallery/navigation checks, 589/589 JPEG responses decoded). Awaiting
  user review of increment 2; full project PASS remains user-owned. Evidence:
  `docs/plans/evidence/durian-two-track-pilot/label-review.md`.

### Photo Organization Follow-up (Delivered)

- User asked to recheck all images in the three original camera directories
  under `Chụp Hộc` and organize by fruit label. Preserve originals and create
  a new grouped copy outside that source root. Do not trust old nearest-match
  OCR, infer identity from sequence, or treat organization as label approval.
- Root reviews IP12/IP17; morphology reviews Máy Đăng indices 0–179;
  fingerprint reviews indices 180–360 (lexicographic filenames). Each image
  receives a direct visual reading or an explicit unclear/no-label status.
- Inventory and per-photo review artifacts stay local. Copy must account for
  every original, retain camera/filename provenance and verify SHA-256.
- Per-photo review UI follow-up is deferred while this priority is active.
  Backend work is safely committed on `agent/photo-review-server` at
  `7f6035e`; not integrated or deployed, no official review-state changes.
- Completed the requested non-destructive organization: 427/427 verified
  copies, 396 images under 84 fruit codes, 11 unclear and 20 unlabelled.
  Original media, workbook and manifests unchanged; 45 local tests passed.
  Destination is the source root's sibling `Hoc_theo_nhan_qua_20260930`.
  Details: `docs/plans/evidence/durian-two-track-pilot/chamber-sort.md`.
  User label acceptance is still pending; the web review pack remains unchanged.
- Follow-up authorized by user: remove camera subfolders and name copies by
  fruit/visible locule (`n1v1c1_h1`), keeping original formats. Duplicate labels
  get `_02` etc.; unknown locules use `h_chua_ro`, unknown fruits retain their
  source basename in the unresolved groups. Preserve old organized layout in
  a sibling backup before rebuilding; keep source/camera provenance in ledger.
- Flat-layout follow-up completed: all 427 byte-verified copies now sit
  directly in their fruit/unresolved groups; 15 duplicate suffixes and one
  `h_chua_ro` preserve uncertainty and avoid overwrite. 46 local tests passed.
  Old layout retained in sibling `Hoc_theo_nhan_qua_20260930_truoc_doi_ten`.

### Current User Priority: Core Code Before Further Photo Work

Authority: user asked for both agents' progress and explicitly said to skip
the two photo tasks and handle code first. Stop further photo-review/UI and
organization work; retain their artifacts and deferred per-photo API branch.

- Both project cores are at accepted increment-1 tooling, not validated models.
  The intervening work was photo-review support, not model accuracy progress.
- Fingerprint agent: additive unique-fruit ranking on geometric evidence and
  batch queries through the existing matcher. Preserve per-bank encoders,
  traceability and `identity_verdict:null`; no uncalibrated accept/reject policy.
- Morphology agent: minimal train/predict/evaluate baseline for explicitly
  supplied per-fruit features, reviewed targets and train/test assignments.
  Reject fruit overlap and unapproved/after-opening inputs. Tests use synthetic
  fixtures; do not infer feature timing, freeze real splits or train on the
  current unreviewed workbook/photo associations.
- Both agents branch from published `a30a112`, own separate code/tests and
  commit bounded increments. Coordinator owns integration and project logs.
- Fingerprint contract: `fruit_ranking` groups exact recorded `sample_id`
  strings by best geometric evidence, with references into unchanged candidate
  rows. This is not verified identity resolution across collections. Batch
  input is an explicit JSON array of unique `query_id`/`image` pairs; errors
  remain per-query and cause exit 2 without losing successful query reports.
- Morphology contract: one explicit JSON input declares feature timing and
  attestations, per-fruit train/test membership, and per-target reviewed labels.
  The first baseline is the training median per target; features are validated
  but deliberately unused. Missing/unapproved labels block only their target;
  no silent row exclusion or evaluation on the real dataset is authorized.
- Completion for this code increment requires executable end-to-end fixture
  proof and integrated regression tests, followed by user review. Real-world
  recognition/prediction accuracy stays unevaluated until evidence is approved.
- Delivered: fingerprint `a89903a` integrated as `217546e`; morphology
  `55744d2` integrated as `7d2ccfe`. Coordinator reviewed code/tests and ran
  all three suites: 33 + 18 + 14 = 65 tests passed, no skips. Both actual CLI
  flows are exercised with synthetic fixtures. Separate project logs and
  `tests.log` record proof. Status: **AWAITING_USER_REVIEW**, not accuracy PASS.

### Core-Code Results Review Surface

User requested showing the delivered results for review. Reuse the existing
loopback review server and append-only feedback, with a separate core-code
pack/state (not the photo pack). Display actual synthetic fixture outputs,
held-out truth/predictions, geometric ranking, source snapshot and limits.
No additional real-image processing, model training or inferred approval.
Keep the SoilTECH green/neutral, border-based interface and document scrolling;
tables precede technical details, and each track has its own decision/comment.
Coordinator owns the additive core mode and browser proof; fingerprint agent
owns the minimal reproducible fixture pack builder/test. No new backend or
frontend framework. Test feedback uses isolated state, never user decisions.

User rejected the synthetic-only surface as insufficient for recognition review:
they explicitly need accompanying images. Follow-up: run one real phone-photo
diagnostic against existing banks (no accuracy benchmark), show the query,
exact selected reference video frames and geometric-correspondence overlays
for three distinct recorded-ID candidates. Decode only selected video prefixes,
keep source banks/media read-only and derived evidence under ignored output.
Do not assert the unverified query-folder ID is truth or that top rank is a
correct identity. Expose writing/tag/background leakage and uncalibrated status.
Morphology remains clearly pending an image predictor; replace synthetic result
numbers with that gap in the real-evidence pack. Preserve previous packs/state.

Further user clarification: predict hidden locule/aril counts from INTACT-fruit
inputs; opened-fruit photos and workbook are reference targets only. Selected
real demo N1V10C3 has independent labelled phone photos, five visibly labelled
H1–H5 photos, workbook totals5/10/20mm and both READY camera streams. Selection
is source-crosschecked, not user-approved gold truth; optional fields remain
missing. Current bank retrieval fails this example (top1 N2V52C3, selected ID
absent fromtop3), which must remain visible and not be rewritten as success.

User explicitly directs using original CAM_TREN/CAM_DUOI RGB + LiDAR sources
under DurianScan. Read selected session sync.json/README_AGENT and repository
StrayScanner format: frame-aligned depth in mm, confidence0/1/2, cadence from
frame_transforms timestamp_unix, flash-relative alignment, independent cameras;
no ARKit cross-camera fusion. Bounded next slice uses fresh source-frame RGB
features inside depth/confidence foreground masks and compares the independent
photo to36 sampledframes per camera of this KNOWN sample. Cached banks provide
sampling frame indexes only, not descriptors. This alignment demo is separate
from database identity retrieval and does not fix its measured failure by fiat.
Expose source RGB/depth/confidence/foreground layers per camera with selectors,
exact frame/timing/provenance and point correspondences. These are exterior
observations, never internal locule/mui segmentations. No hidden-count model or
accepted accuracy exists; keep missing predictions explicit.

## Risks And Recovery

- Most prototype code was untracked at the start. Publish the source baseline
  before making worktrees; retain all original local artifacts.
- The two bank roots have different vocabulary/PCA files. Never compare their
  coarse vectors as if they used one encoder. Initial diagnostics must apply
  each bank's matching encoder; a later unified benchmark can re-encode under
  a frozen shared encoder trained only on development data.
- Existing READY status checks capture consistency, not recognition accuracy.
- Workbook has variable locule counts, duplicated/malformed locule numbers,
  totals that disagree, and ambiguous BONUS/sample IDs. Do not infer labels.
- Do not conflate locules with arils or missing labels with zero.
- Agents change only assigned files; shared-contract changes return to the
  coordinator. Integrate reviewed commits without force-push or history reset.
- New outputs are disposable and separate from sources; retain worktrees for
  inspection if an increment fails.

## Progress

- [x] Inspect repository, dataset inventory, code paths, and workbook.
- [x] Baseline validation: 8 ingest/viewer tests and 14 spike/projection tests pass.
- [x] Publish source baseline to GitHub and verify remote commit (`bfa3925`).
- [x] Start fingerprint and morphology agents in separate worktrees.
- [x] Produce shared media index and workbook audit without modifying sources.
- [x] Integrate and validate first fingerprint and morphology increments.
- [x] Publish validated increment to GitHub (`a260cb7`, remote SHA verified).
- [x] User checks and accepts the first increment of each project (`2ef6f24`, "Duyệt").
- [ ] Review label issues and freeze evaluation groups.
- [ ] Run independent fingerprint and morphology benchmarks.
- [ ] Integrate evidence viewer and record final limits.

## Validation

- Baseline: `test_video/.venv/bin/python -B -m unittest discover -s test_video -p 'test_*.py'`
  and `test_video/.venv/bin/python -B -m unittest prototypes.durian_2d_projection.test_spike_graph`.
- Each new nontrivial data or matching behavior needs a focused executable
  check, including malformed/insufficient input and a valid case.
- Audit real workbook/manifest counts and source provenance; report coverage
  by task, not just total image count.
- Verify pushed branch SHA against GitHub; no CI or recognition-accuracy claim
  follows merely from local unit tests passing.

## Result

In progress. No benchmark accuracy or production readiness has been established.

### Canonical fingerprint dataset — 2026-09-30

- User-confirmed query folders were indexed read-only with matching enrollment
  videos into `output/fingerprint-dataset-v1`; SoilTECH sources were unchanged.
- The snapshot contains 1,228 assets for 62 physical fruit IDs: 154 enrollment
  videos and 1,074 query photos. Every fruit has at least one complete
  `CAM_TREN` + `CAM_DUOI` enrollment session.
- Query identities are deterministically locked to 50 development and 12
  calibration fruits. Current photos are not blind or 30-day evidence.
- `manifest.csv` SHA-256 is
  `ba38a7d8f8f45220e6a4bc4a12c9788727dbeb83c3111111910e76bdb1c57b4d`.
  All 1,228 raw entries are symlinks, none are broken, and no identical content
  is assigned across different fruit IDs.
- Rebuild with `scripts/build_fingerprint_dataset.py`; two focused tests cover
  traceable symlinks, session-level splits, source preservation, safe reruns and
  cross-fruit checksum conflicts. The existing dataset-index tests also pass.
- Query capture timestamps remain unknown. Symlinks require the SoilTECH volume
  at its recorded mount path. Final 30-day PASS still requires the separate
  sealed 80-known + 20-unknown cohort.

### Two-original-stream real demo — 2026-09-30

- Root integrated fingerprint visual builder `fec200e`, RGBD helper `210993a`
  and fresh-feature consumer `322584b`; agents worked on separate code surfaces.
- Real selected source: N1V10C3 / 20260828-124510-e9f5. Both original cameras
  supply RGB + exact-frame depth/confidence. Source-correlated card and H1–H5
  evidence exists locally; identity and Excel targets remain user-unapproved.
- Actual fresh run: 72 frames, 1483 query features, 29.124 s; ALL 72 have zero
  geometric inliers. 71 have fewer than 8 ratio matches; remaining frame621
  has 9 but geometry fails (branch not retained). No threshold tuning.
  Displayed CAM_TREN82/CAM_DUOI80 are earliest zero-score ties, not successful
  matches. No obvious empty-mask or image-coordinate bug found in agent review.
- Prior real bank retrieval remains visible: N2V52C3, N1V1C3, N1V12C2 top3;
  selected ID absent. Known-sample alignment does not replace dataset retrieval.
- Viewer serves `output/n1v10c3-demo-pack-v2.json` on 127.0.0.1:8772,
  pack SHA256 `ec1d42d2244c023c52854e261453507073d11eff5f5bc201f96c8f408bbbaedd`.
  State `output/n1v10c3-review-state`; old photo-review/synthetic state preserved.
  12 RGBD selectable layers; full card and five opened references; failed
  retrieval's exact frames/overlays. Zero-match warning above photos.
- Root reused the existing local review server/UI (no dependencies), separated
  Excel reference values from absent predictions, and added assembly checks.
- Validation: scripts34 + test_video33 + projection14 = 81 passing tests.
  Browser isolated8773: 12 layers,6 reference photos,7 retrieval images decoded;
  zoom scroll, document scroll, mobile width, save/reload, comment preserving
  decision passed, zero page errors. Initial fixed-delay scroll assertion raced
  modal closure; replaced with actual hidden/scroll waits, no UI scroll change.
- Missing: successful cross-photo fingerprint match, hidden-count image model,
  approved fruit-level evaluation split and accepted labels. No model PASS.
  Next: inspect frame621 geometry failure and cross-view feature robustness;
  build image-based morphology only with reviewed supervision/evaluation scope.

### Shell-number localization/OCR trial — 2026-09-30

- Authority: user asks code to recognize the existing numbers on the shell;
  do not ask the user to annotate locations already visible in source images.
- Added `scripts/detect_shell_numbers.py`: blue-ink proposals within a coarse
  green-body hull, local Apple Vision OCR on RGB/binary crops at four rotations.
  Reused source hashing, read-only image loader, exclusive output and review
  pack structure. No dependencies, agents, model downloads or source writes.
- Real run on original IMG_4171.HEIC plus both previously extracted RGB frames:
  `output/shell-numbers-N1V10C3-v3/pack.json`. Proposal counts 10/6/12;
  zero unambiguous literal digits read. Main inspection sees marks including
  3/4/5 in proposed boxes, alongside false proposals. This is PARTIAL localization,
  NOT successful number recognition, locule segmentation or a locule count.
- Earlier trials retained under output; v1 included blue background, v2 split
  faded digit strokes. Final bounds improve localization but OCR remains failed.
- Focused test covers blue proposal geometry, background rejection, no-ink case,
  exact digit parsing and no repair of S/I/fruit IDs into numeric labels.
- Reproduce (use a new output name):
  `test_video/.venv/bin/python -B scripts/detect_shell_numbers.py --image IMAGE --output-dir output/NEW_NAME`.
  Proof: `test_video/.venv/bin/python -B -m unittest test_video.test_shell_numbers -v`.
  Next bottleneck is isolated handwritten-digit recognition, not more review UI.

### First Increment Evidence

- Published baseline `bfa3925` to `origin/agent/add-durian-2d-projection`;
  verified the remote SHA. Original dataset and generated outputs remain local.
- Worktrees: `.worktrees/fingerprint` (`agent/fingerprint-pilot`) and
  `.worktrees/morphology` (`agent/morphology-pilot`).
- `scripts/build_dataset_index.py` indexed 325,311 migration rows into 3,146
  media rows: 210 RGB videos, 2,509 random photos and 427 chamber photos.
  All selected paths exist. There are 1,343 media rows without a sample ID
  (1,058 random photos, 285 chamber photos); these remain unresolved.
- Inventory covers videos for 87 recorded IDs, random photos for 72, and
  chamber photos with recorded IDs for 62. This is not verified label coverage.
- Index artifacts: `output/data-index/{samples.csv,media.csv,summary.json}`;
  ignored by Git. Summary records hashes of both source manifests, not a new
  verification of all media content.
- A visually inspected phone image `N1V11C1/IMG20260827114814.jpg` contains
  handwritten numbers on the shell and a stem label. It may test the query
  plumbing but cannot establish natural fingerprint accuracy.
- Morphology audit reproduced 123 fruit records and 563 nonempty detail rows;
  one detail row lacks Fruit-ID (`A653`). Exact crosswalk matches 86/88 IDs.
- Workbook-wide labels passing current checks: 111 locule counts, 107 aril
  counts, 119 shell thicknesses, 36 empty-locule counts. In the August crosswalk,
  these counts are 77, 77, 83 and zero, respectively. They are not approved labels.
- Final integrated validation: 8 data-tool tests, 11 ingest/viewer/matcher tests,
  and 14 projection/spike tests passed (33 total). Logs retain evidence and limits.
- Both agents returned their reviewed first increments, now accepted by the
  user. Full project PASS and model evaluation remain pending later milestones.
- Published the code, per-project logs, test transcript, diagnostic query and
  morphology summary at `a260cb7e83044a0699e9deda21b04029281cf2bb` on
  `origin/agent/add-durian-2d-projection`; the remote SHA matched locally.
  This subsequent documentation update records that observed publication.
