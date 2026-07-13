# Quy Trình Xử Lý Mẫu Sầu Riêng

Tài liệu này dùng cho bản thử nghiệm lấy dữ liệu sầu riêng: quét dấu vân vỏ, ghi thông tin mẫu, bổ quả và lấy dữ liệu kiểm chứng thật.

## Mục Tiêu Mỗi Mẫu

Mỗi quả sau khi xử lý phải có đủ:

- mã `fruit_id` duy nhất,
- video quét từ 2 camera cho ít nhất 2 lượt,
- ảnh phụ cuống/đáy/4 mặt nếu tiện,
- cân nặng cả quả,
- grade thương mại nếu có,
- dữ liệu sau khi bổ: số múi, nhãn múi, cân vỏ, cân cơm, cân hạt.

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
- Bảng caro/Charuco.
- Tem QR/DataMatrix hoặc dây buộc mã mẫu.
- Dao, thớt, khay đựng cơm/hạt/vỏ.
- Găng tay, khăn lau, túi rác.
- File Excel/log mẫu.

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

## Cột Excel Tối Thiểu

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
commercial_grade
grade_reason
whole_fruit_weight
shell_weight
edible_flesh_weight
seed_weight
segment_count
segment_labels
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
4. Sao lưu video và ảnh sang ổ khác hoặc cloud.
5. Xuất CSV/XLSX log.
6. Ghi lại lỗi quy trình để buổi sau sửa.

## Không Làm Trong Bản Thử Nghiệm

- Không dựng database riêng trước khi Excel/log ổn.
- Không sửa app thành form sầu riêng nếu quy trình lấy mẫu còn đổi.
- Không phụ thuộc QR làm bằng chứng đúng quả.
- Không cố dựng mô hình 3D gai thật chi tiết.
- Không mua thêm camera/motor nếu 2 điện thoại + mốc góc đã đủ lấy dữ liệu ổn.
