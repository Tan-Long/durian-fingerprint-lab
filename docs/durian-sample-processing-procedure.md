# Quy Trình Xử Lý Mẫu Sầu Riêng

Tài liệu này dùng cho bản thử nghiệm lấy dữ liệu sầu riêng: quét dấu vân vỏ, ghi thông tin mẫu, bổ quả và lấy dữ liệu kiểm chứng thật.

## Mục Tiêu Mỗi Mẫu

Mỗi quả sau khi xử lý phải có đủ:

- mã `fruit_id` duy nhất,
- video quét từ 2 camera cho ít nhất 2 lượt,
- ảnh phụ cuống/đáy/4 mặt nếu tiện,
- cân nặng cả quả,
- grade thương mại nếu có,
- dữ liệu cây: chiều cao và độ rộng tán, tách rõ số app ước lượng với số đo đối chứng,
- dữ liệu sau khi bổ: số múi, nhãn múi, cân vỏ, cân cơm, cân hạt, độ Brix và hàm lượng chất khô.

## Chuẩn Bị Trước Buổi Lấy Mẫu

Thiết bị tối thiểu:

- 2 điện thoại quay video.
- 2 chân đỡ/kẹp điện thoại chắc.
- Mâm xoay làm bánh.
- Hộp sáng hoặc khung tản sáng bán kín.
- Nền xám matte.
- Đèn LED ổn định.
- Cân.
- Thước đo.
- Thước dây/laser đo khoảng cách và máy đo góc hoặc máy đo cao cây để lấy số đối chứng.
- Bảng caro/Charuco.
- Tem QR/DataMatrix hoặc dây buộc mã mẫu.
- Dao, thớt, khay đựng cơm/hạt/vỏ.
- Găng tay, khăn lau, túi rác.
- File Excel/log mẫu.

Thiết bị phòng đo cho mẫu sau khi bổ:

- Khúc xạ kế điện tử đo `°Brix`, nước cất và giấy lau mềm.
- Cân tối thiểu chính xác `0,01 g`, đĩa/cốc sấy, tủ sấy `70°C` và bình hút ẩm.

Trước khi bắt đầu:

1. Sạc pin 2 điện thoại, dọn đủ bộ nhớ.
2. Lau sạch nền, mâm xoay, thước và cân.
3. Tạo danh sách mã quả dự kiến.
4. In hoặc viết tem mã mẫu.
5. Kiểm tra cân về `0`.

## Setup Khung Rig

1. Đặt mâm xoay ở giữa hộp sáng/khung tản sáng.
2. Dán một mốc `zero` rõ trên viền mâm.
3. Dán thêm 8-12 vạch quanh viền mâm để ước lượng góc quay.
4. Đặt nền xám matte sau và dưới quả.
5. Đặt thước đo hoặc vật chuẩn kích thước trong khung hình ở 2-3 giây đầu mỗi lượt.
6. Bật đèn LED, tránh bóng gắt và vùng cháy sáng trên gai.
7. Cố định toàn bộ chân máy; sau khi hiệu chuẩn không dịch camera nếu không cần.

Mục tiêu bản thử nghiệm là quét lặp lại sai lệch khoảng 3-5 mm. Không cần motor mâm xoay chính xác ngay.

## Setup 2 Camera

Camera `C1`:

- đặt ngang thân quả,
- thấy rõ vùng giữa thân, gai, khe múi,
- dùng làm góc chính.

Camera `C2`:

- đặt chéo trên khoảng 45 độ,
- thấy cuống, đỉnh quả và khe chạy từ cuống xuống thân,
- tránh góc thẳng đứng 90 độ làm video chính.

Cài đặt cả 2 máy:

- ưu tiên 4K/30fps,
- dùng 1080p/30fps nếu máy nóng, thiếu sáng hoặc thiếu bộ nhớ,
- khóa nét,
- khóa sáng,
- khóa cân bằng trắng,
- không dùng filter làm đẹp/màu.

Đồng bộ:

1. Bấm quay cả 2 máy.
2. Quay tem/mã mẫu 1-2 giây.
3. Nháy đèn hoặc vỗ tay một lần để tạo mốc đồng bộ.
4. Quay thước đo + mốc `zero` 2-3 giây.
5. Bắt đầu xoay mâm.

## Quy Ước Mã Và File

Mã quả:

```text
FARM-TREE-FRUIT
```

Mã video:

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

Trong Excel:

- `fruit_id`: `DL01-T012-F003`
- `sample_id`: `DL01-T012-F003-A-C1`
- `pass`: `A`, `B`, `C`
- `camera_id`: `C1`, `C2`

## Quy Trình Trước Khi Quét

Với từng quả:

1. Gán hoặc kiểm tra `fruit_id`.
2. Dán tem lên dây buộc/túi/thùng, không dán lên vùng vỏ cần quét.
3. Chụp/quay mã mẫu.
4. Cân cả quả, ghi `whole_fruit_weight`.
5. Ghi nguồn: vườn, cây, người bán, ngày nhận, ghi chú vận chuyển.
6. Ghi `commercial_grade` nếu có: `A`, `B`, `offgrade`.
7. Ghi `grade_reason`: tròn, kích thước, 2.7 múi to, 2.5 múi, kem, đồ, lỗi khác.
8. Quan sát nhanh lỗi ngoài vỏ: nứt, dập, sâu, gai gãy nhiều, mốc.

## Đo Chiều Cao Cây Và Độ Rộng Tán

App hiện đã có luồng đo bằng ARKit/LiDAR, nhưng phản hồi của nhóm lấy mẫu cho thấy kết quả chưa đúng. Vì vậy số từ app chỉ là `app_estimate`, chưa được dùng làm ground truth cho tới khi vượt qua đo đối chứng ngoài hiện trường.

Với mỗi `tree_id`:

1. Ghi GPS, ngày giờ, người đo, thiết bị và chụp một ảnh toàn cây có thấy gốc/ngọn.
2. Dùng app đo 3 lần từ cùng vị trí; ghi từng lần, không chỉ ghi số trung bình.
3. Đo chiều cao đối chứng bằng máy đo cao/laser. Nếu không có, đo khoảng cách ngang `D` từ máy tới gốc và góc có dấu tới ngọn `α_top`, tới gốc `α_base`, rồi tính:

```text
tree_height_ref_m = D * (tan(α_top) - tan(α_base))
```

4. Đo tán trên mặt đất theo hai đường kính: `D1` là hướng rộng nhất, `D2` vuông góc với `D1`. Ghi cả hai và tính:

```text
canopy_width_ref_m = (D1 + D2) / 2
```

5. Khi so với app, đứng theo đúng hướng `D1`, ghi hướng chụp và so `canopy_width_app_m` với `canopy_d1_ref_m`.
6. Lặp đo đối chứng ít nhất 2 lần nếu gốc/ngọn bị che, nền dốc hoặc mép tán không rõ; ghi cờ QC thay vì tự sửa số.

Pilot kiểm định tối thiểu 20 cây, trải đều cây thấp/cao và tán hẹp/rộng. Báo cáo `bias`, `MAE`, `MAPE` và độ lặp lại của 3 lần đo app. Trước khi có báo cáo này, đặt:

```text
tree_measurement_status = ESTIMATE_UNVERIFIED
```

## Cách Quay Mỗi Quả

### Lượt A

1. Đặt quả ở tư thế ổn định nhất trên mâm.
2. Đảm bảo dây tem không che vùng vỏ chính.
3. Bấm quay `C1` và `C2`.
4. Quay mã mẫu, nháy đèn/vỗ tay, quay thước và mốc `zero`.
5. Xoay mâm đủ 360 độ trong 15-30 giây.
6. Tốc độ xoay đều tay, không dừng giật.
7. Dừng quay sau khi mốc `zero` quay lại gần vị trí ban đầu.

### Lượt B

1. Lật hoặc đổi tư thế quả để lộ vùng bị che ở lượt A.
2. Tạo `sample_id` mới với `pass = B`.
3. Lặp lại đúng quy trình quay như lượt A.

### Lượt C

Chỉ quay lượt C nếu sau A/B vẫn còn vùng bị che nhiều, quả lăn khó ổn định, hoặc dữ liệu A/B bị rung/mờ.

## Ảnh Phụ

Sau video, chụp nhanh:

- cuống,
- đáy,
- 4 mặt quanh thân,
- vùng lỗi rõ nếu có.

Ảnh phụ không thay video quét. Chỉ dùng để kiểm tra lại nhãn và lỗi ngoài vỏ.

## Kiểm Tra Nhanh Sau Khi Quét

Trước khi chuyển sang quả tiếp theo:

1. Mở thử mỗi video 3-5 giây.
2. Kiểm tra có thấy mã mẫu.
3. Kiểm tra có thấy mốc `zero` và thước đo.
4. Kiểm tra quả không bị mất nét/cháy sáng quá nhiều.
5. Kiểm tra tên file đúng `sample_id`.
6. Ghi chú nếu phải quay lại.

Nếu sai mã mẫu hoặc video mờ nặng, quay lại ngay. Đừng chờ tới cuối buổi.

## Bổ Mẫu Và Ghi Dữ Liệu Thật

Chỉ bổ sau khi đã quét xong các lượt cần thiết.

1. Chụp ảnh quả trước khi bổ.
2. Đánh dấu khe số `0` bằng mực thực phẩm hoặc ghi rõ mốc định hướng.
3. Bổ quả theo cách giữ được thứ tự các múi quanh cuống.
4. Chụp mặt cắt toàn quả.
5. Chụp từng múi/khoang.
6. Ghi `segment_count`.
7. Ghi `segment_labels` theo thứ tự quanh cuống: đầy, vừa, lép, hư/thối/sâu.
8. Tách và cân:
   - `shell_weight`,
   - `edible_flesh_weight`,
   - `seed_weight`.
9. Ghi chú mùi, độ chín, cơm nhão/khô, sâu bệnh nếu có.
10. Chụp cân nếu cần đối soát sau.

Không trộn cơm/hạt/vỏ giữa các quả trước khi cân xong.

## Đo Brix Và Hàm Lượng Chất Khô

Phần này thực hiện ở đợt lấy mẫu sau, ngay sau khi bổ. Với dữ liệu cũ, nếu không còn cơm quả được lưu riêng theo đúng `fruit_id` thì ghi `not_measured`; không suy ra Brix/chất khô từ ảnh. Mẫu đông lạnh, nếu có, phải ghi điều kiện lưu và phân tích thành nhóm riêng, không trộn với mẫu tươi.

Chuẩn bị một mẫu cơm đại diện lấy từ ít nhất 2 hộc, trộn đồng nhất rồi chia cho hai phép đo.

### Độ Brix

1. Zero khúc xạ kế bằng nước cất và lau khô.
2. Ép/lọc mẫu đồng nhất, nhỏ 2-3 giọt lên lăng kính.
3. Đo 3 lần, vệ sinh lăng kính giữa các mẫu và lưu `brix_rep1`, `brix_rep2`, `brix_rep3`, `brix_mean`.
4. Nếu cơm quá đặc phải pha loãng, khóa một tỷ lệ cho toàn pilot và ghi khối lượng cơm/nước. Kết quả hiệu chỉnh:

```text
brix_corrected = brix_reading * (pulp_mass + water_mass) / pulp_mass
```

`°Brix` là chỉ số chất rắn hòa tan, không được ghi thành “% đường chính xác”.

### Hàm lượng chất khô

Làm 2 mẫu lặp, mỗi mẫu khoảng 10-20 g:

1. Cân đĩa rỗng: `m0`.
2. Cân đĩa + mẫu tươi: `m1`.
3. Sấy ở `70°C` trong 48 giờ, làm nguội trong bình hút ẩm rồi cân. Sấy thêm từng 2-4 giờ tới khi khối lượng thay đổi dưới `0,01 g`: `m2`.
4. Tính:

```text
dry_matter_pct = (m2 - m0) / (m1 - m0) * 100
moisture_pct = 100 - dry_matter_pct
```

Giữ nguyên một nhiệt độ, thời gian, khối lượng mẫu và cách lấy mẫu trong toàn pilot.

## Cột Excel Tối Thiểu

```text
sample_id
fruit_id
farm_id
tree_id
fruit_seq
tree_height_app_rep1_m
tree_height_app_rep2_m
tree_height_app_rep3_m
tree_height_ref_m
canopy_width_app_m
canopy_d1_ref_m
canopy_d2_ref_m
canopy_width_ref_m
tree_measurement_status
pass
camera_id
capture_date
source_or_seller
location_note
status
commercial_grade
grade_reason
whole_fruit_weight
shell_weight
edible_flesh_weight
seed_weight
segment_count
segment_labels
brix_rep1
brix_rep2
brix_rep3
brix_mean
brix_pulp_mass_g
brix_water_mass_g
dry_matter_rep1_pct
dry_matter_rep2_pct
dry_matter_mean_pct
quality_measurement_status
notes
```

`status` dùng một trong các giá trị:

```text
field_only
received
rig_scanned
opened_labeled
non_destructive
```

## Checklist Kết Thúc Buổi

1. Đếm số quả thực tế và số dòng Excel.
2. Kiểm tra mỗi `fruit_id` có đủ video `A-C1`, `A-C2`, `B-C1`, `B-C2` nếu quét đủ 2 lượt.
3. Kiểm tra quả đã bổ có đủ cân vỏ/cơm/hạt.
4. Kiểm tra mỗi cây có số app lặp lại và số đo đối chứng; số app chưa kiểm định phải mang trạng thái `ESTIMATE_UNVERIFIED`.
5. Kiểm tra quả đo chất lượng có đủ 3 lần Brix và 2 mẫu chất khô, hoặc ghi rõ `not_measured`.
6. Sao lưu video và ảnh sang ổ khác hoặc cloud.
7. Xuất CSV/XLSX log.
8. Ghi lại lỗi quy trình để buổi sau sửa.

## Không Làm Trong Bản Thử Nghiệm

- Không dựng database riêng trước khi Excel/log ổn.
- Không sửa app thành form sầu riêng nếu quy trình lấy mẫu còn đổi.
- Không phụ thuộc QR làm bằng chứng đúng quả.
- Không cố dựng mô hình 3D gai thật chi tiết.
- Không mua thêm camera/motor nếu 2 điện thoại + mốc góc đã đủ lấy dữ liệu ổn.
