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

`fruit_ranking` gom theo chuỗi `sample_id` được ghi trong bank, chọn bằng chứng
hình học tốt nhất và giữ chỉ mục các dòng hỗ trợ trong `candidates`. Nhiều
camera/phiên không tự cộng điểm; trùng chuỗi mã chưa chứng minh cùng một quả
giữa các collection. Thứ tự khi bằng điểm chỉ để kết quả ổn định.

Truy vấn theo lô: thay `--image` bằng `--batch /path/to/queries.json`, giữ các
tham số `--bank-root`. Nội dung file:

```json
[
  {"query_id": "phone-1", "image": "phone-1.jpg"},
  {"query_id": "phone-2", "image": "phone-2.HEIC"}
]
```

Đường dẫn tương đối tính từ thư mục chứa JSON; mã truy vấn phải duy nhất.
Kết quả từng ảnh gồm bằng chứng hoặc lỗi và thời gian chạy. Lỗi một ảnh không
làm mất kết quả các ảnh khác; mã thoát là `2` nếu có lỗi. Đây chưa phải bộ đo
độ chính xác trên tập kiểm thử đã duyệt.

Baseline hộc/múi/vỏ dùng Python chuẩn, không đọc Excel hay tự chọn tập train/test:

```sh
python3 -B scripts/morphology_baseline.py --help
python3 -B scripts/morphology_baseline.py /path/to/reviewed-fruits.json \
  --output /path/to/new-baseline-result.json
```

Schema JSON có trong `--help`: `feature_definitions` khai báo thời điểm đo trước
khi bổ cùng người xác nhận/bằng chứng; mỗi phần tử `fruits` là một quả duy nhất,
có `fruit_id`, `split`, `features` và nhãn từng target với người duyệt/bằng chứng.
Target hỗ trợ: `locule_count`, `aril_count`, `shell_thickness_mm` (đơn vị mm).
Phải tự giải quyết các mã khác nhau nhưng cùng một quả trước khi nhập.

Code lấy **trung vị nhãn train** làm dự đoán cố định, trả MAE/RMSE/bias trên test.
Các feature được kiểm tra nhưng **chưa dùng để dự đoán**; đây là mốc đối chiếu,
không phải mô hình học từ ảnh. Nhãn thiếu/sai/chưa duyệt chặn riêng target đó,
không tự bỏ hàng. Trùng quả giữa các tập hoặc feature không xác nhận đo trước
khi bổ sẽ bị từ chối. Không ghi đè file có sẵn; mã thoát `0` khi chạy đủ,
`1` khi lỗi đầu vào/IO, `2` khi có target bị chặn nhưng vẫn lưu kết quả còn lại.
Chỉ kiểm thử bằng dữ liệu giả lập ở bước này; `valid` trong audit không phải
nhãn đã duyệt và kết quả chạy không tự cấp PASS.

Kiểm tra các công cụ dữ liệu và matcher:

```sh
python3 -B -m unittest discover -s scripts -p 'test_*.py'
test_video/.venv/bin/python -B -m unittest discover -s test_video -p 'test_*.py'
test_video/.venv/bin/python -B -m unittest prototypes.durian_2d_projection.test_spike_graph
```

## Duyệt Kết Quả Code Trên Máy

### Mẫu Thực Hai Nguồn RGB + LiDAR: N1V10C3

Demo hiện tại dùng `CAM_TREN` và `CAM_DUOI` của session
`28082026/N1V10C3/20260828-124510-e9f5`. Mỗi camera đọc RGB, depth,
confidence và thời gian **đúng frame**. Chỉ dùng 36 chỉ số frame/camera từ bank;
trích SIFT mới, không dùng lại descriptor bank hoặc hợp nhất pose hai thiết bị.

```sh
test_video/.venv/bin/python -B scripts/build_rgbd_sample_review.py \
  --image '/Volumes/SoilTECH/Ảnh chụp sầu riêng/DA_SAP_XEP_28082026/N1V10C3/004__IMG_4171.HEIC' \
  --session-dir /Volumes/SoilTECH/DurianScan/28082026/N1V10C3/20260828-124510-e9f5 \
  --bank-session-dir /Volumes/SoilTECH/DurianScan/28082026/processed_multiview_v1/samples/N1V10C3/20260828-124510-e9f5 \
  --output-dir output/rgbd-N1V10C3-review
```

Kết quả thực: cả 72 frame có 0 inlier hình học. Frame hiển thị 82/80 là
chọn theo thứ tự khi đồng hạng, **chưa khớp thành công**. Truy vấn bank riêng
cũng không có N1V10C3 trong top 3; giữ nguyên kết quả thất bại để duyệt.
Lớp RGB/depth/confidence/mask/rãnh/gai là dữ liệu bề mặt. Độ sâu tới camera
không phải độ dày vỏ. Chưa có mô hình dự đoán hộc/múi bên trong.

Bộ lắp ghép dùng kết quả truy vấn bank bên dưới và hồ sơ chọn mẫu đã đối soát
cục bộ (`output/sample-selection/N1V10C3.json`, không tự tạo/đoán hồ sơ này):

```sh
python3 -B scripts/assemble_sample_demo.py \
  --alignment-pack output/rgbd-N1V10C3-review/pack.json \
  --retrieval-pack output/n1v10c3-real-demo/pack.json \
  --sample-evidence output/sample-selection/N1V10C3.json \
  --output output/n1v10c3-demo-pack-v2.json
python3 -B scripts/serve_label_review.py \
  --pack output/n1v10c3-demo-pack-v2.json \
  --state-dir output/n1v10c3-review-state \
  --media-root output/rgbd-N1V10C3-review \
  --media-root output/n1v10c3-real-demo \
  --media-root /Volumes/SoilTECH --port 8772
```

Mở <http://127.0.0.1:8772/>: đổi lớp dưới từng camera, bấm ảnh để zoom;
ca thứ hai có thẻ mã và đủ H1–H5, Excel 5 hộc/10 múi/20 mm chỉ là đối chứng;
ca thứ ba giữ kết quả tìm mã sai. Chọn trạng thái, ghi comment và lưu.
Đọc lại bằng `curl -fsS http://127.0.0.1:8772/api/export`.
Khởi động lại chỉ chạy server với nguyên pack/state. Tạo bộ mới phải dùng
tên output mới; không ghi đè nguồn, pack hoặc phản hồi cũ. State phải nằm ngoài
mọi media-root. Kiểm thử ghi phản hồi dùng cùng pack, cổng 8773 và state riêng
`output/n1v10c3-browser-test-state`; không dùng state của người duyệt.

### Demo Ảnh Thật: Ảnh Chụp Và Frame Khớp

Chọn ảnh chụp độc lập có mã mẫu đã đối chiếu trước khi chạy. Lệnh chỉ đọc bank
hiện có, trích đúng frame ứng viên và vẽ các cặp điểm khớp; không train lại:

```sh
test_video/.venv/bin/python -B scripts/build_fingerprint_visual_review.py \
  --image /path/to/verified-independent-phone-photo.jpg \
  --bank-root /Volumes/SoilTECH/DurianScan/27082026/processed_multiview_v1 \
  --bank-root /Volumes/SoilTECH/DurianScan/28082026/processed_multiview_v1 \
  --output-dir output/fingerprint-real-review
python3 -B scripts/serve_label_review.py --pack output/fingerprint-real-review/pack.json \
  --state-dir output/fingerprint-real-review-state \
  --media-root output/fingerprint-real-review --port 8772
```

Thư mục output phải mới. Mở <http://127.0.0.1:8772/> để xem ảnh đầu vào, frame
của ba ứng viên và hình nối điểm; bấm ảnh để phóng to/cuộn. Chỉ số khớp không
phải xác suất đúng quả. Chữ/tem/nền có thể gây khớp sai. Hộc/múi/vỏ chưa có
mô hình tạo lớp phân vùng; không hiển thị số giả lập như dự đoán trên ảnh thật.
Phản hồi lưu ở state riêng, không ghi đè phản hồi của các trang duyệt trước.

### Trang Kiểm Thử Chức Năng (Giả Lập, Không Phải Demo Nhận Diện)

Trang cũ cho hai kết quả kiểm thử, không dùng/chỉnh sửa ảnh hoặc nhãn thật:

```sh
mkdir -p output/core-review
test_video/.venv/bin/python -B scripts/build_core_review.py --output output/core-review/pack.json
python3 -B scripts/serve_label_review.py --pack output/core-review/pack.json \
  --state-dir output/core-review/state --media-root scripts --port 8770
```

Mở <http://127.0.0.1:8770/>. Chọn phần code, xem bảng kết quả/JSON, chọn duyệt
hoặc cần sửa và ghi comment rồi lưu. Phản hồi nằm trong
`output/core-review/state/decisions.sqlite3`; đọc lại qua `/api/review` hoặc xuất
`/api/export`. Duyệt chỉ áp dụng cho phần code/snapshot đang xem, không duyệt nhãn
hay chứng nhận độ chính xác. Khởi động lại dùng nguyên pack/state để giữ lịch sử;
builder từ chối ghi đè pack có sẵn. Muốn tạo snapshot mới, dùng tên file mới.

Trang tái dùng giao diện và server duyệt nhãn, ẩn phần ảnh trong chế độ code.
Kiểm tra trình duyệt ảnh thật: `scripts/check_core_review_browser.js` dùng pack
ảnh thật nhưng server cổng `8773` và state **riêng** ngoài thư mục media;
không chạy kiểm tra ghi phản hồi trên state người dùng.

## Duyệt Nhãn Trên Máy

Gắn ổ `SoilTECH`, chạy chỉ mục và đối soát ở trên trước. Tạo bộ duyệt riêng
(chỉ đọc dữ liệu nguồn; không sửa Excel):

```sh
python3 -B scripts/build_label_review.py \
  --audit output/morphology/audit.json \
  --media-index output/data-index/media.csv \
  --index-summary output/data-index/summary.json \
  --chamber-manifest '/Volumes/SoilTECH/Ảnh chụp sầu riêng/Chụp Hộc/BANG_KE_HOC.csv' \
  --preview-root /Volumes/SoilTECH/DurianScan/27082026/processed_multiview_v1 \
  --preview-root /Volumes/SoilTECH/DurianScan/28082026/processed_multiview_v1 \
  --observations docs/plans/evidence/durian-two-track-pilot/label-review-observations.json \
  --output output/label-review/pack-all-chambers.json
python3 -B scripts/serve_label_review.py \
  --pack output/label-review/pack-all-chambers.json \
  --state-dir output/label-review/state \
  --media-root /Volumes/SoilTECH --port 8765
```

Cần Python chuẩn và ImageMagick (`magick`, hỗ trợ HEIC). Mở
<http://127.0.0.1:8765/> trên máy này. Chọn mã trái, xem toàn bộ ảnh hộc ứng viên,
ảnh đối chiếu mã và dữ liệu ô Excel. Kho ảnh hộc giữ cả ảnh chưa đọc được mã;
không tự gán ảnh bên cạnh hoặc coi số ảnh là số hộc. Có nút ảnh trước/sau,
phóng to, vừa khung; ảnh phóng lớn cuộn/kéo được.

Chọn trạng thái, ghi kết luận/căn cứ rồi bấm **Lưu phản hồi**. Bản nháp chưa
lưu chỉ nằm trong tab. Phản hồi lưu nối tiếp tại
`output/label-review/state/decisions.sqlite3`, không thay đổi nhãn nguồn hoặc
cấp PASS cho mô hình. Điều phối viên đọc lại bằng nút **Xuất phản hồi** hoặc:

```sh
curl -fsS http://127.0.0.1:8765/api/export
```

Giữ lại file pack cũ và thư mục state khi đổi bộ bằng chứng. Máy chủ đọc pack
khi khởi động; dùng tên file mới rồi khởi động lại để chuyển bộ. Phản hồi gắn
với hash của pack, không tự chuyển duyệt sang bộ mới. SQLite vẫn giữ lịch sử
các bộ cũ; API chỉ xuất bộ đang chạy. Sao lưu DB khi máy chủ đã dừng.

Kiểm tra giao diện đọc-only: chạy `scripts/check_label_review_browser.js` bằng
công cụ Playwright `browser_run_code_unsafe` với `filename` là đường dẫn tuyệt
đối. Check dùng context riêng, không gửi phản hồi; bộ mẫu hiện tại cần kho
427 ảnh. Kiểm thử ghi phản hồi phải dùng state/port riêng, không dùng state
duyệt thật. Dừng máy chủ bằng Ctrl-C; ảnh nguồn không bị thay đổi.

### Sắp xếp ảnh hộc theo nhãn quả

`scripts/organize_chamber_photos.py` tạo bản sao theo mã đọc trực tiếp trên ảnh,
không di chuyển ảnh gốc hoặc dùng mã gần nhất từ OCR cũ. Bước chuẩn bị cần máy
chủ duyệt ở cổng 8765 với toàn bộ ảnh hộc và ImageMagick trên macOS:

```sh
python3 -B -m scripts.organize_chamber_photos prepare \
  --source '/Volumes/SoilTECH/Ảnh chụp sầu riêng/Chụp Hộc' \
  --output output/chamber-sort-review
```

Kiểm tra ảnh/nhãn trong các bảng ảnh; ghi kết quả riêng cho **từng ảnh** dưới
dạng JSON `{đường_dẫn_tương_đối: {fruit_id, locule, status, note}}`.
`status` là `visual_read`, `unclear` hoặc `not_labelled`. Không rõ mã thì
`fruit_id: null`; không lấy mã từ ảnh bên cạnh. BONUS phải giữ riêng.
Sau khi tất cả ảnh có kết quả đọc, sao chép tới một thư mục **chưa tồn tại**:

```sh
python3 -B -m scripts.organize_chamber_photos copy \
  --inventory output/chamber-sort-review/inventory.json \
  --reviews output/chamber-sort-review/root.json \
    output/chamber-sort-review/morphology.json output/chamber-sort-review/fingerprint.json \
  --destination '/Volumes/SoilTECH/Ảnh chụp sầu riêng/Hoc_theo_nhan_qua_20260930'
```

Bộ mới giữ cấu trúc `N1V1C1/n1v1c1_h1.jpg`, không có cấp thư mục máy chụp.
Giữ nguyên định dạng ảnh; trùng nhãn dùng `_02`, `_03`...; chưa rõ hộc dùng
`h_chua_ro`. Ảnh chưa rõ mã quả dùng tên file nguồn viết thường trong nhóm
chưa rõ/không có nhãn.
Tên file và máy chụp gốc vẫn có trong `DOI_CHIEU_ANH.csv/json`.
SHA-256 được đối chiếu trước/sau sao chép;
không ghi đè thư mục cũ. Nếu lỗi giữa chừng, giữ bộ dở để kiểm tra và dùng đích
mới khi chạy lại. Đây là phân nhóm theo nhãn nhìn thấy, **chưa phải người dùng
duyệt nhãn hay xác nhận số hộc/múi**. Kiểm thử:
`python3 -B -m unittest scripts.test_organize_chamber_photos -v`.
