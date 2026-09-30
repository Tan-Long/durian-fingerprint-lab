# Pretrained retrieval models for phone photos of durian shell regions

Research cutoff: 2026-09-30. This is a model-selection decision, not accuracy
evidence. No SoilTECH media was read or changed.

## Decision

Benchmark the smallest useful ladder, in this order:

1. **XFeat sparse** replaces SIFT while retaining the repository's exact linear
   scan, per-bank coarse shortlist, and fundamental-matrix RANSAC. Rebuild a
   separate XFeat bank; never reinterpret existing SIFT arrays. This is the
   primary pretrained baseline because the official model emits keypoints plus
   compact 64-D descriptors, runs on CPU, and specifically targets viewpoint and
   illumination robustness.
2. **DINOv2 ViT-S/14** is an optional coarse-retrieval challenger in front of
   the same XFeat verifier. Compare the official `[CLS]` and average-patch-token
   representations; choose only on the frozen development split. It is not a
   replacement for local geometric evidence.
3. **ALIKED + LightGlue** is the second local-verification challenger if XFeat
   plus nearest-neighbour matching misses positives. Run it only on shortlisted
   frame pairs. The extractor/matcher pairing and licenses are explicitly
   supported by the official LightGlue distribution.
4. **RoMa** is an escalation experiment on the top few frame pairs only, and
   only if both sparse pipelines fail recall with a GPU available. Do not build
   the first bank or server around it.

Do not add ANN/vector-database infrastructure for the pilot. The repository's
measured exact search over 36,000 views is 2.1 ms; feature extraction and pairwise
verification are the current cost and recall risks.

## Shortlist evidence

| Candidate | Primary-source facts | License | Fit and limit |
| --- | --- | --- | --- |
| XFeat | Official implementation reports sparse and semi-dense modes, 64-D descriptors, real-time VGA CPU inference, and better viewpoint/illumination robustness than ORB/SIFT. The paper evaluates pose estimation and visual localization, not fruit identity. | Apache-2.0 | Smallest change to the current local-feature bank. Requires PyTorch and a fresh bank/schema because descriptors are 64-D rather than SIFT's 128-D. |
| DINOv2 ViT-S/14 | Official model card lists a 21M-parameter ViT-S, 384-D tokens, 14-pixel patches, nearest-neighbour image retrieval, `[CLS]` and average-patch-token use, and Apache-2.0 code/weights. | Apache-2.0 | Cheap independent coarse signal after offline frame encoding. Arbitrary shell crops may not preserve enough global context; benchmark, do not assume. |
| ALIKED + LightGlue | Official LightGlue code accepts ALIKED keypoints/descriptors and returns correspondences; its adaptive matcher targets speed/accuracy for sparse matching. | ALIKED BSD-3-Clause; LightGlue code/weights Apache-2.0 | Stronger learned pairwise verifier with a documented pairing, but adds torchvision, Kornia, and another learned matcher. |
| RoMa | Official paper targets dense matching under large scale, illumination, viewpoint, and texture changes using DINOv2 coarse features; default implementation works at 560 then upsamples to 864. | Code MIT; DINOv2 component Apache-2.0 | Useful failure-case challenger, but pairwise dense inference and its broad dependency set make it a poor first-stage bank. |

## Integration constraints from this repository

- Current flow is SIFT -> RootSIFT -> per-root PCA/BoW -> exact top-view scan ->
  BF ratio test -> fundamental-matrix RANSAC. Banks hard-code 128-D input and
  int8 projected descriptors. XFeat needs a separately versioned encoder and
  rebuilt bank; DINOv2 needs a separate embedding artifact.
- Preserve per-root encoder SHA-256, recorded sample/session/camera/frame, READY
  filtering, and `identity_verdict: null` until development thresholds and the
  blind split support a decision. Never compare coarse scores produced by
  different encoders.
- The committed runtime requirements are only NumPy, SciPy, and headless OpenCV.
  Every shortlisted learned model adds PyTorch. LightGlue additionally declares
  torchvision, Kornia, OpenCV, Matplotlib, and NumPy; RoMa declares a much larger
  stack including torchvision, timm, Kornia, albumentations, poselib, and wandb.
- Pin repository commit and local weight SHA-256 in the processed-data manifest.
  Do not download code or weights during a query request.
- Keep the current foreground/depth-confidence mask path. Learned features do
  not remove leakage from labels, turntable, background, or dark markings.
- Keep exact search through 1,000 fruit unless measured latency disproves the
  existing result. Apply expensive learned matching only to shortlisted frames.
- Use 1-3 query-image evidence aggregation only after single-image scores are
  preserved; repeated photos must not be treated as independent training items.

## Minimum benchmark matrix

Use the already-agreed split by capture event, including blind positives and
held-out unregistered fruit. No fine-tuning during this comparison.

1. Existing SIFT baseline.
2. XFeat sparse + existing coarse/geometry structure.
3. DINOv2 ViT-S/14 coarse shortlist + XFeat verification.
4. ALIKED + LightGlue verification on the same shortlist budget.

Keep shortlist size and image-resolution budgets explicit. Report top-1,
top-5, unknown rejection, abstention, candidate recall before verification,
latency p50/p95, peak memory, and errors by capture age/lighting/view overlap.
Only test RoMa on the sparse methods' false negatives. Advance the simplest row
that reaches the pilot thresholds; otherwise the result is evidence that capture
coverage or domain adaptation must be revisited.

## Exclusions

- **SuperPoint + LightGlue:** LightGlue's official repository warns that
  SuperPoint inference code and weights use a separate restrictive license.
  ALIKED is the documented permissive alternative.
- **DINOv3 for the first pilot:** official weights require accepting a custom
  DINOv3 license and access approval. DINOv2 has directly downloadable
  Apache-2.0 code/weights and is sufficient to answer the baseline question.
- **RoMa as primary retrieval/index representation:** it is a pairwise dense
  matcher, not the smallest bank replacement, and its official package has a
  materially larger dependency surface.
- **Training from scratch, early fine-tuning, ANN, or a new vector database:**
  none addresses the currently observed lack of robust positive matches, and
  each adds a variable before the pretrained baseline is measured.

## Primary sources and inspected revisions

- Meta AI, [DINOv2 official repository and model
  card](https://github.com/facebookresearch/dinov2/blob/main/MODEL_CARD.md),
  inspected commit `7764ea0f912e53c92e82eb78a2a1631e92725fc8`;
  [paper](https://arxiv.org/abs/2304.07193).
- VeRLab, [XFeat official
  repository](https://github.com/verlab/accelerated_features), inspected commit
  `e92685f57f8318b18725c5c8c0bd28c7fe188d9a`;
  [CVPR 2024 paper](https://openaccess.thecvf.com/content/CVPR2024/papers/Potje_XFeat_Accelerated_Features_for_Lightweight_Image_Matching_CVPR_2024_paper.pdf).
- ETH CVG, [LightGlue official repository](https://github.com/cvg/LightGlue),
  inspected commit `eb42fee2d71449efb0aa5c10549752b5d75384d8`;
  [ICCV 2023 paper](https://openaccess.thecvf.com/content/ICCV2023/papers/Lindenberger_LightGlue_Local_Feature_Matching_at_Light_Speed_ICCV_2023_paper.pdf).
- Zhao et al., [ALIKED official repository and BSD-3-Clause
  license](https://github.com/Shiaoming/ALIKED), inspected commit
  `683d7c65197395c0b3f01ebe76e1084a27e73a65`.
- Edstedt et al., [RoMa official repository](https://github.com/Parskatt/RoMa),
  inspected commit `77f8d68803526dcddfd9b7a46bc76125bdc25f15`;
  [CVPR 2024 paper](https://openaccess.thecvf.com/content/CVPR2024/papers/Edstedt_RoMa_Robust_Dense_Feature_Matching_CVPR_2024_paper.pdf).
- Meta AI, [DINOv3 official repository](https://github.com/facebookresearch/dinov3)
  and [official weight-access FAQ](https://github.com/facebookresearch/dinov3/issues/108),
  inspected commit `6876159a11b4df116f30f667f8c9888617df0751`.

## Unresolved risks

- None of the cited benchmarks measures same-instance retrieval on repetitive,
  curved durian shell texture or 30-day biological appearance change.
- A phone crop may not overlap either enrollment camera, so no model can recover
  absent surface coverage; candidate-recall errors must be separated from
  verifier errors.
- DINOv2 global tokens may rank fruit shape/background rather than the local
  spike-foot/groove pattern. XFeat/ALIKED may also repeat-match similar spikes.
- CPU-only latency on the eventual server and compatibility of the repository's
  Python environment with PyTorch/torchvision remain unmeasured.
- Thresholds for unknown rejection and multi-photo aggregation remain a later
  calibration decision; this research does not set them.
