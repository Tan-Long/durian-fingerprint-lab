# Chamber photo organization — 2026-09-30

User priority changed from per-image web review to rechecking and arranging the
original chamber photos from three camera directories by visible fruit label.
The per-image API implementation is retained at `7f6035e` in its agent branch,
not integrated or deployed. Official review state and pack were not modified.

## Method and scope

Source: `/Volumes/SoilTECH/Ảnh chụp sầu riêng/Chụp Hộc`.
All 427 originals were inventoried and SHA-256 hashed: Máy Đăng 361,
Máy IP17 56, Máy IP12 10; total original payload 978,050,786 bytes.
Existing hash-checked local previews were reused for numbered label sheets;
full previews/originals were inspected when crops were insufficient.

Root read IP12/IP17. Morphology read Máy Đăng indices 0–179; fingerprint read
180–360, each in lexicographic filename order. Every image has its own
transcription or explicit unresolved status. Old fuzzy OCR guesses, neighbor
filenames, workbook totals and assumptions about five locules were not used
to assign fruit IDs. BONUS remains separate; edited/repeated photos are kept.

Final review coverage: 427/427 unique source paths, no omissions/overlap.
396 images are grouped under 84 visibly read fruit codes; 11 have unresolved
fruit labels; 20 lack a visible fruit label suitable for grouping. These are
agent visual transcriptions, not user-approved identity or hộc/múi counts.

## Cross-checks and uncertainty

Root spot-checked the agents' images 132–143 and 240–251, plus disputed
168, 190, 192, 286, 308 and 324. Morphology independently checked root's
IP12 002/007 and IP17 017–021.

- IP12 `IMG_0717.JPG` / `IMG_E0717.JPG`: C/E prefix ambiguity, kept unresolved.
- IP17 `IMG_2640`, `2641`, `2643`, `2644`: curled 8/9 ambiguity, kept unresolved;
  `IMG_2642` has a clearer direct V9 reading. No copying of adjacent IDs.
- Máy Đăng `IMG_9799`: V8/V9 unresolved.
- `IMG_9822` / `IMG_9824`: coordinator/agent disagreement on V3/V5;
  original-photo recheck did not resolve it, so neither code is assigned.
- `IMG_9923`: written `N2-C10-V3-H5`; field order is not silently repaired.
- `IMG_9945`: overwritten V/C characters, unresolved fruit identity.
- `IMG_9962`: fruit code N2V12C3 is readable but H suffix is ambiguous;
  group by fruit, keep locule null. Organization is not locule validation.

## Artifacts and recovery

Local working evidence: `output/chamber-sort-review/inventory.json`,
`root.json`, `morphology.json`, `fingerprint.json`, camera previews/sheets.
Generated photos and per-photo data are not committed to Git.

New copy destination:
`/Volumes/SoilTECH/Ảnh chụp sầu riêng/Hoc_theo_nhan_qua_20260930`.
Structure: `fruit_code/original_camera/original_filename`, plus
`_CHUA_RO_NHAN` and `_KHONG_CO_NHAN_QUA`. `DOI_CHIEU_ANH.csv/json` records
each source/destination/hash, observed code, ambiguity and `user_approved:false`.
The original three directories, workbook and old manifest stay unchanged.

`scripts/organize_chamber_photos.py` requires complete one-to-one review
coverage, a fresh output outside originals, and safe relative paths. It
verifies source hash before copying and both source and copy after copying.
No source is moved, overwritten, deduplicated or deleted. If interrupted, keep
partial output for inspection and use a fresh destination; do not overwrite.
README contains the reproducible commands.

## Validation

20 data/server/organization tests, 11 viewer/matcher tests and 14 projection
tests passed (45 total). The new focused test exercises valid copies and
negative cases: incomplete/duplicate coverage, outputs inside source,
unsafe fruit folder, existing destination and changed source bytes.
Local executable proof only; no CI or merge-blocking claim.

Physical copy command completed: 427/427 copied and SHA-256 verified, with
original hashes still matching. Independent destination enumeration matched
all 427 ledger paths and total payload 978,050,786 bytes. The original
workbook/manifest hashes also match the previous review pack. Final ledger
SHA-256: `0aba6fca3eb9b5f436a1437acb0a94f01ac6f1998c0323f8c4ee23faf30cd081`.
Every exported record remains `user_approved:false`. Label/user acceptance
remains open; this new grouping has not been substituted into the web pack.
