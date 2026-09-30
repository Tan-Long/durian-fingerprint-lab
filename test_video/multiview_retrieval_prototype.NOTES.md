# Kết luận prototype multi-view

## Câu hỏi

Không ghép atlas; lưu một bank descriptor nhiều góc có đủ nhanh và đủ ổn định để đối chiếu ảnh điện thoại hay không? Kiểu quay nào tốt hơn trên dữ liệu demo: cam cố định + quả xoay, hay quả treo + cam di chuyển?

## Kết quả 2026-08-25

- Mỗi bank: 36 view, tối đa 800 local feature/view, descriptor PCA 32 chiều.
- Dung lượng: `turntable` 985.385 byte/quả; `orbit` 987.457 byte/quả, xấp xỉ 0,99 GB cho 1.000 quả.
- Tìm kiếm vector chính xác trên 36.000 view: median 2,1 ms. Quy mô 1.000 quả chưa cần ANN/vector database.
- Tổng thuật toán một query: median 1,37 giây (`turntable`) và 1,33 giây (`orbit`); phần chậm là trích SIFT và xác minh top-20, không phải tìm database.
- Chỉ `IMG_0069` qua quality gate. Bank `orbit` tốt hơn rõ rệt: 54 geometric inlier / 10 non-dark inlier; `turntable`: 21 / 5.
- Bốn ảnh còn lại chưa đủ bằng chứng. Không được kết luận hệ thống đã nhận fingerprint tự nhiên vì chỉ có một quả và vỏ có nét bút đen.

## Quyết định tạm thời

Multi-view bank giải quyết được lỗi cắt/nối/blur của atlas và chi phí tìm kiếm không phải nút thắt. Chưa hấp thụ prototype vào production: matcher cổ điển hiện chưa đủ recall với góc và ánh sáng tự do.

Lần lấy dữ liệu kế tiếp cần ba camera cố định cao/giữa/thấp, khoá focus/exposure/white-balance, ánh sáng tán đều, quả không đánh dấu, ảnh điện thoại positive đa điều kiện và tối thiểu năm quả khác làm negative control.
