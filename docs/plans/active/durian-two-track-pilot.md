# Execution Plan: Durian fingerprint and morphology pilot

Date: 2026-09-30

## Status

Active. The user authorized publishing the existing code to GitHub and then
implementing the agreed plan incrementally with two sub-agents.

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
  123 morphology records with 562 locule rows. These are inventory counts,
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
- [ ] Publish source baseline to GitHub and verify remote commit.
- [ ] Start fingerprint and morphology agents in separate worktrees.
- [ ] Produce shared media index and workbook audit without modifying sources.
- [ ] Integrate and validate first fingerprint and morphology increments.
- [ ] Publish validated increment to GitHub.
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
