# Quy trình dàn ảnh thân quả sầu riêng hiện tại

## Phạm vi

Pipeline hiện tại chỉ tạo **ảnh RGB dàn phẳng 360° của phần thân giữa quả** từ video quả quay trên bàn xoay. Chế độ này chưa nhận diện chân gai, đỉnh gai, chưa tạo fingerprint và chưa so khớp ảnh người mua.

Đầu và đít quả đang bị loại khỏi map vì video hiện tại chủ yếu quay ngang và mô hình chiếu đang coi thân quả gần giống một hình trụ.

## Đầu vào

Pipeline đọc dữ liệu tại:

```text
test_video/CAM-TURNTABLE-01/
├── rgb.mp4
└── depth/*.png
```

- `rgb.mp4`: video màu 1920 × 1440, 60 fps.
- `depth/*.png`: depth đồng bộ theo frame, dùng để tách quả khỏi nền.
- Pipeline lấy 48 frame RGB ở độ phân giải xử lý 960 × 720.
- Chỉ lấy khoảng 2%–98% thời lượng để bỏ phần đầu và cuối lúc bắt đầu/dừng quay.

## Luồng xử lý

```text
RGB video + depth
        ↓
Lấy mẫu 48 frame đồng bộ
        ↓
Tạo mask quả bằng depth + màu
        ↓
Ước lượng trục quay và bán kính thân theo từng vị trí dọc quả
        ↓
Apple Vision đo chuyển động giữa các frame
        ↓
Chọn đoạn gần đúng một vòng 360°
        ↓
Gán lại góc đều theo tốc độ bàn xoay
        ↓
Chiếu ngược từng pixel của map về frame RGB
        ↓
Tìm seam động ở vùng frame chồng nhau
        ↓
Cắt lấy phần thân giữa và ghi PNG
```

### 1. Lấy mẫu RGB và depth

`project.decode_frames()` dùng FFmpeg để lấy mẫu đều theo thời gian, scale ảnh về 960 × 720 và giữ đúng tỉ lệ. Frame depth tương ứng được chọn theo cùng vị trí thời gian.

### 2. Tạo mask quả

`registration_mask()` kết hợp hai điều kiện:

- Depth nằm trong khoảng gần bề mặt quả tại vùng trung tâm.
- Màu RGB có đặc trưng xanh/vàng của vỏ sầu riêng.

Sau đó pipeline đóng các lỗ nhỏ và chỉ giữ thành phần liên thông lớn gần tâm ảnh. Mask này loại phần lớn nền và bàn xoay.

### 3. Ước lượng hình thân quả

`rotation_profile()` tính:

- `axis_y`: trục quay ngang chung, lấy trung vị tâm mask của các frame.
- `radius[x]`: bán kính biểu kiến của quả tại từng vị trí dọc thân.
- Vùng thân dùng để dàn: các cột có bán kính ít nhất bằng 70% bán kính lớn nhất.

Vì vậy map hiện tại cố ý bỏ phần thân thuôn mạnh ở đầu và đít quả.

### 4. Xác định một vòng quay

Mỗi frame được chuyển thành ảnh chi tiết xám, lọc nền tần số thấp và áp cửa sổ Hanning. Apple Vision đo dịch chuyển dọc giữa hai frame liên tiếp.

Các dịch chuyển sai hướng hoặc lớn hơn 20° bị thay bằng giá trị lân cận. Chuỗi đo này chỉ dùng để tìm frame kết thúc gần 360° nhất.

Sau khi chọn đúng số frame cho một vòng, góc được gán lại đều từ 0° đến 360° vì bàn xoay hiện được giả định chạy với tốc độ không đổi. Việc này đã loại lỗi một vùng hoặc một gai bị ghi hai lần do bước góc đo được từng nhảy từ khoảng 1° đến 17°.

### 5. Chiếu ngược RGB sang map

Map có:

- Chiều cao bằng chiều dài vùng thân đã chọn.
- Chiều rộng xấp xỉ chu vi lớn nhất của thân: `2π × radius_max`, tối thiểu 720 px.

Mỗi frame chỉ đóng góp vùng nhìn gần chính diện trong khoảng `±12°`. Với từng pixel đích trên map, pipeline tính ngược vị trí cần lấy trong frame nguồn:

```text
source_y = axis_y - radius[x] × sin(longitude_offset)
```

RGB được nội suy song tuyến tính; mask dùng nội suy nearest-neighbor. Cách chiếu ngược này thay cho cách rải pixel cũ, tránh cột trống, sọc lặp và việc tự lấp pixel làm nhòe gai.

### 6. Nối các frame bằng seam động

Ở vùng hai frame chồng nhau:

1. Tính sai khác màu trung bình tại từng pixel.
2. Dùng dynamic programming tìm một đường seam từ trên xuống dưới có tổng sai khác thấp nhất; mỗi bước chỉ lệch trái, đứng yên hoặc lệch phải một pixel.
3. Phía trái seam giữ frame cũ, phía phải lấy frame mới.

Mỗi pixel chỉ đến từ **một frame**; pipeline không alpha-blend và không lấy trung bình hai frame. Các lỗ còn lại rộng tối đa 3 px mới được lấp bằng pixel hợp lệ gần nhất.

## Cách chạy

Từ thư mục dự án:

```bash
python3 prototypes/durian_2d_projection/video_spike_pattern.py test_video --unwrap-only
```

Kiểm tra logic:

```bash
python3 -m unittest prototypes.durian_2d_projection.test_spike_graph
```

## File đầu ra

```text
test_video/processed/video-body-unwrap/
├── body-texture-map.png
└── report.json
```

Kết quả gần nhất:

| Thông số | Giá trị |
|---|---:|
| Frame dùng cho một vòng | 43/48 |
| Kích thước map | 1259 × 353 px |
| Vùng thân trong ảnh xử lý | x = 358–711 |
| Coverage | 100% |
| Chuyển động đo được | 392.68° |
| Sai số frame gần 360° | 0.41° |

## Giới hạn hiện tại

- Giả định bàn xoay chạy đều; chưa có encoder ghi góc thật cho từng frame.
- Mô hình thân gần hình trụ, chưa dùng hình học 3D thật của từng gai.
- Chưa hiệu chỉnh dịch chuyển hoặc biến dạng cục bộ giữa từng cặp frame.
- Gai nhô ra gây parallax và tự che khuất, nên seam vẫn có thể cắt sai một chân gai dù RGB nguồn rõ.
- Hai mép trái/phải của PNG là cùng một biên 0°/360° và phải được xem như nối vòng.
- `--unwrap-only` dừng ngay sau RGB map; chưa chạy contour, tip/base, graph, fingerprint hoặc đối chiếu ảnh truy vấn.

## Tiêu chí duyệt bước hiện tại

Chỉ chuyển sang tách chân gai và đỉnh gai khi RGB map đạt các điều kiện:

- Không lặp cùng chữ đánh dấu hoặc cùng cụm gai.
- Không có hai ảnh bán trong suốt đè lên nhau.
- Chân gai không bị seam cắt thành hai cấu trúc khác nhau.
- Nét vỏ giữ đủ sắc để đối chiếu trực tiếp với frame gốc.

## Nhánh thử nghiệm depth cho từng gai

Đã bổ sung prototype RGB-D đa frame tại `test_video/rgbd_mesh.py`. Nhánh này
không thay thế RGB unwrap; nó tạo thêm một kênh độ cao theo mét.

Quy trình:

1. Theo dõi tốc độ quay không đều bằng đặc trưng RGB và tọa độ LiDAR.
2. Chuẩn hóa hành trình đo được thành đúng một vòng 360°.
3. Khóa tọa độ dọc quả theo cùng một dải pixel trong mọi frame.
4. Ở mỗi góc, lấy profile depth có confidence cao đúng giữa camera.
5. Ước lượng bề mặt thân cục bộ và trừ khỏi bán kính để thu relief gai.
6. Chạy thêm fusion dải `±22°` làm đối chứng, không dùng làm bề mặt chính.

Lệnh chạy:

```bash
test_video/.venv/bin/python test_video/rgbd_mesh.py \
  --dataset test_video/CAM-TURNTABLE-01 \
  --output test_video/processed/rgbd-spike-fusion \
  --rows 360 --columns 256 --mesh-rows 180 --mesh-columns 180
```

Đầu ra chính:

```text
test_video/processed/rgbd-spike-fusion/
├── depth-aligned-rgb-wide-preview.png
├── depth-aligned-rgb-circular-preview.png
├── spike-height-map.png
├── spike-height-map-circular-preview.png
├── depth-relief-overlay-preview.png
├── radial-surface-meters.npy
├── spike-height-meters.npy
├── fused-band-spike-height-map.png
└── report.json
```

Kết quả `test_video`: centerline giữ relief P99 khoảng 4,15 mm; fusion dải chỉ
còn 1,23 mm dù đạt 86,3% coverage và trung vị 38 quan sát/ô. Vì vậy depth hiện
chỉ là kênh đo hình dạng thô. RGB vẫn phải xác định vị trí tip/chân gai; không
được coi LiDAR 256×192 là ground truth cho từng gai.

Ảnh RGB chính luôn là
`test_video/processed/video-body-unwrap/body-texture-map.png` ở độ phân giải
1259×353. Các file RGB trong thư mục `rgbd-spike-fusion` chỉ là preview căn
theo lưới LiDAR 256×192, không được dùng thay map RGB chính.

Map canonical vẫn là dữ liệu vòng 360°. PNG phẳng có thể xẻ một gai giữa mép
0° và 360° nhưng không làm mất dữ liệu. Hai file `*-circular-preview.png` chép
thêm 30° từ mép đối diện sang mỗi đầu, giúp kiểm tra trọn gai đi qua seam; không
dùng phần chép thêm làm dữ liệu fingerprint mới.
