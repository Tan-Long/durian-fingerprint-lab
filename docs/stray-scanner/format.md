# Định Dạng Dữ Liệu Stray Scanner

Tài liệu này mô tả các file Stray Scanner ghi ra sau mỗi lần quay. Phần tên file/tên cột giữ nguyên tiếng Anh vì ứng dụng và các đoạn xử lý tự động đang dùng đúng các tên đó.

Mỗi bộ dữ liệu nằm trong một thư mục riêng. Bản TestLab dùng kiểu đặt tên theo cây/mẫu, ví dụ:

```text
cay_0001_1805_M-1.1*
```

Trong đó:

| Phần tên | Nghĩa |
| --- | --- |
| `cay_0001_1805` | Mã cây hoặc nhóm cây |
| `M-1.1` | `Sample ID` mới nhất khi quay |
| `*` | Mẫu/cây được đánh dấu cờ |

## Cấu Trúc Thư Mục

```text
camera_matrix.csv
odometry.csv
imu.csv
depth/
  - 000000.png
  - 000001.png
  - ...
confidence/
  - 000000.png
  - 000001.png
  - ...
distortion/          (không phải lúc nào cũng có)
  - 000000.bin
  - 000001.bin
  - ...
sample_metadata.json
rgb.mp4
```

## File Chính

| File/thư mục | Nghĩa dễ hiểu |
| --- | --- |
| `rgb.mp4` | Video màu từ máy quay iPhone, mã hóa HEVC |
| `depth/` | Bản đồ độ sâu cho từng khung hình |
| `confidence/` | Độ tin cậy của từng điểm đo sâu |
| `camera_matrix.csv` | Thông số máy quay ở khung cuối, giữ để tương thích với dữ liệu cũ |
| `odometry.csv` | Vị trí, hướng nhìn và thông số máy quay theo từng khung hình |
| `distortion/` | Bảng sửa méo ống kính, chỉ có khi máy cung cấp dữ liệu hiệu chuẩn |
| `sample_metadata.json` | Nối thư mục video với `Sample ID` trên màn quay |
| `imu.csv` | Dữ liệu gia tốc và xoay của điện thoại |

## `depth/`

Thư mục `depth/` có một file `.png` cho mỗi khung hình màu. Mỗi ảnh là ảnh xám 16-bit, kích thước 192 x 256. Giá trị pixel là khoảng cách đo được, đơn vị millimet.

Khi đọc bằng OpenCV:

```python
cv2.imread(depth_frame_path, -1)
```

## `confidence/`

Thư mục `confidence/` có bản đồ độ tin cậy tương ứng với từng ảnh trong `depth/`. Mỗi điểm có giá trị:

| Giá trị | Nghĩa |
| --- | --- |
| `0` | Tin cậy thấp |
| `1` | Tin cậy vừa |
| `2` | Tin cậy cao |

## `odometry.csv`

File này có một dòng cho mỗi khung hình. Các cột chính:

| Cột | Nghĩa |
| --- | --- |
| `timestamp` | Thời gian tính bằng giây |
| `frame` | Số khung hình, ví dụ `000005` |
| `x` | Tọa độ x tính bằng mét từ lúc bắt đầu quay |
| `y` | Tọa độ y tính bằng mét từ lúc bắt đầu quay |
| `z` | Tọa độ z tính bằng mét từ lúc bắt đầu quay |
| `qx` | Thành phần x của hướng xoay camera |
| `qy` | Thành phần y của hướng xoay camera |
| `qz` | Thành phần z của hướng xoay camera |
| `qw` | Thành phần w của hướng xoay camera |
| `fx` | Tiêu cự ngang tính theo pixel |
| `fy` | Tiêu cự dọc tính theo pixel |
| `cx` | Tọa độ x của tâm ảnh |
| `cy` | Tọa độ y của tâm ảnh |
| `distortion_center_x` | Tâm méo ống kính theo trục x, để trống nếu không có |
| `distortion_center_y` | Tâm méo ống kính theo trục y, để trống nếu không có |

## `distortion/`

Thư mục này chứa bảng sửa méo ống kính theo từng khung hình. Mỗi file `.bin` là mảng số `float32` little-endian. Tên file khớp với cột `frame` trong `odometry.csv`.

## `sample_metadata.json`

File này giúp biết thư mục video thuộc về `Sample ID` nào mà không cần soi ảnh thủ công. Ứng dụng tự điền từ ảnh mẫu mới nhất nếu có, nhưng người quay vẫn sửa được trước khi bấm quay.

Thông tin thường có:

| Trường | Nghĩa |
| --- | --- |
| `sample_id` | Mã mẫu cuối cùng dùng khi quay |
| `flag` | Có đánh dấu cờ hay không |
| `sample_type` | Loại mẫu |
| `site` | Địa điểm/site |
| `dataset_folder` | Tên thư mục video cuối cùng |

## `imu.csv`

File này ghi gia tốc và tốc độ xoay của điện thoại theo thời gian.

| Cột | Nghĩa |
| --- | --- |
| `timestamp` | Thời gian tính bằng giây |
| `a_x` | Gia tốc theo trục x, đơn vị m/s^2 |
| `a_y` | Gia tốc theo trục y, đơn vị m/s^2 |
| `a_z` | Gia tốc theo trục z, đơn vị m/s^2 |
| `alpha_x` | Tốc độ xoay quanh trục x, đơn vị rad/s |
| `alpha_y` | Tốc độ xoay quanh trục y, đơn vị rad/s |
| `alpha_z` | Tốc độ xoay quanh trục z, đơn vị rad/s |
