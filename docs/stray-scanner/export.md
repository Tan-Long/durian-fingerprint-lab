# Cách Xuất Dữ Liệu

Có 2 cách lấy dữ liệu từ iPhone/iPad ra máy tính:

1. Cắm cáp Lightning/USB-C vào Mac hoặc máy tính.
2. Dùng ứng dụng Files trên iOS để chuyển thư mục sang iCloud Drive, AirDrop hoặc app khác.

## Xuất Bằng Cáp Trên Mac

Các bước:

1. Cắm iPhone/iPad vào Mac.
2. Mở Finder.
3. Chọn thiết bị ở thanh bên trái.
4. Mở tab **Files**.
5. Tìm mục **Stray Scanner**.
6. Kéo thư mục dữ liệu cần lấy ra vị trí lưu trên Mac.

Mỗi thư mục là một bộ dữ liệu đã quay/chụp. Nếu dùng Windows, thao tác tương tự nhưng thường phải mở qua iTunes.

## Xuất Qua Ứng Dụng Files

Trên iPhone/iPad:

1. Mở **Files**.
2. Vào **Browse > On My iPhone > Stray Scanner**.
3. Chọn thư mục dữ liệu.
4. Chuyển sang iCloud Drive, AirDrop hoặc chia sẻ sang app khác.

## Tên Thư Mục Video Mới

Thư mục video LiDAR mới lấy tên từ `Sample ID` đang dùng và dấu cờ nếu có.

Ví dụ:

```text
M-1.1*_video_20260524_121530
```

Khi xuất ZIP toàn bộ, ứng dụng cũng chuẩn hóa các thư mục video cũ có `sample_metadata.json` sang kiểu tên theo `Sample ID`.

Cấu trúc trong file ZIP:

```text
StrayScanner_export_20052026_to_24052026.zip
└── 24052026/
    ├── 01_videos/
    ├── 02_sample_photos/
    ├── 03_sample_logs/
    │   ├── samples_log_24052026.csv
    │   └── samples_log_24052026.xlsx
    └── 04_sample_data/
```

Trong đó:

| Thư mục | Nội dung |
| --- | --- |
| `01_videos` | Video LiDAR/RGB đã quay |
| `02_sample_photos` | Ảnh mẫu đã chụp |
| `03_sample_logs` | Bảng log CSV/XLSX theo ngày |
| `04_sample_data` | Dữ liệu mẫu khác nếu có |
