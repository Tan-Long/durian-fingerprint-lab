# Thay Đổi Phần Ảnh Mẫu Và File Log

## Mục Tiêu

Khi cắm điện thoại vào Mac, có thể kéo trực tiếp thư mục `samples` sang máy. Thư mục này gồm:

- Ảnh mẫu `.jpg` đã ghi thông tin lên ảnh.
- `samples_log.csv`, mỗi ảnh là một dòng dữ liệu.
- `samples_log.xlsx`, hiện là file text phân tách bằng tab nhưng đặt đuôi `.xlsx` để Excel/Numbers mở được.
- Khi xuất ZIP toàn bộ, ứng dụng tách dữ liệu theo thư mục ngày `ddMMyyyy`: video trong `01_videos`, ảnh mẫu trong `02_sample_photos`, log trong `03_sample_logs`.

Ví dụ file log theo ngày:

```text
samples_log_24052026.csv
samples_log_24052026.xlsx
```

## Đã Thay Đổi

- Ảnh mẫu được lưu kèm thông tin hiển thị trực tiếp trên ảnh.
- Màn hình chụp mẫu bỏ trường `Tên mẫu`, chỉ giữ `Sample ID` để định danh ảnh/data.
- Màn hình chụp mẫu có nút cờ `*`; cờ này được ghi lên ảnh, file dữ liệu và dùng tiếp cho thư mục video.
- Một `Sample ID` giữ nguyên cho tới khi có đủ 2 ảnh `Upslope` và `Downslope`; sau đó ứng dụng mới tăng sang `Sample ID` tiếp theo.
- Tên file ảnh gồm `Sample ID`, cờ nếu có, hướng lấy mẫu và thời gian chụp.

Ví dụ:

```text
M-1.1*_Upslope_20260518_094500.jpg
M-1.1*_Downslope_20260518_094700.jpg
```

- `Loại mẫu` là nút chọn riêng `Địa y` / `Không địa y`, không tự động liên kết vào `Sample ID`.
- `Site` được đồng bộ từ GPS và địa chỉ suy ra từ tọa độ. Nếu chưa có địa chỉ, ứng dụng hiển thị tọa độ GPS tạm thời.
- Nếu GPS không cập nhật được, `Site` tự điền site GPS gần nhất đã lưu. Nếu máy chưa từng có GPS thì ghi `Không có GPS` để file dữ liệu không bị trống.
- Ô `Site` vẫn cho nhập tay. Khi người dùng đã nhập tay, ứng dụng giữ nội dung đó và không ghi đè bằng GPS nữa.
- Bên dưới ô `Site` có trạng thái báo rõ đang dùng GPS, tọa độ GPS, site GPS gần nhất, không có GPS, hoặc site nhập tay.
- `Hướng lấy mẫu` là nút chọn riêng `Upslope` / `Downslope`.
- `Hướng camera nhìn vào cây` và `Hướng mảnh xám` cập nhật theo hướng nhìn thời gian thực của máy quay. Hướng mảnh xám là hướng ngược lại với hướng máy quay, tức hướng bề mặt đi ra môi trường.
- Trình giả lập có máy quay giả để xem giao diện và tạo ảnh/dữ liệu giả khi không có iPhone.
- Sau khi chụp mẫu, ứng dụng lưu `Sample ID` hiện tại để màn hình quay video tự điền vào ô `Sample ID`. Người dùng vẫn sửa được trước khi quay.
- Giá trị cuối cùng trong ô `Sample ID` được gắn vào tên thư mục video.

Ví dụ:

```text
cay_0001_1805_M-1.1*
```

- Mỗi thư mục video có thêm `sample_metadata.json` để nối ngược về `Sample ID`, cờ, loại mẫu và địa điểm/site.

## Thông Tin Ghi Trên Ảnh

Thông tin ghi kèm trên ảnh gồm:

- Tên file ảnh.
- `Sample ID`.
- Cờ.
- Loại mẫu.
- Thời gian chụp.
- `Site`.
- Hướng máy quay nhìn vào cây.
- Hướng mảnh xám.
- Hướng lấy mẫu.
- GPS latitude và longitude.
- Độ chính xác GPS.
- Altitude.
- Heading degree và hướng cardinal.
- Địa điểm suy ra từ tọa độ GPS.

## File Dữ Liệu

File dữ liệu bây giờ bắt đầu bằng cột `File ảnh`, nên có thể nối dòng dữ liệu với ảnh mà không cần soi lại nội dung trên ảnh.

Các cột đang ghi:

```text
File ảnh
Sample-ID
Flag
Loại mẫu
Ngày lấy
Lat
Long
GPS_accuracy_m
Altitude_m
Hướng camera degree
Hướng camera cardinal
Hướng mảnh xám degree
Hướng mảnh xám cardinal
Location
Site
Hướng lấy mẫu
```

Các file `samples_log.csv` cũ sẽ được tự chuyển sang thứ tự cột mới khi ứng dụng ghi thêm hoặc xuất dữ liệu lần tiếp theo.

## Quản Lý Ảnh Mẫu

Màn hình chính có nút `Quản lý ảnh mẫu` để:

- Xem từng ảnh đã chụp.
- Xóa mềm vào `samples/recently_deleted`.
- Khôi phục ảnh đã xóa gần đây.
- Xóa vĩnh viễn.

Khi xóa mềm, dòng dữ liệu bị cắt khỏi `samples_log.csv` / `samples_log.xlsx` và lưu trong `recently_deleted/deleted_samples_log.csv` để có thể khôi phục.

Trong `Quản lý ảnh mẫu`, nút `LiDAR` cho phép chọn thư mục video có `sample_metadata.json` và `rgb.mp4`, kéo qua các khung hình, rồi tạo lại ảnh mẫu từ khung đang chọn. Ảnh khôi phục từ LiDAR được ghi thông tin `Recovered from LiDAR`, thêm vào log mẫu và sao lưu vào Photos nếu ứng dụng có quyền.

Khi xuất ZIP toàn bộ, mỗi thư mục ngày gồm riêng `01_videos`, `02_sample_photos`, `03_sample_logs`. File `samples_log.csv` tổng trong ứng dụng được cắt thành các log theo ngày dựa trên thời gian của `File ảnh` / `Ngày lấy`.

Khi chụp ảnh mẫu trên máy thật, ứng dụng xin quyền thêm ảnh vào Photos và lưu thêm một bản sao trong Photos của iPhone.

## Ghi Chú

- Ứng dụng vẫn lưu ảnh thành file trong thư mục `samples`, không nhúng ảnh vào cơ sở dữ liệu, để việc copy thư mục qua Mac đơn giản và nhẹ hơn.
- Không dùng cột chung chung `Heading_degree` / `Heading_cardinal` nữa vì dễ nhầm với `Hướng mảnh xám`. File dữ liệu mới ghi độ/hướng riêng cho máy quay và mảnh xám.
- Các dòng cũ chưa có heading hoặc GPS accuracy sẽ để trống các cột đó sau khi chuyển đổi.
