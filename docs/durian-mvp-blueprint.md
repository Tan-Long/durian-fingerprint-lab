# Durian MVP Blueprint

## Mục tiêu

Xây hệ thống dữ liệu cho 2 bài toán cùng một pipeline lấy mẫu:

1. **Identity verification**: xác minh đúng quả sầu riêng cụ thể, ưu tiên không phụ thuộc marker/QR.
2. **Quality grading**: ước lượng số múi, múi đầy/lép, yield cơm ăn được, độ chín/hư hỏng từ scan ngoài vỏ.

Nguyên tắc chính: **scan không phá quả để dự đoán**, nhưng **phá một subset mẫu để lấy ground truth**.

## Quyết Định Đã Chốt

- Định danh ở mức **đúng quả cụ thể**, không chỉ đúng lô/vườn.
- Đăng ký gốc có thể dùng rig/thiết bị riêng; người mua verify bằng điện thoại.
- Fingerprint chính ưu tiên **pattern gai/vỏ từ RGB**, không dựa vào LiDAR mesh làm nguồn chính.
- LiDAR/depth chỉ dùng phụ trợ: scale thô, pose, coarse shell, unwrap 2.5D.
- Verify người mua nên quét **một vùng nhỏ bất kỳ** thay vì full 360.
- Marker/QR là optional để tăng tốc hoặc quản lý dataset, không là bằng chứng chính.
- Search ưu tiên full-search về mặt sản phẩm, nhưng backend nên scope theo batch/time/market trước để giảm false positive.
- Dữ liệu gốc nên unwrap thành **atlas/map 2.5D** thay vì chỉ lưu ảnh rời.
- MVP lấy mẫu phải capture cả identity và grading ngay từ đầu vì quả đã bổ thì không phục hồi được.

## Rig MVP Hà Nội

Thiết kế tối thiểu để lấy mẫu repeatable:

- 2 phone quay đồng thời.
- `C1`: camera ngang nhìn thân quả; nếu có LiDAR thì dùng làm cam chính.
- `C2`: camera chéo trên khoảng 45 độ để thấy cuống, đỉnh, khe múi.
- Turntable làm bánh dùng được, dù quay không đều.
- Dán `zero marker` và 8-12 tick quanh viền mâm để estimate góc quay thật từ video.
- Lightbox/khung tản sáng bán kín.
- Nền xám matte trung tính.
- Khóa focus, exposure, white balance trước mỗi batch.
- Ưu tiên 4K/30fps; fallback 1080p/30fps nếu máy yếu, nóng, hoặc thiếu sáng.

Không nên dùng top camera 90 độ làm stream chính. Top chỉ nên là ảnh phụ cuống/đáy nếu cần.

## Calibration

Mục tiêu thực tế: repeatability khoảng **3-5 mm**, không cần 1 mm ở MVP.

Routine:

- Mỗi ngày: checkerboard/Charuco calibration đầy đủ hơn.
- Mỗi batch: quay ruler/scale object + marker mâm trong 2-3 giây đầu video.
- Đồng bộ 2 phone bằng flash hoặc clap lúc bắt đầu, sau đó dùng marker mâm để nội suy góc.

Nguồn scale chính nên là calibrated camera rig; LiDAR chỉ là phụ trợ.

## Sample ID Và Label

Nên mua máy in nhiệt label nếu đi field nhiều quả theo cây/vườn.

Label:

- In QR/DataMatrix + text readable.
- Dán cả túi/thùng và tag buộc quả để tránh mất dấu.
- Không dán trực tiếp lên quả nếu ảnh hưởng scan.
- Khi scan canonical: quay label 1-2 giây, tháo tag khỏi quả, rồi scan.

Format video:

```text
FARM-TREE-FRUIT-PASS-CAM
```

Ví dụ:

```text
DL01-T012-F003-A-C1
DL01-T012-F003-A-C2
DL01-T012-F003-B-C1
DL01-T012-F003-B-C2
```

Trong Excel, `fruit_id = DL01-T012-F003`.

## Taxonomy Mẫu

### Field receipt sample

Mẫu scan nhanh ở nơi mua/vườn, chất lượng thấp, dùng làm evidence/logistics.

Tối thiểu:

- video phone thô 15-30s,
- ảnh cuống,
- ảnh đáy,
- cân nặng nếu tiện.

Không cần lightbox, mesh, atlas.

### Canonical rig sample

Scan chính ở Hà Nội trước khi bổ, dùng cho identity và grading.

### Delayed destructive sample

Quả mua/ship về Hà Nội rồi mới bổ. Vẫn có ground truth sau bổ.

Nếu chỉ scan được một mốc, ưu tiên scan ngay trước khi bổ.

### Non-destructive sample

Scan/cân nhưng không bổ. Dùng cho identity, tracking, distribution shift; không dùng làm ground truth ruột.

## Protocol Mỗi Quả

### Trước khi bổ

1. Cân cả quả: `whole_fruit_weight`.
2. Ghi metadata tối thiểu.
3. Quay label bằng cả 2 phone.
4. Tháo tag khỏi quả nếu che bề mặt.
5. Scan pass A.
6. Lật/đổi tư thế scan pass B.
7. Optional pass C nếu vùng che còn nhiều.
8. Chụp ảnh phụ: cuống, đáy, 4 mặt nếu tiện.

Với 1 camera thì nên 3 pass, nhưng với 2 camera ngang + chéo, bắt đầu bằng 2 pass là đủ cho MVP.

### Sau khi bổ

1. Chụp mặt cắt toàn quả.
2. Chụp từng múi/segment.
3. Ghi `segment_count`.
4. Cân:
   - `shell_weight`,
   - `edible_flesh_weight`,
   - `seed_weight`.
5. Label từng múi:
   - đầy,
   - vừa,
   - lép,
   - hư/thối/sâu.

Nên có một mốc định hướng dataset, ví dụ chấm mực thực phẩm tại khe số 0 trước khi bổ. Khi bổ vẫn ghi thủ công theo thứ tự múi quanh cuống.

## Excel Master Tối Thiểu

Mỗi video/pass một row hoặc mỗi quả một row kèm links folder đều được. MVP nên bắt đầu đơn giản: mỗi video/pass một row, có chung `fruit_id`.

Các cột tối thiểu:

```text
sample_id
fruit_id
farm_id
tree_id
fruit_seq
pass
camera_id
capture_date
source_or_seller
location_note
status
whole_fruit_weight
shell_weight
edible_flesh_weight
seed_weight
segment_count
segment_labels
notes
```

`status` gợi ý:

```text
field_only
received
rig_scanned
opened_labeled
non_destructive
```

## App Stray Scanner

Repo: `/Users/jin/scanner`

Có thể dùng ngay cho MVP:

- Màn record có `Sample ID` editable.
- Folder video đặt theo Sample ID.
- `sample_metadata.json` link dataset với sample.
- Có export CSV/XLSX log, nhưng `.xlsx` hiện là TSV fallback mở được bằng Excel.

Khuyến nghị trước mắt:

- Chưa sửa app thành form sầu riêng.
- Encode metadata chính vào Sample ID.
- Excel master giữ toàn bộ field.
- Sửa app sau khi protocol lấy mẫu ổn định.

## Pipeline Sau Này

### Farm/packing registration

```text
multi-view RGB/depth coarse
-> fruit segmentation
-> coarse 3D shell
-> unwrap surface atlas 2.5D
-> detect gai/hom/texture keypoints
-> store descriptors + provenance
```

### Buyer verify

```text
phone scan 10-20s patch
-> reconstruct local patch/features
-> search scoped/global index
-> geometric consistency check
-> confidence: same fruit / uncertain / fail
```

### Quality grading

```text
outer scan + scale + weight
-> seam/khe detection
-> segment map
-> shape/fullness features
-> model predicts segment fullness, yield, ripeness, defects
-> evaluate against destructive ground truth subset
```

## Không Làm Ngay

- Không cố dựng TSDF mesh sắc gai làm fingerprint chính.
- Không phụ thuộc marker/QR để chứng minh đúng quả.
- Không dựng app/database riêng trước khi protocol ổn.
- Không cần motor turntable chính xác ngay; marker góc đủ cho MVP.
- Không cần multi-camera rig 4 camera ngay.

## Checklist Mua/Dựng MVP

- 2 phone.
- Tripod/mount chắc cho 2 phone.
- Turntable làm bánh.
- Decal marker/tick cho mâm.
- Đèn LED + vật liệu tản sáng/lightbox.
- Nền xám matte.
- Cân.
- Máy in nhiệt label + tem.
- Checkerboard/Charuco in giấy.
- Ruler/thanh đo scale.
- Excel master template.

