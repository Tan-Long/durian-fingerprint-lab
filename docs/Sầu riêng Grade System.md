Sầu riêng Grade System
Flow hiện tại người dân tròng, thương lái lên gõ và thu hoạch
Tuy nhiên metric đánh giá dựa trên kinh nghiệm, không minh bạch giữa người mua và ngừoi bán. Dẫn tới thương lái ép giá vườn trồng


Grade
Loại A: tròn, kích thước, 2,7 múi to ( từ đầu tới cuối)
Loại B: 2,5 múi 
Dạt: kem, đồ 

Xác định múi nhìn vào khe sọc thân
Gõ để nghe tiếng


V1 chụp ảnh quả sầu riêng, biết số lượng múi,
1.1 quét lidar cả vuonừ (drone lidar, lidar xịn quét 100m) 
V2 sử dụng âm thanh, phát ra tiếng để nghe lại

V1
Chuẩn bị dữ liệu 

Hệ thống Scan ở đầu dây chuyền tách quả, Scan nhanh qua khung rig, sau đó xử lý mẫu, đánh dấu output khi bổ là quả có bao nhiêu múi, múi nào to múi nào lép. Để làm giữ liệu training


Training mô hình

Nhận diện ngay khi vào khung rig 

nhận diện bằng ảnh chụp điện thoại

ước lượng số múi, múi đầy/lép, tỷ lệ cơm ăn được, độ chín? (cái này cần màu và bộ dữ liệu quả chín và quả chưa chín)	1	Cân:
    * shell_weight,
    * edible_flesh_weight,
    * seed_weight.
￼
