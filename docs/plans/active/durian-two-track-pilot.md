# Execution Plan: Durian fingerprint and morphology pilot

Date: 2026-09-30

## Status

Active. The user authorized publishing the existing code to GitHub and then
implementing the agreed plan incrementally with two sub-agents.

User acceptance is pending. On 2026-09-30 the user required project-specific
logs, committed evidence, coordinator review, and their own check before PASS.
Passing automated checks does not grant project acceptance.

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
7. Extend the existing viewer after useful evaluation evidence exists.

## Coordination And Acceptance

Use this one repository plan as the shared Harness record. Keep task evidence
in `docs/plans/evidence/durian-two-track-pilot/`; do not introduce a separate
task database or orchestration lifecycle.

| Track | Agent | Implementation | Coordinator review | User acceptance |
| --- | --- | --- | --- | --- |
| Fingerprint | `/root/fingerprint` | First increment integrated at `8b6ff5d` | Unit tests passed; real-data smoke is diagnostic only | Pending |
| Morphology | `/root/morphology` | First increment integrated at `0dab7ce`, `14d28d4` | Six audit tests passed; real workbook audit reproduced | Pending |
| Shared data | Coordinator | Inventory committed at `87fdda6` | Two tests passed; cross-review found no blocking issue | Pending |

- Agents report files, commit SHA, exact check commands, observed results,
  artifacts, and unresolved risks to the coordinator.
- Each project has its own evidence log: `fingerprint.log` and `morphology.log`.
  Shared checks and publication evidence go in `integration.log`.
- After review and publication, the first increment is **AWAITING_USER_REVIEW**.
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
- Current acceptance: **AWAITING_USER_REVIEW** for both first increments.
  No user PASS has been recorded. Wait for that review before advancing these
  increments to the next agreed stage.

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
- [ ] Publish validated increment to GitHub.
- [ ] User checks and accepts the first increment of each project.
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
- Both agents returned their reviewed first increments. Full project PASS and
  model evaluation remain pending the user's review and later milestones.
