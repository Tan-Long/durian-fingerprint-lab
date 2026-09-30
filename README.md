# Dự Án Dấu Vân Sầu Riêng

Ghi chú riêng cho bản thử nghiệm quét sầu riêng, xác minh đúng quả và đánh giá chất lượng.

## Tài Liệu Chính

- [Bản thiết kế thử nghiệm sầu riêng](docs/durian-mvp-blueprint.md)
- [Quy trình xử lý mẫu sầu riêng](docs/durian-sample-processing-procedure.md)
- [Mô phỏng giao diện khảo sát sầu riêng](docs/mocks/durian-survey-preview.html)
- [Mô phỏng màn nhập mã mẫu khi quay](docs/mocks/recording-sample-id-layout.html)

## Tài Liệu Tham Chiếu Stray Scanner

- [Định dạng dữ liệu](docs/stray-scanner/format.md)
- [Cách xuất dữ liệu](docs/stray-scanner/export.md)
- [Thay đổi phần ảnh mẫu và file log](docs/stray-scanner/sample-photo-export.md)

## Hướng Hiện Tại

- Xác minh đúng quả bằng dấu vân tự nhiên trên vỏ: gai, hõm, khe, vân màu.
- LiDAR / đo sâu chỉ dùng phụ trợ cho dáng thô và tỷ lệ kích thước.
- Bộ quét thử nghiệm dùng 2 điện thoại: một máy ngang, một máy chéo trên 45 độ.
- Excel là nguồn dữ liệu chính cho tới khi quy trình lấy mẫu ổn định.

## Pilot Hai Bài Toán

Tiến độ, phạm vi và điều kiện kiểm chứng được giữ trong
[kế hoạch pilot](docs/plans/active/durian-two-track-pilot.md).

Lập chỉ mục từ manifest hiện có, không sao chép hay giải mã video:

```sh
python3 scripts/build_dataset_index.py \
  /Volumes/SoilTECH/DurianData/collections/202608_RIG_V1 \
  --output output/data-index
```

Kết quả gồm `samples.csv`, `media.csv` và `summary.json`. Mã mẫu, trạng thái QC
và checksum media được giữ từ manifest nguồn; chỉ mục kiểm tra file tồn tại,
không xác nhận nhãn hay đo độ chính xác nhận diện. `random_photo` có thể gồm ảnh
tem hoặc ảnh sau bổ, cần xem nội dung trước khi chọn ảnh truy vấn.

Chạy kiểm tra chỉ mục với Python chuẩn:

```sh
python3 -B -m unittest discover -s scripts -p 'test_build_dataset_index.py'
```

Đối soát nhãn Excel (cần `openpyxl` trong môi trường Python đang dùng):

```sh
python3 scripts/audit_morphology.py \
  "/Volumes/SoilTECH/Ảnh chụp sầu riêng/Chụp Hộc/SAMPLE_Fruit_morphology.xlsx" \
  --samples /Volumes/SoilTECH/DurianData/collections/202608_RIG_V1/manifests/samples.csv \
  --output output/morphology
```

`audit.json` giữ giá trị gốc, vị trí ô Excel và lỗi đối soát. Bảng
`sample_crosswalk.csv` nối mã collection với mã Excel khi khớp rõ ràng;
`valid` chỉ có nghĩa là qua các kiểm tra nhãn hiện có, chưa phải người duyệt.

Thử truy vấn ảnh với bank hai ngày quét (cần các thư viện trong
`test_video/requirements.txt` và ImageMagick; máy phát triển có môi trường
`test_video/.venv`):

```sh
test_video/.venv/bin/python test_video/query_multiview_banks.py \
  --image /path/to/phone-photo.jpg \
  --bank-root /Volumes/SoilTECH/DurianScan/27082026/processed_multiview_v1 \
  --bank-root /Volumes/SoilTECH/DurianScan/28082026/processed_multiview_v1
```

Lệnh trả JSON ra stdout, dùng bộ mã hóa riêng của từng bank root và chỉ xét
phiên `READY`. Điểm khớp là bằng chứng thử nghiệm chưa hiệu chuẩn; kết quả
`identity_verdict` vẫn là `null`. Chữ viết, tem và nền có thể ảnh hưởng matcher.

Kiểm tra các công cụ dữ liệu và matcher:

```sh
python3 -B -m unittest discover -s scripts -p 'test_*.py'
test_video/.venv/bin/python -B -m unittest discover -s test_video -p 'test_*.py'
test_video/.venv/bin/python -B -m unittest prototypes.durian_2d_projection.test_spike_graph
```
