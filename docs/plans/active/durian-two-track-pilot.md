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
